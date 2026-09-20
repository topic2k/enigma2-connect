# SPDX-License-Identifier: Apache-2.0
"""Control failures, device availability and lifecycle behavior in real HA."""

import asyncio
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.util import dt as dt_util

from custom_components.enigma2_connect import async_unload_entry
from custom_components.enigma2_connect.api import (
    CommandRejectedError,
    ConnectionError,
    PowerCommandUnconfirmed,
    ProtocolError,
)
from custom_components.enigma2_connect.button import EnigmaKey, EnigmaRefresh
from custom_components.enigma2_connect.calendar import EnigmaCalendar
from custom_components.enigma2_connect.camera import EnigmaCamera
from custom_components.enigma2_connect.const import KEYS
from custom_components.enigma2_connect.media_player import EnigmaMediaPlayer
from custom_components.enigma2_connect.remote import EnigmaRemote, key_codes
from custom_components.enigma2_connect.select import EnigmaSelect

from .conftest import BOUQUET, REFERENCE
from .test_integration import setup


async def test_player_controls_send_expected_commands(hass, entry, receiver):
    await setup(hass, entry)
    player = EnigmaMediaPlayer(entry.runtime_data)
    await player.async_turn_on()
    receiver[2].assert_awaited_with("powerstate", newstate=4)
    for volume, expected in [(-0.5, "set0"), (0.42, "set42"), (2, "set100")]:
        await player.async_set_volume_level(volume)
        receiver[2].assert_awaited_with("vol", set=expected)
    with patch.object(entry.runtime_data.client, "set_mute", new_callable=AsyncMock) as mute:
        await player.async_mute_volume(True)
        mute.assert_awaited_once_with(True)
    for method, key in [
        ("async_volume_up", "volume_up"),
        ("async_volume_down", "volume_down"),
        ("async_media_play", "play"),
        ("async_media_pause", "pause"),
        ("async_media_stop", "stop"),
        ("async_media_next_track", "channel_up"),
        ("async_media_previous_track", "channel_down"),
    ]:
        await getattr(player, method)()
        receiver[3].assert_awaited_with([KEYS[key]])
    player.hass = hass
    with pytest.raises(ServiceValidationError):
        await player.async_play_media("video", "media-source://other/recording")
    receiver[3].side_effect = ProtocolError()
    with pytest.raises(HomeAssistantError):
        await player.async_media_play()


async def test_remote_sequences_validate_and_preserve_power_semantics(hass, entry, receiver):
    hass.config_entries.async_update_entry(entry, options={"off_mode": "deep_standby"})
    await setup(hass, entry)
    remote = EnigmaRemote(entry.runtime_data, "remote")
    await remote.async_turn_on()
    receiver[2].assert_awaited_with("powerstate", newstate=4)
    await remote.async_turn_off()
    receiver[2].assert_awaited_with("powerstate", newstate=5)
    await remote.async_send_command("ok", num_repeats=2, delay_secs=0, hold_secs=1)
    receiver[3].assert_awaited_with([KEYS["ok"], KEYS["ok"]], delay=0, hold=True)
    receiver[3].reset_mock()
    for command, kwargs in [
        ([], {}),
        (["ok"], {"num_repeats": 0}),
        (["ok"] * 6, {"num_repeats": 100}),
        (["ok"], {"delay_secs": 6}),
    ]:
        with pytest.raises(ServiceValidationError):
            await remote.async_send_command(command, **kwargs)
    receiver[3].assert_not_awaited()
    assert key_codes([]) == []
    with pytest.raises(ServiceValidationError):
        key_codes([768])


async def test_buttons_and_selections_report_failures(hass, entry, receiver):
    await setup(hass, entry)
    coordinator = entry.runtime_data
    await EnigmaKey(coordinator, "ok", KEYS["ok"]).async_press()
    receiver[3].assert_awaited_with([KEYS["ok"]])
    bouquet = EnigmaSelect(coordinator, "bouquet")
    await bouquet.async_select_option(bouquet.options[0])
    receiver[1].assert_any_await("getservices", sRef=BOUQUET)
    for select in (bouquet, EnigmaSelect(coordinator, "channel")):
        with pytest.raises(ServiceValidationError):
            await select.async_select_option("missing")
    refresh = EnigmaRefresh(coordinator, "refresh")
    receiver[1].reset_mock()
    await refresh.async_press()
    assert {"timerlist", "movielist"} <= {call.args[0] for call in receiver[1].call_args_list}
    receiver[0]["statusinfo"] = ConnectionError()
    with pytest.raises(HomeAssistantError) as error:
        await refresh.async_press()
    assert error.value.translation_key == "cannot_update"


async def test_camera_shares_capture_and_handles_unavailability(hass, entry, receiver):
    await setup(hass, entry)
    camera = EnigmaCamera(entry.runtime_data)
    with patch.object(
        entry.runtime_data.client, "screenshot", new_callable=AsyncMock
    ) as screenshot:
        screenshot.return_value = b"image"
        assert (
            await asyncio.gather(camera.async_camera_image(), camera.async_camera_image())
            == [b"image"] * 2
        )
        screenshot.assert_awaited_once()
        camera._fetched = 0
        screenshot.side_effect = ConnectionError()
        assert await camera.async_camera_image() is None
        for standby, available in [(True, True), (False, False)]:
            entry.runtime_data.data = replace(
                entry.runtime_data.data,
                state=replace(entry.runtime_data.data.state, standby=standby),
            )
            entry.runtime_data.last_update_success = available
            screenshot.reset_mock()
            assert await camera.async_camera_image() is None
            screenshot.assert_not_awaited()


