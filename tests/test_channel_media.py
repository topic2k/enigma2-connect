# SPDX-License-Identifier: Apache-2.0
"""Optional media-browser channels, independent bouquets and protected picons."""

from dataclasses import replace
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.components import media_source
from homeassistant.components.media_player.errors import BrowseError
from homeassistant.exceptions import HomeAssistantError
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.enigma2_connect.api import UnsupportedError
from custom_components.enigma2_connect.channel_media import CONF_CHANNEL_BOUQUET, CONF_SHOW_CHANNELS
from custom_components.enigma2_connect.const import DOMAIN
from custom_components.enigma2_connect.media_player import EnigmaMediaPlayer
from custom_components.enigma2_connect.media_source import CONF_RECORDINGS_LAYOUT

from .conftest import BOUQUET, DATA, REFERENCE
from .test_integration import setup
from .test_recording_images import picture

SOURCE = f"media-source://{DOMAIN}"
OTHER_BOUQUET = '1:7:1:0:0:0:0:0:0:0:FROM BOUQUET "other.tv" ORDER BY bouquet'
OTHER_CHANNEL = "1:0:1:2222:44D:1:C00000:0:0:0:"


async def test_disabled_default_and_configurable_bouquet(hass, entry, receiver):
    await setup(hass, entry)
    player = EnigmaMediaPlayer(entry.runtime_data)
    player.hass = hass
    assert (await player.async_browse_media()).children == []
    assert entry.runtime_data.data.media_channels is None
    get_services = [call for call in receiver[1].await_args_list if call.args[0] == "getservices"]
    assert len(get_services) == 1
    with patch.object(hass.config_entries, "async_reload", new_callable=AsyncMock):
        flow = await hass.config_entries.options.async_init(entry.entry_id)
        flow = await hass.config_entries.options.async_configure(
            flow["flow_id"], {"next_step_id": "settings"}
        )
        defaults = flow["data_schema"]({})
        assert defaults[CONF_SHOW_CHANNELS] is False
        assert defaults[CONF_CHANNEL_BOUQUET] == ""
        selector = next(
            value
            for key, value in flow["data_schema"].schema.items()
            if key.schema == CONF_CHANNEL_BOUQUET
        )
        assert {"value": BOUQUET, "label": "Favorites"} in selector.config["options"]
        assert selector.config["custom_value"] is False
        saved = await hass.config_entries.options.async_configure(
            flow["flow_id"],
            {**defaults, CONF_SHOW_CHANNELS: True, CONF_CHANNEL_BOUQUET: BOUQUET},
        )
        assert saved["type"] == "create_entry"
        assert entry.options[CONF_CHANNEL_BOUQUET] == BOUQUET


@pytest.mark.parametrize("reference", [BOUQUET, OTHER_BOUQUET])
async def test_bouquet_labels_survive_reopening_and_missing_catalog(
    hass, entry, receiver, reference
):
    hass.config_entries.async_update_entry(
        entry, options={CONF_CHANNEL_BOUQUET: reference, "bouquet": reference}
    )
    await setup(hass, entry)
    with patch.object(hass.config_entries, "async_reload", new_callable=AsyncMock):
        for catalog_available in (True, False):
            if not catalog_available:
                entry.runtime_data.async_set_updated_data(
                    replace(entry.runtime_data.data, bouquets={})
                )
            flow = await hass.config_entries.options.async_init(entry.entry_id)
            flow = await hass.config_entries.options.async_configure(
                flow["flow_id"], {"next_step_id": "settings"}
            )
            defaults = flow["data_schema"]({})
            for field in (CONF_CHANNEL_BOUQUET, "bouquet"):
                select = next(
                    value
                    for key, value in flow["data_schema"].schema.items()
                    if key.schema == field
                )
                assert defaults[field] == reference
                assert select.config["custom_value"] is False
                label = next(
                    choice["label"]
                    for choice in select.config["options"]
                    if choice["value"] == reference
                )
                assert label == (
                    "Favorites"
                    if catalog_available and reference == BOUQUET
                    else "userbouquet.favourites.tv"
                    if reference == BOUQUET
                    else "other.tv"
                )
                assert select("") == ""
            saved = await hass.config_entries.options.async_configure(flow["flow_id"], defaults)
            assert saved["type"] == "create_entry"
            assert entry.options[CONF_CHANNEL_BOUQUET] == reference
            assert entry.options["bouquet"] == reference


async def test_dedicated_bouquet_does_not_change_source_and_channels_tune(hass, entry, receiver):
    hass.config_entries.async_update_entry(
        entry, options={CONF_SHOW_CHANNELS: True, CONF_CHANNEL_BOUQUET: OTHER_BOUQUET}
    )
    original = receiver[1].side_effect

    async def get(endpoint, **params):
        if endpoint == "getservices" and params.get("sRef") == OTHER_BOUQUET:
            return {
                "services": [
                    {"servicereference": OTHER_CHANNEL, "servicename": "Extra"},
                    {"servicereference": "1:64:0:0:0:0:0:0:0:0:", "servicename": "Marker"},
                ]
            }
        return await original(endpoint, **params)

    receiver[1].side_effect = get
    await setup(hass, entry)
    player = EnigmaMediaPlayer(entry.runtime_data)
    player.hass = hass
    assert player.source_list == ["Channel"]
    root = await player.async_browse_media()
    assert [child.title for child in root.children] == ["Channels"]
    # Native media browsing also works without loading the generic Media integration.
    channels = await player.async_browse_media(
        "enigma2_directory", root.children[0].media_content_id
    )
    assert [child.title for child in channels.children] == ["Extra"]
    node = channels.children[0]
    assert node.thumbnail.startswith("/api/enigma2_connect/channel_picon/")
    assert "secret" not in node.thumbnail and "receiver.local" not in node.thumbnail
    await hass.services.async_call(
        "media_player",
        "play_media",
        {
            "entity_id": "media_player.test_receiver",
            "media_content_type": node.media_content_type,
            "media_content_id": node.media_content_id,
        },
        blocking=True,
    )
    receiver[2].assert_awaited_once_with("zap", sRef=OTHER_CHANNEL)
    await entry.runtime_data.select_bouquet(BOUQUET)
    assert list(entry.runtime_data.data.media_channels) == ["Extra"]
    # Losing only the optional media bouquet must preserve the ordinary source list.

    async def unavailable(endpoint, **params):
        if endpoint == "getservices" and params.get("sRef") == OTHER_BOUQUET:
            raise UnsupportedError("No bouquet")
        return await original(endpoint, **params)

    receiver[1].side_effect = unavailable
    entry.runtime_data.invalidate_lists()
    await entry.runtime_data.async_refresh()
    assert entry.runtime_data.last_update_success and player.source_list == ["Channel"]
    with pytest.raises(BrowseError):
        await player.async_browse_media("enigma2_directory", root.children[0].media_content_id)


