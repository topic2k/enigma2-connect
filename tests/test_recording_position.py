# SPDX-License-Identifier: Apache-2.0
"""Optional receiver playback samples, distinct from EPG and saved progress."""

from copy import deepcopy

import pytest
from homeassistant.components.media_player.const import MediaPlayerEntityFeature, MediaPlayerState

from custom_components.enigma2_connect.api import ReceiverError
from custom_components.enigma2_connect.media_player import EnigmaMediaPlayer
from custom_components.enigma2_connect.models import ReceiverState

from .test_integration import setup

REFERENCE = "1:0:0:0:0:0:0:0:0:0:/media/hdd/movie/Example.ts"
RAW = {"inStandby": False, "currservice_serviceref": REFERENCE}
CURRENT = {
    "info": {"ref": REFERENCE},
    "now": {"sref": REFERENCE, "position": 120, "duration_sec": 600, "remaining": 999},
}


@pytest.mark.parametrize("position", [0, 120, 600, 650])
def test_recording_seconds(position):
    current = deepcopy(CURRENT)
    current["now"]["position"] = position
    state = ReceiverState.parse(RAW, current)
    assert state.media_position == position
    assert state.media_duration == 600


@pytest.mark.parametrize("value", [None, True, False, -1, 1.5, "120", "12%", float("nan"), []])
def test_invalid_position_is_unknown(value):
    current = deepcopy(CURRENT)
    current["now"]["position"] = value
    state = ReceiverState.parse(RAW, current)
    assert state.media_position is state.media_duration is None


@pytest.mark.parametrize("value", [None, True, 0, -1, 1.5, "600", float("inf"), {}])
def test_invalid_duration_preserves_position(value):
    current = deepcopy(CURRENT)
    current["now"]["duration_sec"] = value
    state = ReceiverState.parse(RAW, current)
    assert state.media_position == 120
    assert state.media_duration is None


@pytest.mark.parametrize(
    "current", [None, {}, {"info": []}, {"info": {"ref": REFERENCE}, "now": []}]
)
def test_missing_optional_data(current):
    state = ReceiverState.parse(RAW, current)
    assert state.media_position is state.media_duration is None


@pytest.mark.parametrize("section", ["info", "now"])
@pytest.mark.parametrize("reference", [None, "", REFERENCE + "other"])
def test_mixed_service_snapshots_are_rejected(section, reference):
    current = deepcopy(CURRENT)
    current[section]["ref" if section == "info" else "sref"] = reference
    state = ReceiverState.parse(RAW, current)
    assert state.media_position is state.media_duration is None


@pytest.mark.parametrize(
    "reference",
    [None, "1:0:1:123:0:0:0:0:0:0:", "4097:0:0:0:0:0:0:0:0:0:http%3a//example.org/video"],
)
def test_other_media_cannot_inherit_recording_progress(reference):
    state = ReceiverState.parse({**RAW, "currservice_serviceref": reference}, CURRENT)
    assert state.media_position is state.media_duration is None


def test_standby_and_older_openwebif():
    state = ReceiverState.parse({**RAW, "inStandby": True}, CURRENT)
    assert state.media_position is state.media_duration is None
    current = deepcopy(CURRENT)
    del current["now"]["position"]
    state = ReceiverState.parse(RAW, current)
    assert state.media_position is state.media_duration is None


def test_receiver_reference_encoding_preserves_literal_path_characters():
    reference = REFERENCE.replace("Example", "Grüße &amp; 100% %2F")
    encoded = REFERENCE.replace("Example", "Gr%C3%BC%C3%9Fe %26amp; 100%25 %252F")
    current = deepcopy(CURRENT)
    current["info"]["ref"] = current["now"]["sref"] = encoded
    state = ReceiverState.parse({**RAW, "currservice_serviceref": reference}, current)
    assert state.media_position == 120


async def test_ha_samples_refresh_and_clear_without_pause_inference(hass, entry, receiver):
    replies, calls, commands, keys = receiver
    replies["statusinfo"].update(RAW)
    replies["getcurrent"] = deepcopy(CURRENT)
    await setup(hass, entry)
    coordinator = entry.runtime_data
    player = EnigmaMediaPlayer(coordinator)
    entity_id = "media_player.test_receiver"
    state = hass.states.get(entity_id)
    assert state.attributes["media_position"] == 120
    assert state.attributes["media_duration"] == 600
    assert state.attributes["media_remaining"] == 480
    assert state.attributes["media_position_updated_at"] == player.media_position_updated_at
    assert player.media_position_updated_at.tzinfo is not None
    assert player.assumed_state
    assert not player.supported_features & MediaPlayerEntityFeature.SEEK

    for position in (120, 150, 30, 650):
        replies["getcurrent"]["now"]["position"] = position
        calls.reset_mock()
        await coordinator.async_refresh()
        assert player.media_position == position
        assert player.extra_state_attributes["media_remaining"] == max(0, 600 - position)
        assert player.state == MediaPlayerState.PLAYING
        assert player.media_position_updated_at is not None
        assert sum(call.args == ("getcurrent",) for call in calls.await_args_list) == 1

    replies["getcurrent"]["now"]["duration_sec"] = 0
    await coordinator.async_refresh()
    assert player.media_position == 650
    assert player.media_duration is None
    assert "media_remaining" not in player.extra_state_attributes

    replies["getcurrent"] = ReceiverError("optional read failed")
    await coordinator.async_refresh()
    assert player.available
    assert player.media_position is player.media_duration is None
    assert player.media_position_updated_at is None
    assert "media_position" not in hass.states.get(entity_id).attributes

    replies["getcurrent"] = deepcopy(CURRENT)
    await coordinator.async_refresh()
    assert player.media_position == 120
    # Switching between two recordings or to live TV must clear mixed samples.
    for reference in (REFERENCE + "other", "1:0:1:123:0:0:0:0:0:0:"):
        replies["statusinfo"]["currservice_serviceref"] = reference
        await coordinator.async_refresh()
        assert player.media_position is player.media_duration is None
        assert player.media_position_updated_at is None
    replies["statusinfo"].update(RAW)
    await coordinator.async_refresh()
    assert player.media_position == 120
    replies["statusinfo"] = ReceiverError("offline")
    await coordinator.async_refresh()
    assert not player.available
    assert player.media_position is player.media_duration is None
    assert "media_remaining" not in player.extra_state_attributes

    replies["statusinfo"] = {**RAW, "inStandby": True}
    await coordinator.async_refresh()
    assert player.media_position is player.media_duration is None
    assert player.extra_state_attributes == {}
    commands.assert_not_awaited()
    keys.assert_not_awaited()
