# SPDX-License-Identifier: Apache-2.0
"""Image cache pressure, provider failures and inaccessible media identifiers."""

import asyncio
from dataclasses import replace
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from aiohttp import web
from homeassistant.components import media_source
from homeassistant.components.media_player.errors import BrowseError
from homeassistant.setup import async_setup_component
from PIL import Image

from custom_components.enigma2_connect.channel_media import channel_from_identifier
from custom_components.enigma2_connect.const import DOMAIN
from custom_components.enigma2_connect.recording_images import (
    CONF_OMDB_KEY,
    CONF_TMDB_KEY,
    RecordingImages,
    normalize_image,
    recording_thumbnail,
)

from .test_integration import setup
from .test_recording_images import MOVIE, picture


@pytest.fixture
def images(hass, entry, tmp_path):
    manager = RecordingImages(
        hass, SimpleNamespace(entry=entry, last_update_success=True, client=object())
    )
    manager.cache = tmp_path
    return manager


def test_image_format_rejection_and_cache_io_failure(images):
    content = BytesIO()
    Image.new("RGB", (2, 2)).save(content, "GIF")
    with pytest.raises(ValueError):
        normalize_image(content.getvalue())
    with patch.object(Path, "glob", side_effect=OSError()):
        assert images._cache_index() == {}
    assert images._snapshot_ready(MOVIE)


async def test_image_request_pressure_and_negative_cache_limit(images, monkeypatch):
    monkeypatch.setattr("custom_components.enigma2_connect.recording_images.CACHE_LIMIT", 1)
    with patch.object(images, "_from_source", return_value=None):
        assert await images._generate("first", MOVIE) is None
        assert await images._generate("second", MOVIE) is None
    assert list(images._failed) == ["second"]
    images._pending = {str(i): asyncio.get_running_loop().create_future() for i in range(32)}
    assert await images.async_image(MOVIE) is None
    await images.async_close()


async def test_snapshot_source_uses_configured_binary(images):
    images.hass.data["ffmpeg"] = SimpleNamespace(binary="custom-ffmpeg")
    with patch(
        "custom_components.enigma2_connect.recording_images.extract_snapshot",
        return_value=picture(),
    ) as extract:
        assert await images._from_source("snapshot", MOVIE, {}) == picture()
        extract.assert_awaited_once_with(images.coordinator.client, MOVIE, 10, "custom-ffmpeg")
        images.coordinator.last_update_success = False
        assert await images._from_source("snapshot", MOVIE, {}) is None
        assert extract.await_count == 1


@pytest.mark.parametrize(
    "result",
    [
        None,
        {},
        {"results": "bad"},
        {"results": [None, {"media_type": "movie", "poster_path": "/../invalid"}]},
    ],
)
async def test_bad_tmdb_results_never_fetch_a_poster(images, result):
    with patch.object(images, "_fetch", return_value=result) as fetch:
        assert await images._from_source("tmdb", MOVIE, {CONF_TMDB_KEY: "key"}) is None
        fetch.assert_awaited_once()


@pytest.mark.parametrize(
    "result",
    [None, {"Response": "False"}, {"Response": "True", "Poster": "http://untrusted.local/x"}],
)
async def test_bad_omdb_results_never_fetch_a_poster(images, result):
    with patch.object(images, "_fetch", return_value=result) as fetch:
        assert await images._from_source("omdb", MOVIE, {CONF_OMDB_KEY: "key"}) is None
        fetch.assert_awaited_once()


async def test_empty_download_and_unsupported_url(images, aiohttp_server, socket_enabled):
    async def empty(request):
        return web.Response(status=204)

    app = web.Application()
    app.router.add_get("/empty", empty)
    server = await aiohttp_server(app)
    with pytest.raises(ValueError, match="did not return data"):
        await images._fetch(server.make_url("/empty"))
    with pytest.raises(ValueError, match="Unsupported image URL"):
        await images._fetch("file:///private/image")


async def test_media_browsing_rejects_bad_paths_and_returns_image_fallback(
    hass, entry, receiver, hass_client
):
    receiver[0]["movielist"] = {"movies": [{}, MOVIE]}
    await setup(hass, entry)
    assert await async_setup_component(hass, "media_source", {})
    client = await hass_client()
    url = recording_thumbnail(entry, MOVIE)
    with patch.object(entry.runtime_data.recording_images, "async_image", return_value=None):
        response = await client.get(url)
        assert response.status == 200
        assert response.content_type == "image/svg+xml"
        assert response.headers["Cache-Control"] == "no-store"
    assert (await client.get(url.replace(entry.entry_id, "missing"))).status == 404
    source = f"media-source://{DOMAIN}"
    for identifier in ("receiver/missing", "channels/missing", "invalid/path"):
        with pytest.raises(BrowseError):
            await media_source.async_browse_media(hass, f"{source}/{identifier}")
    folder = await media_source.async_browse_media(hass, f"{source}/receiver/{entry.entry_id}")
    assert folder.children
    with pytest.raises(media_source.Unresolvable):
        channel_from_identifier(hass, "not-a-channel")
    entry.runtime_data.data = replace(entry.runtime_data.data, movies=None)
    assert (await client.get(url)).status == 404
