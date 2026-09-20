# SPDX-License-Identifier: Apache-2.0
"""Real HA config-entry lifecycle, entity platforms and actions."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
import voluptuous as vol
from homeassistant.config_entries import ConfigEntryState
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
from probatio.codecs.fields import to_field_list

from custom_components.enigma2_connect.api import (
    AuthenticationError,
    ConnectionError,
    ProtocolError,
    UnsupportedError,
)
from custom_components.enigma2_connect.calendar import EnigmaCalendar
from custom_components.enigma2_connect.config_flow import schema
from custom_components.enigma2_connect.const import DOMAIN
from custom_components.enigma2_connect.diagnostics import async_get_config_entry_diagnostics
from custom_components.enigma2_connect.media_player import EnigmaMediaPlayer
from custom_components.enigma2_connect.remote import EnigmaRemote

from .conftest import DATA, REFERENCE


async def setup(hass, entry):
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED


async def test_actions_registered_without_entries(hass):
    """Automations can discover action schemas even without a configured receiver."""
    assert not hass.config_entries.async_entries(DOMAIN)
    assert await async_setup_component(hass, DOMAIN, {})
    assert set(hass.services.async_services()[DOMAIN]) == {
        "reboot",
        "restart_gui",
        "deep_standby",
        "message",
        "record_now",
        "epg_search",
        "epg_similar",
        "record_event",
        "recordings_list",
        "recording_manage",
        "recording_operation_status",
        "recording_destinations",
        "timer_add",
        "timer_edit",
        "timer_delete",
        "timer_toggle",
    }


async def test_setup_all_platforms_and_unload(hass, entry, receiver):
    await setup(hass, entry)
    assert entry.state is ConfigEntryState.LOADED
    entities = er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)
    assert {item.domain for item in entities} == {
        "media_player",
        "remote",
        "notify",
        "select",
        "sensor",
        "binary_sensor",
        "camera",
        "calendar",
        "button",
    }
    assert len({item.device_id for item in entities}) == 1
    for item in entities:
        if item.disabled_by is None:
            assert hass.states.get(item.entity_id) is not None, item.entity_id
    assert hass.states.get("remote.test_receiver_remote").state == "on"
    state = hass.states.get("media_player.test_receiver")
    assert state.state == "playing"
    assert state.attributes["source_list"] == ["Channel"]
    assert "stream_url" not in state.attributes
    assert "secret" not in str(hass.states.async_all())
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_optional_failure_is_unknown_and_retries(hass, entry, receiver):
    receiver[0]["timerlist"] = UnsupportedError()
    receiver[0]["movielist"] = ConnectionError()
    await setup(hass, entry)
    assert entry.runtime_data.data.movies is None
    assert entry.runtime_data.data.timers is None
    receiver[0]["timerlist"] = {"timers": []}
    receiver[0]["movielist"] = {"movies": []}
    entry.runtime_data.invalidate_lists()
    await entry.runtime_data.async_refresh()
    assert entry.runtime_data.data.movies == []
    assert entry.runtime_data.data.timers == []


async def test_offline_is_unavailable_not_standby(hass, entry, receiver):
    await setup(hass, entry)
    receiver[0]["statusinfo"] = ConnectionError()
    await entry.runtime_data.async_refresh()
    assert not entry.runtime_data.last_update_success
    assert hass.states.get("media_player.test_receiver").state == "unavailable"
    receiver[0]["statusinfo"] = {"inStandby": True}
    await entry.runtime_data.async_refresh()
    assert entry.runtime_data.data.state.standby is True


async def test_service_target_required_and_timer_validation(hass, entry, receiver):
    await setup(hass, entry)
    device = dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id)[0]
    with pytest.raises(vol.Invalid):
        await hass.services.async_call(DOMAIN, "reboot", {}, blocking=True)
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(DOMAIN, "reboot", {"device_id": "missing"}, blocking=True)
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            "timer_add",
            {
                "device_id": device.id,
                "service_reference": REFERENCE,
                "begin": 100,
                "end": 99,
                "name": "Test",
            },
            blocking=True,
        )
    receiver[2].assert_not_awaited()
    await hass.services.async_call(
        DOMAIN,
        "timer_add",
        {
            "device_id": device.id,
            "service_reference": REFERENCE,
            "begin": 100,
            "end": 200,
            "name": "Test",
        },
        blocking=True,
    )
    assert receiver[2].call_args.args == ("timeradd",)
    assert receiver[2].call_args.kwargs["sRef"] == REFERENCE


async def test_action_rejection_surfaces(hass, entry, receiver):
    await setup(hass, entry)
    receiver[2].side_effect = ProtocolError()
    entity = EnigmaMediaPlayer(entry.runtime_data)
    with pytest.raises(HomeAssistantError):
        await entity.async_turn_on()


async def test_media_channel_number_sources_browse(hass, entry, receiver):
    await setup(hass, entry)
    entity = EnigmaMediaPlayer(entry.runtime_data)
    entity.hass = hass
    await entity.async_play_media("channel", "105")
    assert receiver[3].call_args.args == ([2, 11, 6, 352],)
    await entity.async_select_source("Channel")
    assert receiver[2].call_args.kwargs == {"sRef": REFERENCE}
    with pytest.raises(ServiceValidationError):
        await entity.async_play_media("channel", "0")
    with pytest.raises(ServiceValidationError):
        await entity.async_select_source("Missing")
    browse = await entity.async_browse_media()
    assert browse.children == []
    assert entity.source_list == ["Channel"]


async def test_media_browse_recordings_including_nested_folders(hass, entry, receiver):
    paths = [
        "/media/hdd/movie/News.ts",
        "/media/hdd/movie/Series/Episode.ts",
        "/media/hdd/movie/Series/Season 1/Episode.ts",
    ]
    movies = [{"serviceref": f"1:0:0:0:0:0:0:0:0:0:{path}", "filename": path} for path in paths]
    movies[0]["eventname"] = "News recording"
    original_get = receiver[1].side_effect

    async def get(endpoint, **params):
        if endpoint == "movielist":
            return {
                "directory": "/media/hdd/movie/",
                "movies": (movies if params.get("recursive") else movies[:1])
                + [{"eventname": "Missing service reference"}],
            }
        return await original_get(endpoint, **params)

    receiver[1].side_effect = get
    await setup(hass, entry)
    entity = EnigmaMediaPlayer(entry.runtime_data)
    entity.hass = hass
    browse = await entity.async_browse_media()
    assert not browse.can_play
    assert browse.can_expand
    assert [child.title for child in browse.children] == ["Series", "News recording"]
    folder = browse.children[0]
    assert folder.can_expand and not folder.can_play
    series = await entity.async_browse_media(folder.media_content_type, folder.media_content_id)
    assert [child.title for child in series.children] == ["Season 1", "Episode.ts"]
    assert series.children[1].media_content_id == movies[1]["serviceref"]
    season = series.children[0]
    nested_folder = await entity.async_browse_media(
        season.media_content_type, season.media_content_id
    )
    assert [child.title for child in nested_folder.children] == ["Episode.ts"]
    assert entity.source_list == ["Channel"]
    nested = nested_folder.children[0]
    assert nested.can_play and not nested.can_expand
    await entity.async_play_media(nested.media_content_type, nested.media_content_id)
    assert receiver[2].call_args.args == ("zap",)
    assert receiver[2].call_args.kwargs == {"sRef": movies[-1]["serviceref"]}


async def test_bad_macro_has_no_side_effect(hass, entry, receiver):
    await setup(hass, entry)
    entity = EnigmaRemote(entry.runtime_data, "remote")
    with pytest.raises(ServiceValidationError):
        await entity.async_send_command(["menu", "not-a-key"])
    receiver[3].assert_not_awaited()


async def test_diagnostics_allowlist(hass, entry, receiver):
    await setup(hass, entry)
    result = str(await async_get_config_entry_diagnostics(hass, entry))
    for value in ("secret", "receiver.local", "AA:BB", "Channel", REFERENCE):
        assert value not in result


async def test_calendar_overlap_disabled_and_repetition(hass, entry, receiver):
    receiver[0]["timerlist"] = {
        "timers": [
            {
                "begin": int(datetime(2026, 9, 12, 10, tzinfo=UTC).timestamp()),
                "end": int(datetime(2026, 9, 12, 12, tzinfo=UTC).timestamp()),
                "name": "Active",
                "serviceref": REFERENCE,
            },
            {
                "begin": int(datetime(2026, 9, 12, 10, tzinfo=UTC).timestamp()),
                "end": int(datetime(2026, 9, 12, 12, tzinfo=UTC).timestamp()),
                "name": "Disabled",
                "disabled": "true",
            },
        ]
    }
    await setup(hass, entry)
    entity = EnigmaCalendar(entry.runtime_data, "calendar")
    entity.hass = hass
    events = await entity.async_get_events(
        hass, datetime(2026, 9, 12, 11, tzinfo=UTC), datetime(2026, 9, 12, 13, tzinfo=UTC)
    )
    assert [event.summary for event in events] == ["Active"]


async def test_user_flow_and_duplicate(hass, receiver):
    with patch("custom_components.enigma2_connect.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
        assert result["type"] == "form"
        result = await hass.config_entries.flow.async_configure(result["flow_id"], DATA)
        assert result["type"] == "create_entry"
        assert result["result"].unique_id == "aabbccddeeff"
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}, data=DATA
        )
        assert result["type"] == "abort"
        assert result["reason"] == "already_configured"


async def test_user_flow_without_authentication_fields(hass, receiver):
    data = {
        "host": "receiver.local",
        "port": 80,
        "use_https": False,
        "verify_ssl": True,
    }
    with patch("custom_components.enigma2_connect.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
        result = await hass.config_entries.flow.async_configure(result["flow_id"], data)
    assert result["type"] == "create_entry"
    assert "username" not in result["data"]
    assert "password" not in result["data"]


def test_user_schema_keeps_empty_credentials_optional():
    fields = {
        field["name"]: field
        for field in to_field_list(schema({}), custom_serializer=cv.custom_serializer)
    }
    assert fields["port"]["required"] is True
    for name in ("username", "password"):
        assert fields[name]["required"] is False
        assert "default" not in fields[name]


@pytest.mark.parametrize(
    ("failure", "error"),
    [
        (AuthenticationError(), "invalid_auth"),
        (ConnectionError(), "cannot_connect"),
        ({"info": {}}, "invalid_response"),
    ],
)
async def test_user_flow_errors(hass, receiver, failure, error):
    receiver[0]["about"] = failure
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}, data=DATA
    )
    assert result["type"] == "form"
    assert result["errors"]["base"] == error


async def test_options_flow(hass, entry, receiver):
    with patch.object(hass.config_entries, "async_reload", new_callable=AsyncMock) as reload:
        result = await hass.config_entries.options.async_init(entry.entry_id)
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"next_step_id": "settings"}
        )
        assert result["type"] == "form"
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {
                "scan_interval": 30,
                "artwork": "picon",
                "bouquet": "",
                "message_timeout": 10,
                "message_type": 1,
            },
        )
        assert result["type"] == "create_entry"
        assert entry.options["scan_interval"] == 30
        await hass.async_block_till_done()
        reload.assert_awaited_once_with(entry.entry_id)


async def test_reconfigure_and_reauth(hass, entry, receiver):
    with patch.object(hass.config_entries, "async_reload", new_callable=AsyncMock):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "reconfigure", "entry_id": entry.entry_id}
        )
        assert result["type"] == "form"
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {**DATA, "host": "new.local"}
        )
        assert result["type"] == "abort"
        assert entry.data["host"] == "new.local"
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "reauth", "entry_id": entry.entry_id}, data=entry.data
        )
        assert result["step_id"] == "reauth_confirm"
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {**DATA, "password": "new-secret"}
        )
        assert result["reason"] == "reauth_successful"
        assert entry.data["password"] == "new-secret"


@pytest.mark.parametrize(
    ("action", "endpoint"),
    [
        ("timer_add", "timeradd"),
        ("timer_toggle", "timertogglestatus"),
        ("timer_delete", "timerdelete"),
    ],
)
async def test_timer_actions_trim_only_outer_reference_whitespace(
    hass, entry, receiver, action, endpoint
):
    await setup(hass, entry)
    device = dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id)[0]
    reference = "1:0:19:283D:3FB:1:C00000:0:0:0:"
    stream_reference = "4097:0:0:0:0:0:0:0:0:0:http%3a//example.test/live:My Channel"
    for supplied, expected in [
        (" " + reference, reference),
        ("\t" + reference + " \r\n", reference),
        (reference, reference),
        (" " + stream_reference + " ", stream_reference),
    ]:
        receiver[2].reset_mock()
        data = {"device_id": device.id, "service_reference": supplied, "begin": 100, "end": 200}
        if action == "timer_add":
            data["name"] = "Whitespace regression"
        await hass.services.async_call(DOMAIN, action, data, blocking=True)
        assert receiver[2].await_count == 1
        assert receiver[2].call_args.args == (endpoint,)
        assert receiver[2].call_args.kwargs["sRef"] == expected
        assert receiver[2].call_args.kwargs["begin"] == 100
        assert receiver[2].call_args.kwargs["end"] == 200


@pytest.mark.parametrize("action", ["timer_add", "timer_toggle", "timer_delete"])
@pytest.mark.parametrize("reference", ["", " \t\r\n"])
async def test_timer_actions_reject_blank_reference_before_receiver(
    hass, entry, receiver, action, reference
):
    await setup(hass, entry)
    device = dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id)[0]
    receiver[1].reset_mock()
    receiver[2].reset_mock()
    data = {"device_id": device.id, "service_reference": reference, "begin": 100, "end": 200}
    if action == "timer_add":
        data["name"] = "Blank reference"
    with pytest.raises(vol.Invalid):
        await hass.services.async_call(DOMAIN, action, data, blocking=True)
    receiver[1].assert_not_awaited()
    receiver[2].assert_not_awaited()
