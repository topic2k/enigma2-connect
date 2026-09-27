# SPDX-License-Identifier: Apache-2.0
"""Audio selection with real HA entities and simulated receiver replies."""

from copy import deepcopy

import pytest
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from custom_components.enigma2_connect.api import (
    AuthenticationError,
    CommandUnconfirmed,
    UnsupportedError,
)
from custom_components.enigma2_connect.audio_tracks import parse_tracks
from custom_components.enigma2_connect.select import EnigmaAudioSelect

TRACKS = {
    "result": True,
    "tracklist": [
        {"index": 0, "description": "German (AC3)", "active": True},
        {"index": 2, "description": "English (AAC)", "active": False},
    ],
}


@pytest.mark.parametrize(
    "data",
    [
        None,
        {},
        {"result": False},
        {"result": True},
        {"result": True, "tracklist": {}},
        {"result": True, "tracklist": [None]},
    ],
)
def test_invalid_container(data):
    assert parse_tracks(data) is None


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("index", True),
        ("index", -1),
        ("index", "0"),
        ("description", None),
        ("description", " "),
        ("active", None),
    ],
)
def test_invalid_track(key, value):
    data = deepcopy(TRACKS)
    data["tracklist"][0][key] = value
    assert parse_tracks(data) is None


def test_duplicates_and_active_flags():
    data = deepcopy(TRACKS)
    data["tracklist"][1]["index"] = 0
    assert parse_tracks(data) is None
    data = deepcopy(TRACKS)
    data["tracklist"][1]["active"] = True
    assert parse_tracks(data) is None
    data["tracklist"][1]["active"] = "false"
    data["tracklist"][1]["description"] = data["tracklist"][0]["description"]
    tracks = parse_tracks(data)
    assert len({t.option for t in tracks}) == 2


async def setup(hass, entry, receiver):
    receiver[0]["getaudiotracks"] = deepcopy(TRACKS)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return EnigmaAudioSelect(entry.runtime_data)


async def test_entity_refresh_selection(hass, entry, receiver):
    entity = await setup(hass, entry, receiver)
    assert entity.available
    assert entity.options == ["1: German (AC3)", "3: English (AAC)"]
    assert entity.current_option == entity.options[0]
    assert any(
        s.attributes.get("options") == entity.options for s in hass.states.async_all("select")
    )
    original = receiver[1].side_effect

    async def get(endpoint, **params):
        if endpoint == "selectaudiotrack":
            assert params == {"id": 2}
            assert entry.runtime_data.client.command_lock.locked()
            receiver[0]["getaudiotracks"]["tracklist"][0]["active"] = False
            receiver[0]["getaudiotracks"]["tracklist"][1]["active"] = True
            return {"result": True}
        return await original(endpoint, **params)

    receiver[1].side_effect = get
    await entity.async_select_option(entity.options[1])
    assert entity.current_option == entity.options[1]
    with pytest.raises(ServiceValidationError):
        await entity.async_select_option("missing")
    receiver[0]["getaudiotracks"]["tracklist"] = []
    await entry.runtime_data.async_refresh()
    assert not entity.available
    assert entity.options == []
    assert entity.current_option is None
    with pytest.raises(ServiceValidationError):
        await entity.async_select_option("1: German (AC3)")


@pytest.mark.parametrize(
    "failure",
    [UnsupportedError(), {"result": True, "tracklist": [None]}, {"result": True, "tracklist": []}],
)
async def test_optional_failure_and_recovery(hass, entry, receiver, failure):
    entity = await setup(hass, entry, receiver)
    receiver[0]["getaudiotracks"] = failure
    await entry.runtime_data.async_refresh()
    assert entry.runtime_data.last_update_success
    assert not entity.available
    assert not entity.options
    receiver[0]["getaudiotracks"] = deepcopy(TRACKS)
    await entry.runtime_data.async_refresh()
    assert entity.available
    receiver[0]["statusinfo"]["inStandby"] = True
    receiver[1].reset_mock()
    await entry.runtime_data.async_refresh()
    assert not entity.available
    assert not entity.options
    assert not any(c.args[0] == "getaudiotracks" for c in receiver[1].call_args_list)