async def test_failed_platform_unload_keeps_background_manager(hass, entry, receiver):
    await setup(hass, entry)
    with (
        patch.object(hass.config_entries, "async_unload_platforms", return_value=False),
        patch.object(
            entry.runtime_data.recording_images, "async_close", new_callable=AsyncMock
        ) as close,
    ):
        assert not await async_unload_entry(hass, entry)
        close.assert_not_awaited()


async def test_calendar_ignores_corrupt_intervals_and_returns_next_event(hass, entry, receiver):
    await setup(hass, entry)
    calendar = EnigmaCalendar(entry.runtime_data, "calendar")
    calendar.hass = hass
    now = dt_util.utcnow()
    valid = {
        "begin": int((now + timedelta(hours=1)).timestamp()),
        "end": int((now + timedelta(hours=2)).timestamp()),
        "name": "Next",
    }
    entry.runtime_data.data = replace(
        entry.runtime_data.data,
        timers=[{}, {"begin": "bad", "end": 0}, {"begin": 2, "end": 1}, valid],
    )
    assert calendar.events(now, now) == []
    assert calendar.event.summary == "Next"
    # First occurrence traverses the autumn repeated hour backwards in wall time.
    begin = datetime(2026, 10, 25, 0, 45, tzinfo=UTC)
    end = datetime(2026, 10, 25, 1, 15, tzinfo=UTC)
    hass.config_entries.async_update_entry(entry, options={"receiver_timezone": "Europe/Berlin"})
    entry.runtime_data.data = replace(
        entry.runtime_data.data,
        timers=[
            {
                "begin": int(begin.timestamp()),
                "end": int(end.timestamp()),
                "repeated": 64,
                "name": "Fold",
            }
        ],
    )
    events = calendar.events(begin - timedelta(hours=1), end + timedelta(days=8))
    assert events[0].end.timestamp() - events[0].start.timestamp() == 1800
    assert len(events) == 2
    # The following weekly 02:30 occurrence does not exist at the spring transition.
    begin = datetime(2026, 3, 22, 1, 30, tzinfo=UTC)
    entry.runtime_data.data = replace(
        entry.runtime_data.data,
        timers=[
            {
                "begin": int(begin.timestamp()),
                "end": int((begin + timedelta(minutes=15)).timestamp()),
                "repeated": 64,
                "name": "Spring",
            }
        ],
    )
    assert len(calendar.events(begin - timedelta(hours=1), begin + timedelta(days=8))) == 1


async def test_player_artwork_failure_and_reference_playback(hass, entry, receiver):
    await setup(hass, entry)
    player = EnigmaMediaPlayer(entry.runtime_data)
    await player.async_play_media("enigma2_reference", REFERENCE)
    receiver[2].assert_awaited_with("zap", sRef=REFERENCE)
    with patch.object(entry.runtime_data.client, "picon", side_effect=ConnectionError()):
        assert await player.async_get_media_image() == (None, None)


async def test_optional_data_and_unconfirmed_power_are_explicit(hass, entry, receiver):
    await setup(hass, entry)
    receiver[0]["timerlist"] = {"timers": "invalid"}
    entry.runtime_data.invalidate_lists()
    await entry.runtime_data.async_refresh()
    assert entry.runtime_data.last_update_success
    assert entry.runtime_data.data.timers is None
    assert hass.states.async_all("calendar")[0].state == "unavailable"
    with pytest.raises(HomeAssistantError) as error:
        await entry.runtime_data.perform(AsyncMock(side_effect=PowerCommandUnconfirmed()))
    assert error.value.translation_key == "power_unconfirmed"


async def test_missing_receiver_model_retries_setup(hass, entry, receiver):
    from homeassistant.config_entries import ConfigEntryState
    from homeassistant.setup import async_setup_component

    receiver[0]["about"] = {"info": {}}
    assert await async_setup_component(hass, "enigma2_connect", {})
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_message_action_and_invalid_timer_window(hass, entry, receiver):
    from homeassistant.helpers import device_registry as dr

    await setup(hass, entry)
    device = dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id)[0]
    await hass.services.async_call(
        "enigma2_connect", "message", {"device_id": device.id, "text": "Hello"}, blocking=True
    )
    receiver[2].assert_awaited_with("message", text="Hello", type=1, timeout=10)
    receiver[2].reset_mock()
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            "enigma2_connect",
            "timer_add",
            {
                "device_id": device.id,
                "service_reference": REFERENCE,
                "begin": 100,
                "end": 99,
                "name": "Invalid",
            },
            blocking=True,
        )
    receiver[2].assert_not_awaited()


async def test_receiver_without_reported_mac_keeps_persistent_identity(hass, entry, receiver):
    from homeassistant.helpers import device_registry as dr

    receiver[0]["about"]["info"].pop("ifaces")
    await setup(hass, entry)
    devices = dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id)
    assert len(devices) == 1
    assert devices[0].identifiers == {("enigma2_connect", entry.unique_id)}
    assert not devices[0].connections


async def test_structured_rejection_keeps_translated_ha_error(hass, entry, receiver, caplog):
    await setup(hass, entry)
    rejection = CommandRejectedError(
        {"result": False, "message": "private-token", "conflicts": [{"name": "Private title"}]}
    )
    receiver[2].side_effect = rejection
    with pytest.raises(HomeAssistantError) as caught:
        await entry.runtime_data.perform(
            entry.runtime_data.client.command, "timeradd", refresh=False
        )
    assert caught.value.translation_key == "request_failed"
    assert caught.value.__cause__ is rejection
    assert "private-token" not in str(caught.value)
    assert "Private title" not in caplog.text
    assert "private-token" not in caplog.text
