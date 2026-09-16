# SPDX-License-Identifier: Apache-2.0
"""Public media-source browsing, multi-receiver identity, and playback routing."""

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.components import media_source
from homeassistant.exceptions import HomeAssistantError
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.enigma2_connect.const import DOMAIN
from custom_components.enigma2_connect.media_player import EnigmaMediaPlayer
from custom_components.enigma2_connect.media_source import (
    CONF_RECORDINGS_LAYOUT,
    EnigmaRecordingSource,
)

from .conftest import DATA
from .test_integration import setup

SOURCE = f"media-source://{DOMAIN}"
MOVIE_REF = "1:0:0:0:0:0:0:0:0:0:/media/hdd/movie/Series/Season 1/Film %: test.ts"


def test_source_name_supports_the_writable_ha_contract(hass):
    with patch(
        "custom_components.enigma2_connect.media_source.async_get_cached_translations",
        return_value={f"component.{DOMAIN}.common.recordings": "Aufnahmen"},
    ):
        source = EnigmaRecordingSource(hass)
        assert source.name == "Aufnahmen"
        source.name = "Custom library"
        assert source.name == "Custom library"
        source.name = None
        assert source.name == "Aufnahmen"


async def test_source_tile_grouped_merged_and_playback(hass, entry, receiver):
    second = MockConfigEntry(
        domain=DOMAIN,
        title="Second Receiver",
        unique_id="second",
        data={**DATA, "host": "second.local"},
    )
    second.add_to_hass(hass)
    receiver[0]["movielist"] = {
        "directory": "/media/hdd/movie/",
        "movies": [
            {
                "serviceref": MOVIE_REF,
                "eventname": "Film",
                "length": "90:00",
                "recordingtime": 1789323300,
                "servicename": "Example HD",
            }
        ],
    }
    await setup(hass, entry)
    assert await async_setup_component(hass, "media_source", {})
    await hass.async_block_till_done()
    sources = await media_source.async_browse_media(hass, None)
    assert any(
        child.title == "Enigma2 Connect" and child.media_content_id == SOURCE
        for child in sources.children
    )
    root = await media_source.async_browse_media(hass, SOURCE)
    assert [child.title for child in root.children] == ["Second Receiver", "Test Receiver"]
    own = next(child for child in root.children if child.title == entry.title)
    folder = await media_source.async_browse_media(hass, own.media_content_id)
    assert [child.title for child in folder.children] == ["Series"]
    folder = await media_source.async_browse_media(hass, folder.children[0].media_content_id)
    assert [child.title for child in folder.children] == ["Season 1"]
    folder = await media_source.async_browse_media(hass, folder.children[0].media_content_id)
    recording = folder.children[0]
    assert "Example HD" in recording.title and "1 h 30 min" in recording.title
    assert "/media/hdd" not in recording.media_content_id
    assert recording.can_play and not recording.can_expand
    player = EnigmaMediaPlayer(entry.runtime_data)
    player.hass = hass
    delegated = await player.async_browse_media("enigma2_directory", own.media_content_id)
    assert [child.title for child in delegated.children] == ["Series"]

    # Generic resolution never sends a receiver command or pretends to stream.
    with pytest.raises(media_source.Unresolvable, match="Test Receiver"):
        await media_source.async_resolve_media(hass, recording.media_content_id, None)
    receiver[2].assert_not_awaited()
    await hass.services.async_call(
        "media_player",
        "play_media",
        {
            "entity_id": "media_player.test_receiver",
            "media_content_type": recording.media_content_type,
            "media_content_id": recording.media_content_id,
        },
        blocking=True,
    )
    receiver[2].assert_awaited_once_with("zap", sRef=MOVIE_REF)
    receiver[2].reset_mock()
    with pytest.raises(HomeAssistantError, match="Test Receiver"):
        await hass.services.async_call(
            "media_player",
            "play_media",
            {
                "entity_id": "media_player.second_receiver",
                "media_content_type": recording.media_content_type,
                "media_content_id": recording.media_content_id,
            },
            blocking=True,
        )
    receiver[2].assert_not_awaited()

    hass.config_entries.async_update_entry(entry, options={CONF_RECORDINGS_LAYOUT: "merged"})
    root = await media_source.async_browse_media(hass, SOURCE)
    assert [child.title for child in root.children] == ["Series"]
    series = await media_source.async_browse_media(hass, root.children[0].media_content_id)
    merged = await media_source.async_browse_media(hass, series.children[0].media_content_id)
    assert len(merged.children) == 2
    assert len({child.media_content_id for child in merged.children}) == 2
    assert any("[Second Receiver]" in child.title for child in merged.children)
    assert any("[Test Receiver]" in child.title for child in merged.children)
    assert recording.media_content_id in {child.media_content_id for child in merged.children}

    # Playback IDs remain bound to a catalog item across layout changes and unload.
    assert await hass.config_entries.async_unload(entry.entry_id)
    with pytest.raises(media_source.Unresolvable):
        await media_source.async_resolve_media(hass, recording.media_content_id, None)
    receiver[2].assert_not_awaited()