@pytest.mark.parametrize("change", ["service", "standby", "tracks", "description", "midread"])
async def test_stale_selection_never_writes(hass, entry, receiver, change):
    entity = await setup(hass, entry, receiver)
    option = entity.options[1]
    if change == "service":
        receiver[0]["statusinfo"]["currservice_serviceref"] = "other"
    elif change == "standby":
        receiver[0]["statusinfo"]["inStandby"] = True
    elif change == "tracks":
        receiver[0]["getaudiotracks"] = {"result": False}
    elif change == "description":
        receiver[0]["getaudiotracks"]["tracklist"][1]["description"] = "changed"
    else:
        original = receiver[1].side_effect

        async def get(endpoint, **params):
            if endpoint == "getaudiotracks":
                receiver[0]["statusinfo"]["currservice_serviceref"] = "other"
            return await original(endpoint, **params)

        receiver[1].side_effect = get
    with pytest.raises(HomeAssistantError) as error:
        await entity.async_select_option(option)
    assert error.value.translation_key == "audio_track_changed"
    assert not any(c.args[0] == "selectaudiotrack" for c in receiver[1].call_args_list)


@pytest.mark.parametrize(
    ("reply", "key"),
    [
        ({"result": False}, "request_failed"),
        ({}, "audio_track_unconfirmed"),
        ({"result": True}, "audio_track_unconfirmed"),
        (CommandUnconfirmed(), "audio_track_unconfirmed"),
        (AuthenticationError(), "invalid_auth"),
    ],
)
async def test_write_failures(hass, entry, receiver, reply, key):
    entity = await setup(hass, entry, receiver)
    receiver[0]["selectaudiotrack"] = reply
    with pytest.raises(HomeAssistantError) as error:
        await entity.async_select_option(entity.options[1])
    assert error.value.translation_key == key
    assert sum(c.args[0] == "selectaudiotrack" for c in receiver[1].call_args_list) == 1


async def test_poll_auth_failure(hass, entry, receiver):
    entity = await setup(hass, entry, receiver)
    receiver[0]["getaudiotracks"] = AuthenticationError()
    await entry.runtime_data.async_refresh()
    assert not entry.runtime_data.last_update_success
    assert not entity.available


@pytest.mark.parametrize(
    "change",
    [
        "missing_reference",
        "missing_state",
        "late_standby",
        "late_service",
        "late_tracks",
        "late_error",
        "late_invalid_state",
        "late_auth",
    ],
)
async def test_workflow_boundaries(change):
    import asyncio
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    from custom_components.enigma2_connect.audio_tracks import AudioTrackError, select_track

    written = False

    async def get(endpoint, **params):
        nonlocal written
        if endpoint == "selectaudiotrack":
            written = True
            return {"result": True}
        if endpoint == "statusinfo":
            if change == "missing_state" or (written and change == "late_invalid_state"):
                return {}
            return {
                "inStandby": written and change == "late_standby",
                "currservice_serviceref": "other"
                if written and change == "late_service"
                else "service",
            }
        if written and change == "late_error":
            raise UnsupportedError()
        if written and change == "late_auth":
            raise AuthenticationError()
        if written and change == "late_tracks":
            return {}
        return TRACKS

    client = SimpleNamespace(command_lock=asyncio.Lock(), get=AsyncMock(side_effect=get))
    expected = AuthenticationError if change == "late_auth" else AudioTrackError
    with pytest.raises(expected):
        await select_track(
            client, None if change == "missing_reference" else "service", parse_tracks(TRACKS)[1]
        )
    assert written == change.startswith("late_")
    assert not client.command_lock.locked()
