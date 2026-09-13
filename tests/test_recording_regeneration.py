# SPDX-License-Identifier: Apache-2.0
"""Options action, cache invalidation and real HA reload of thumbnail jobs."""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.enigma2_connect.const import DOMAIN
from custom_components.enigma2_connect.recording_images import (
    CONF_IMAGE_GENERATION,
    CONF_IMAGE_SOURCES,
    CONF_IMAGE_URL,
    RecordingImages,
    normalize_image,
    recording_thumbnail,
)

from .conftest import DATA
from .test_integration import setup
from .test_recording_images import MOVIE, picture
from .test_recording_preparation import finish


async def regenerate(hass, entry):
    menu = await hass.config_entries.options.async_init(entry.entry_id)
    assert menu["type"] == "menu"
    assert menu["menu_options"] == ["settings", "regenerate_images"]
    return await hass.config_entries.options.async_configure(
        menu["flow_id"], {"next_step_id": "regenerate_images"}
    )


async def test_regeneration_is_per_receiver_repeatable_and_survives_settings(hass, entry):
    hass.config_entries.async_update_entry(
        entry,
        options={CONF_IMAGE_SOURCES: ["custom"], CONF_IMAGE_URL: "https://covers.example/{title}"},
    )
    second = MockConfigEntry(
        domain=DOMAIN, title="Second", unique_id="second", data={**DATA, "host": "second.local"}
    )
    second.add_to_hass(hass)
    other_url = recording_thumbnail(second, MOVIE)
    with patch.object(hass.config_entries, "async_reload", new_callable=AsyncMock):
        for _ in range(2):
            before = dict(entry.options)
            url = recording_thumbnail(entry, MOVIE)
            result = await regenerate(hass, entry)
            assert result["type"] == "create_entry"
            assert recording_thumbnail(entry, MOVIE) != url
            assert {
                key: value for key, value in entry.options.items() if key != CONF_IMAGE_GENERATION
            } == {key: value for key, value in before.items() if key != CONF_IMAGE_GENERATION}
            assert second.options == {}
            assert recording_thumbnail(second, MOVIE) == other_url

        generation = entry.options[CONF_IMAGE_GENERATION]
        url = recording_thumbnail(entry, MOVIE)
        menu = await hass.config_entries.options.async_init(entry.entry_id)
        form = await hass.config_entries.options.async_configure(
            menu["flow_id"], {"next_step_id": "settings"}
        )
        defaults = form["data_schema"]({})
        assert CONF_IMAGE_GENERATION not in defaults
        result = await hass.config_entries.options.async_configure(
            form["flow_id"], {**defaults, "scan_interval": 42}
        )
        assert result["type"] == "create_entry"
        assert entry.options[CONF_IMAGE_GENERATION] == generation
        assert recording_thumbnail(entry, MOVIE) == url


async def test_disabled_sources_do_not_regenerate_or_reload(hass, entry):
    hass.config_entries.async_update_entry(entry, options={CONF_IMAGE_SOURCES: []})
    with patch.object(hass.config_entries, "async_reload", new_callable=AsyncMock) as reload:
        result = await regenerate(hass, entry)
        assert result["type"] == "abort"
        assert result["reason"] == "images_disabled"
        await hass.async_block_till_done()
        reload.assert_not_awaited()
        assert entry.options == {CONF_IMAGE_SOURCES: []}


@pytest.mark.parametrize("previous", ["cached", "running", "failed"])
async def test_regenerate_reloads_jobs_and_bypasses_old_cache(
    hass, entry, receiver, monkeypatch, previous
):
    receiver[0]["movielist"] = {"movies": [MOVIE]}
    monkeypatch.setattr("custom_components.enigma2_connect.recording_images.BACKGROUND_DELAY", 0.01)
    started = asyncio.Event()
    calls = 0

    async def generate(*args):
        nonlocal calls
        calls += 1
        if calls == 1:
            started.set()
            if previous == "running":
                await asyncio.Event().wait()
            if previous == "failed":
                return None
            return picture("blue")
        return picture("red")

    with patch.object(RecordingImages, "_from_source", side_effect=generate):
        await setup(hass, entry)
        old = entry.runtime_data.recording_images
        old_key = old._image_key(MOVIE)
        await asyncio.wait_for(started.wait(), 5)
        if previous != "running":
            await finish(old)
        assert calls == 1
        result = await regenerate(hass, entry)
        assert result["type"] == "create_entry"
        await hass.async_block_till_done()
        current = entry.runtime_data.recording_images
        assert old._closed and old._worker is None and not old._pending
        assert current is not old
        assert current._image_key(MOVIE) != old_key
        await finish(current)
        assert calls == 2
        content = await current.async_image(MOVIE)
        assert content == normalize_image(picture("red"))
        assert calls == 2
        assert await hass.config_entries.async_unload(entry.entry_id)
