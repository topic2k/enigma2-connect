# SPDX-License-Identifier: Apache-2.0
"""Additional lifecycle, calendar, transport and multiple receiver regressions."""

from copy import deepcopy
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import device_registry as dr
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.enigma2_connect.api import AuthenticationError, ConnectionError
from custom_components.enigma2_connect.calendar import EnigmaCalendar
from custom_components.enigma2_connect.camera import EnigmaCamera
from custom_components.enigma2_connect.const import DOMAIN
from custom_components.enigma2_connect.notify import EnigmaNotify
from custom_components.enigma2_connect.select import EnigmaSelect

from .conftest import DATA, RESPONSES
from .test_integration import setup


@pytest.mark.parametrize("endpoint", ["about", "statusinfo", "signal", "timerlist"])
async def test_auth_failure_during_setup_requests_reauth(hass, entry, receiver, endpoint):
    receiver[0][endpoint] = AuthenticationError()
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.SETUP_ERROR
    assert any(
        flow["context"]["source"] == "reauth" for flow in hass.config_entries.flow.async_progress()
    )


async def test_unavailable_setup_retries(hass, entry, receiver):
    receiver[0]["statusinfo"] = ConnectionError()
    assert await async_setup_component(hass, DOMAIN, {})
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_repeated_poll_failure_logs_once_and_recovers(hass, entry, receiver, caplog):
    """The coordinator reports transitions instead of logging every failed poll."""
    await setup(hass, entry)
    healthy = deepcopy(receiver[0]["statusinfo"])
    caplog.clear()
    receiver[0]["statusinfo"] = ConnectionError()
    for _ in range(3):
        await entry.runtime_data.async_refresh()
    assert hass.states.get("media_player.test_receiver").state == "unavailable"
    failures = [
        message for message in caplog.messages if "Error fetching enigma2_connect" in message
    ]
    assert len(failures) == 1
    receiver[0]["statusinfo"] = healthy
    for _ in range(2):
        await entry.runtime_data.async_refresh()
    assert hass.states.get("media_player.test_receiver").state == "playing"
    assert caplog.messages.count("Fetching enigma2_connect data recovered") == 1


async def test_slow_poll_cadence(hass, entry, receiver):
    await setup(hass, entry)
    receiver[1].reset_mock()
    await entry.runtime_data.async_refresh()
    endpoints = [call.args[0] for call in receiver[1].call_args_list]
    assert "statusinfo" in endpoints
    assert not set(endpoints) & {"movielist", "timerlist", "bouquets", "getservices"}


async def test_select_shared_catalog_and_actual_channel(hass, entry, receiver):
    await setup(hass, entry)
    channel = EnigmaSelect(entry.runtime_data, "channel")
    assert channel.current_option == "Channel"
    receiver[0]["getservices"] = {
        "services": [{"servicename": "Other", "servicereference": "1:0:1:other"}]
    }
    await entry.runtime_data.select_bouquet("another-bouquet")
    assert channel.options == ["Other"]
    assert channel.current_option is None
    await channel.async_select_option("Other")
    assert receiver[2].call_args.kwargs == {"sRef": "1:0:1:other"}


async def test_notification_and_camera(hass, entry, receiver):
    await setup(hass, entry)
    notifier = EnigmaNotify(entry.runtime_data, "message")
    await notifier.async_send_message("A & B", "Title")
    assert receiver[2].call_args.kwargs["text"] == "Title\nA & B"
    camera = EnigmaCamera(entry.runtime_data)
    with patch.object(
        entry.runtime_data.client, "screenshot", new_callable=AsyncMock, return_value=b"image"
    ) as screenshot:
        assert await camera.async_camera_image() == b"image"
        assert await camera.async_camera_image() == b"image"
        screenshot.assert_awaited_once()


async def test_two_receivers_require_exact_device(hass, entry, receiver):
    await setup(hass, entry)
    receiver[0]["about"]["info"]["ifaces"][0]["mac"] = "11:22:33:44:55:66"
    second = MockConfigEntry(
        domain=DOMAIN,
        title="Other Receiver",
        unique_id="112233445566",
        data={**DATA, "host": "other.local"},
    )
    second.add_to_hass(hass)
    assert await hass.config_entries.async_setup(second.entry_id)
    await hass.async_block_till_done()
    device = dr.async_entries_for_config_entry(dr.async_get(hass), second.entry_id)[0]
    with (
        patch.object(entry.runtime_data, "perform", new_callable=AsyncMock) as first,
        patch.object(second.runtime_data, "perform", new_callable=AsyncMock) as other,
    ):
        await hass.services.async_call(DOMAIN, "reboot", {"device_id": device.id}, blocking=True)
        first.assert_not_awaited()
        other.assert_awaited_once()
    await hass.config_entries.async_unload(second.entry_id)
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(DOMAIN, "reboot", {"device_id": device.id}, blocking=True)


async def test_weekly_timer_dst(hass, entry, receiver):
    hass.config.time_zone = "Europe/Berlin"
    # Saturday before and after European DST ends: same receiver wall clock.
    receiver[0]["timerlist"] = {
        "timers": [
            {
                "begin": int(datetime(2026, 10, 24, 18, tzinfo=UTC).timestamp()),
                "end": int(datetime(2026, 10, 24, 19, tzinfo=UTC).timestamp()),
                "repeated": 32,
                "name": "Weekly",
            }
        ]
    }
    await setup(hass, entry)
    calendar = EnigmaCalendar(entry.runtime_data, "calendar")
    calendar.hass = hass
    events = calendar.events(datetime(2026, 10, 24, tzinfo=UTC), datetime(2026, 11, 2, tzinfo=UTC))
    assert [event.start.hour for event in events] == [20, 20]
    assert [event.start.astimezone(UTC).hour for event in events] == [18, 19]


async def test_reconfigure_rejects_different_device(hass, entry, receiver):
    receiver[0]["about"] = deepcopy(RESPONSES["about"])
    receiver[0]["about"]["info"]["ifaces"][0]["mac"] = "11:22:33:44:55:66"
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "reconfigure", "entry_id": entry.entry_id}, data=DATA
    )
    assert result["reason"] == "wrong_device"


async def test_action_auth_failure_starts_reauth(hass, entry, receiver):
    await setup(hass, entry)
    receiver[2].side_effect = AuthenticationError()
    with pytest.raises(HomeAssistantError):
        await entry.runtime_data.perform(entry.runtime_data.client.command, "vol", set="up")
    await hass.async_block_till_done()
    assert any(
        flow["context"]["source"] == "reauth" for flow in hass.config_entries.flow.async_progress()
    )