async def test_empty_bouquet_follows_source_selection(hass, entry, receiver):
    hass.config_entries.async_update_entry(entry, options={CONF_SHOW_CHANNELS: True})
    await setup(hass, entry)
    assert entry.runtime_data.data.media_channels == entry.runtime_data.data.channels
    receiver[0]["getservices"] = {
        "services": [{"servicereference": OTHER_CHANNEL, "servicename": "Other"}]
    }
    await entry.runtime_data.select_bouquet(OTHER_BOUQUET)
    assert list(entry.runtime_data.data.media_channels) == ["Other"]


@pytest.mark.parametrize("missing", [False, True])
async def test_picon_auth_cache_missing_and_disabled(hass, entry, receiver, hass_client, missing):
    hass.config_entries.async_update_entry(entry, options={CONF_SHOW_CHANNELS: True})
    hass.config.language = "de"
    await setup(hass, entry)
    player = EnigmaMediaPlayer(entry.runtime_data)
    player.hass = hass
    root = await player.async_browse_media()
    assert root.children[0].title == "Sender"
    channels = await player.async_browse_media(
        "enigma2_directory", root.children[0].media_content_id
    )
    node = channels.children[0]
    client = await hass_client()
    with patch.object(
        entry.runtime_data.client,
        "picon",
        AsyncMock(
            side_effect=UnsupportedError("Missing") if missing else None, return_value=picture()
        ),
    ) as picon:
        assert (
            await client.get(node.thumbnail, headers={"Authorization": "Bearer invalid"})
        ).status == 401
        picon.assert_not_awaited()
        for _ in range(2):
            response = await client.get(node.thumbnail)
            assert response.status == 200
            assert response.content_type == ("image/svg+xml" if missing else "image/jpeg")
        picon.assert_awaited_once_with(REFERENCE, "Channel")
        hass.config_entries.async_update_entry(entry, options={CONF_SHOW_CHANNELS: False})
        assert (await client.get(node.thumbnail)).status == 404
        with pytest.raises(HomeAssistantError):
            await player.async_play_media(node.media_content_type, node.media_content_id)
        picon.assert_awaited_once()
    receiver[2].assert_not_awaited()


async def test_shared_tile_receiver_ownership_and_merged_channel_folders(hass, entry, receiver):
    hass.config_entries.async_update_entry(entry, options={CONF_SHOW_CHANNELS: True})
    second = MockConfigEntry(
        domain=DOMAIN,
        title="Second Receiver",
        unique_id="second",
        data={**DATA, "host": "second.local"},
        options={CONF_SHOW_CHANNELS: True},
    )
    second.add_to_hass(hass)
    await setup(hass, entry)
    assert await async_setup_component(hass, "media_source", {})
    await hass.async_block_till_done()
    root = await media_source.async_browse_media(hass, SOURCE)
    own = next(child for child in root.children if child.title == entry.title)
    own_root = await media_source.async_browse_media(hass, own.media_content_id)
    channels = await media_source.async_browse_media(hass, own_root.children[0].media_content_id)
    node = channels.children[0]
    with pytest.raises(media_source.Unresolvable, match="Test Receiver"):
        await media_source.async_resolve_media(hass, node.media_content_id, None)
    other = EnigmaMediaPlayer(second.runtime_data)
    other.hass = hass
    with pytest.raises(HomeAssistantError, match="Test Receiver"):
        await other.async_play_media(node.media_content_type, node.media_content_id)
    receiver[2].assert_not_awaited()
    hass.config_entries.async_update_entry(
        entry, options={**entry.options, CONF_RECORDINGS_LAYOUT: "merged"}
    )
    merged = await media_source.async_browse_media(hass, SOURCE)
    assert merged.children[0].title == "Channels"
    receivers = await media_source.async_browse_media(hass, merged.children[0].media_content_id)
    assert [child.title for child in receivers.children] == ["Second Receiver", "Test Receiver"]
    all_nodes = [
        (await media_source.async_browse_media(hass, child.media_content_id)).children[0]
        for child in receivers.children
    ]
    assert len({child.media_content_id for child in all_nodes}) == 2
    assert len({child.thumbnail for child in all_nodes}) == 2
    entry.runtime_data.async_set_updated_data(replace(entry.runtime_data.data, media_channels={}))
    owner = EnigmaMediaPlayer(entry.runtime_data)
    owner.hass = hass
    with pytest.raises(HomeAssistantError):
        await owner.async_play_media(node.media_content_type, node.media_content_id)
