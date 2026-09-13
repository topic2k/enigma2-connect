# SPDX-License-Identifier: Apache-2.0
"""Functions identified in the official Enigma2 integration and its library."""

from unittest.mock import AsyncMock, patch

from custom_components.enigma2_connect.api import UnsupportedError
from custom_components.enigma2_connect.media_player import EnigmaMediaPlayer
from custom_components.enigma2_connect.models import ReceiverState, picon_candidates

from .conftest import REFERENCE
from .test_api import client_for
from .test_integration import setup


def test_epg_metadata_and_recording_type():
    state = ReceiverState.parse(
        {
            "inStandby": False,
            "currservice_serviceref": "1:0:0:0:0:0:0:0:0:0:/media/hdd/movie.ts",
            "currservice_fulldescription": "Full description",
            "currservice_begin_timestamp": 100,
            "currservice_end_timestamp": "200",
        }
    )
    assert state.description == "Full description"
    assert state.programme_start == 100
    assert state.programme_end == 200
    assert state.recording_playback is True


def test_name_picons_and_local_hint_validation():
    paths = picon_candidates(REFERENCE, "Télé & Sport+", "https://external.test/icon.png")
    assert paths[-1] == "/picon/teleandsportplus.png"
    assert paths[0].endswith("1_0_1_6DD2_44D_1_C00000_0_0_0.png")
    assert picon_candidates("bad", None, "/picon/../secret.png") == []
    assert picon_candidates("bad", None, "/picon/known.png") == ["/picon/known.png"]
    assert picon_candidates(
        "4097:0:0:0:0:0:0:0:0:0:/media/20260912 - Sender HD - Film.ts", "Film"
    ) == ["/picon/senderhd.png"]


async def test_missing_reference_picon_falls_back_to_name():
    client, _ = client_for()
    with patch.object(
        client, "request", new_callable=AsyncMock, side_effect=[UnsupportedError(), b"image"]
    ) as request:
        assert await client.picon(REFERENCE, "Channel") == b"image"
        assert request.call_args.args[0] == "/picon/channel.png"


async def test_radio_bouquets_are_in_shared_catalog(hass, entry, receiver):
    previous = receiver[1].side_effect

    async def get(endpoint, **params):
        if endpoint == "bouquets" and params.get("stype") == "radio":
            return {"bouquets": [["1:7:2:radio", "Radio favorites"]]}
        return await previous(endpoint, **params)

    receiver[1].side_effect = get
    await setup(hass, entry)
    assert "Radio favorites" in entry.runtime_data.data.bouquets


async def test_deep_standby_option_is_actually_applied(hass, entry, receiver):
    hass.config_entries.async_update_entry(entry, options={"off_mode": "deep_standby"})
    await setup(hass, entry)
    player = EnigmaMediaPlayer(entry.runtime_data)
    await player.async_turn_off()
    assert receiver[2].call_args.kwargs == {"newstate": 1}


async def test_artwork_disabled(hass, entry, receiver):
    hass.config_entries.async_update_entry(entry, options={"artwork": "none"})
    await setup(hass, entry)
    player = EnigmaMediaPlayer(entry.runtime_data)
    assert player.media_image_url is None
    assert await player.async_get_media_image() == (None, None)


async def test_custom_bouquet_reference_survives_catalog_refresh(hass, entry, receiver):
    reference = '1:7:1:0:0:0:0:0:0:0:FROM BOUQUET "custom.tv" ORDER BY bouquet'
    hass.config_entries.async_update_entry(entry, options={"bouquet": reference})
    await setup(hass, entry)
    assert entry.runtime_data.data.bouquet == reference
    entry.runtime_data.invalidate_lists()
    await entry.runtime_data.async_refresh()
    assert entry.runtime_data.data.bouquet == reference
    assert any(
        call.args == ("getservices",) and call.kwargs == {"sRef": reference}
        for call in receiver[1].call_args_list
    )