async def test_options_layout_is_shared_and_preserves_other_options(hass, entry):
    second = MockConfigEntry(
        domain=DOMAIN,
        title="Second Receiver",
        unique_id="second",
        data={**DATA, "host": "second.local"},
        options={"scan_interval": 42},
    )
    second.add_to_hass(hass)
    with patch.object(hass.config_entries, "async_reload", new_callable=AsyncMock):
        flow = await hass.config_entries.options.async_init(entry.entry_id)
        flow = await hass.config_entries.options.async_configure(
            flow["flow_id"], {"next_step_id": "settings"}
        )
        result = await hass.config_entries.options.async_configure(
            flow["flow_id"],
            {
                CONF_RECORDINGS_LAYOUT: "merged",
                "scan_interval": 30,
                "artwork": "picon",
                "message_timeout": 10,
                "message_type": 1,
                "receiver_timezone": "Europe/Berlin",
            },
        )
        assert result["type"] == "create_entry"
        assert entry.options[CONF_RECORDINGS_LAYOUT] == "merged"
        assert second.options == {"scan_interval": 42, CONF_RECORDINGS_LAYOUT: "merged"}
        flow = await hass.config_entries.options.async_init(second.entry_id)
        flow = await hass.config_entries.options.async_configure(
            flow["flow_id"], {"next_step_id": "settings"}
        )
        assert flow["data_schema"]({"scan_interval": 42})[CONF_RECORDINGS_LAYOUT] == "merged"
        await hass.config_entries.options.async_configure(
            flow["flow_id"],
            {
                CONF_RECORDINGS_LAYOUT: "receivers",
                "scan_interval": 42,
                "artwork": "picon",
                "message_timeout": 10,
                "message_type": 1,
                "receiver_timezone": "Europe/Berlin",
            },
        )
        assert entry.options[CONF_RECORDINGS_LAYOUT] == "receivers"
        assert entry.options["scan_interval"] == 30


async def test_empty_source_and_invalid_identifiers(hass, entry, receiver):
    await setup(hass, entry)
    assert await async_setup_component(hass, "media_source", {})
    await hass.async_block_till_done()
    root = await media_source.async_browse_media(hass, SOURCE)
    folder = await media_source.async_browse_media(hass, root.children[0].media_content_id)
    assert folder.children == []
    for suffix in (
        "",
        "recording/missing/invalid",
        f"recording/{entry.entry_id}/invalid",
        "merged",
    ):
        with pytest.raises(media_source.Unresolvable):
            await media_source.async_resolve_media(hass, f"{SOURCE}/{suffix}", None)
    receiver[2].assert_not_awaited()


async def test_new_receiver_inherits_shared_layout(hass, receiver):
    existing = MockConfigEntry(
        domain=DOMAIN,
        title="Existing Receiver",
        unique_id="existing",
        data={**DATA, "host": "existing.local"},
        options={CONF_RECORDINGS_LAYOUT: "merged"},
    )
    existing.add_to_hass(hass)
    with patch("custom_components.enigma2_connect.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
        result = await hass.config_entries.flow.async_configure(result["flow_id"], DATA)
        assert result["type"] == "create_entry"
        assert result["result"].options[CONF_RECORDINGS_LAYOUT] == "merged"
