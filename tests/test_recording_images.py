# SPDX-License-Identifier: Apache-2.0
"""Artwork options, provider fallback, cache, authentication and real frame seeking."""

import asyncio
import shutil
from dataclasses import replace
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import aiohttp
import pytest
from aiohttp import web
from PIL import Image

from custom_components.enigma2_connect.api import OpenWebifClient
from custom_components.enigma2_connect.media_player import EnigmaMediaPlayer
from custom_components.enigma2_connect.recording_images import (
    CONF_IMAGE_SOURCES,
    CONF_IMAGE_URL,
    CONF_OMDB_KEY,
    CONF_SNAPSHOT_MINUTES,
    CONF_TMDB_KEY,
    RecordingImages,
    custom_image_url,
    image_version,
    normalize_image,
    recording_thumbnail,
    validate_image_options,
)
from custom_components.enigma2_connect.recording_snapshot import extract_snapshot, snapshot_position

from .test_integration import setup

MOVIE = {
    "serviceref": "1:0:0:0:0:0:0:0:0:0:/media/hdd/movie/Film.ts",
    "filename": "/media/hdd/movie/Film.ts",
    "eventname": "Film & Friends / 100%",
    "servicename": "Example HD",
    "length": "90:00",
    "recordingtime": 100,
}


def picture(color="blue"):
    output = BytesIO()
    Image.new("RGB", (64, 36), color).save(output, "JPEG")
    return output.getvalue()


@pytest.mark.parametrize(
    ("length", "minutes", "expected"),
    [
        ("90:00", 10, 600),
        ("5:00", 10, 150),
        ("10:00", 10, 300),
        ("?:??", 10, 600),
        ("90:00", 2.5, 150),
        ("90:00", 0, 0),
    ],
)
def test_snapshot_position(length, minutes, expected):
    assert snapshot_position({"length": length}, minutes) == expected


def test_encoded_custom_url_and_invalid_templates():
    url = custom_image_url("https://covers.example/cover?title={title}&file={filename}", MOVIE)
    assert url.query["title"] == MOVIE["eventname"]
    assert url.query["file"] == "Film.ts"
    assert "/media/hdd" not in str(url)
    for value in (
        "file:///secret",
        "https://root:secret@example/image",
        "https://x/{title.__class__}",
        "https://x/{unknown}",
        "https://x/{title!r}",
        "https://x/{",
    ):
        with pytest.raises(ValueError):
            custom_image_url(value, MOVIE)


def test_provider_options_validation():
    assert validate_image_options({CONF_IMAGE_SOURCES: []}) == {}
    assert validate_image_options({CONF_IMAGE_SOURCES: ["snapshot"]}) == {}
    assert validate_image_options({CONF_IMAGE_SOURCES: ["tmdb", "omdb", "custom"]}) == {
        CONF_TMDB_KEY: "image_api_key_required",
        CONF_OMDB_KEY: "image_api_key_required",
        CONF_IMAGE_URL: "invalid_image_url",
    }


async def test_option_defaults_and_disable(hass, entry):
    with patch.object(hass.config_entries, "async_reload", new_callable=AsyncMock):
        flow = await hass.config_entries.options.async_init(entry.entry_id)
        flow = await hass.config_entries.options.async_configure(
            flow["flow_id"], {"next_step_id": "settings"}
        )
        defaults = flow["data_schema"]({})
        assert defaults[CONF_SNAPSHOT_MINUTES] == 10
        assert defaults[CONF_IMAGE_SOURCES] == ["snapshot"]
        result = await hass.config_entries.options.async_configure(
            flow["flow_id"],
            {
                **defaults,
                CONF_IMAGE_SOURCES: ["tmdb"],
            },
        )
        assert result["errors"] == {CONF_TMDB_KEY: "image_api_key_required"}
        result = await hass.config_entries.options.async_configure(
            flow["flow_id"],
            {
                **defaults,
                CONF_IMAGE_SOURCES: [],
                CONF_SNAPSHOT_MINUTES: 3.5,
            },
        )
        assert result["type"] == "create_entry"
        assert entry.options[CONF_IMAGE_SOURCES] == []
        assert entry.options[CONF_SNAPSHOT_MINUTES] == 3.5


async def test_cache_deduplication_and_settings_change(hass, entry, tmp_path):
    coordinator = SimpleNamespace(entry=entry, last_update_success=True)
    manager = RecordingImages(hass, coordinator)
    manager.cache = tmp_path
    content = picture()
    source = AsyncMock(return_value=content)
    with patch.object(manager, "_from_source", source):
        images = await asyncio.gather(*(manager.async_image(MOVIE) for _ in range(5)))
        assert all(image == images[0] for image in images)
        source.assert_awaited_once_with("snapshot", MOVIE, entry.options)
        manager2 = RecordingImages(hass, coordinator)
        manager2.cache = tmp_path
        with patch.object(manager2, "_from_source", AsyncMock(side_effect=AssertionError)):
            assert await manager2.async_image(MOVIE) == images[0]
        old_version = image_version(entry, MOVIE)
        hass.config_entries.async_update_entry(entry, options={CONF_SNAPSHOT_MINUTES: 3})
        assert image_version(entry, MOVIE) != old_version
        assert await manager.async_image(MOVIE)
        assert source.await_count == 2
        hass.config_entries.async_update_entry(entry, options={CONF_IMAGE_SOURCES: []})
        assert recording_thumbnail(entry, MOVIE) is None
        assert await manager.async_image(MOVIE) is None
        assert source.await_count == 2


async def test_fallback_priority_and_negative_cache(hass, entry, tmp_path):
    hass.config_entries.async_update_entry(
        entry, options={CONF_IMAGE_SOURCES: ["omdb", "snapshot", "tmdb", "custom"]}
    )
    manager = RecordingImages(hass, SimpleNamespace(entry=entry))
    manager.cache = tmp_path
    with patch.object(
        manager, "_from_source", AsyncMock(side_effect=[ValueError(), None, None, picture()])
    ) as source:
        assert await manager.async_image(MOVIE)
        assert [call.args[0] for call in source.await_args_list] == [
            "custom",
            "tmdb",
            "omdb",
            "snapshot",
        ]
    manager = RecordingImages(hass, SimpleNamespace(entry=entry))
    manager.cache = tmp_path / "missing"
    with patch.object(manager, "_from_source", AsyncMock(return_value=None)) as source:
        assert await manager.async_image(MOVIE) is None
        assert await manager.async_image(MOVIE) is None
        assert source.await_count == 4


async def test_movie_providers(hass, entry):
    manager = RecordingImages(hass, SimpleNamespace(entry=entry))
    with patch.object(
        manager,
        "_fetch",
        AsyncMock(
            side_effect=[
                {
                    "results": [
                        {"media_type": "person", "poster_path": "/wrong.jpg"},
                        {"media_type": "movie", "poster_path": "/cover.jpg"},
                    ],
                },
                picture(),
            ]
        ),
    ) as fetch:
        assert await manager._from_source("tmdb", MOVIE, {CONF_TMDB_KEY: "api-secret"})
        assert fetch.await_args_list[0].kwargs["params"]["query"] == MOVIE["eventname"]
        assert fetch.await_args_list[1].args == ("https://image.tmdb.org/t/p/w500/cover.jpg",)
    with patch.object(
        manager,
        "_fetch",
        AsyncMock(
            side_effect=[
                {
                    "Response": "True",
                    "Poster": "https://m.media-amazon.com/images/cover.jpg",
                },
                picture(),
            ]
        ),
    ) as fetch:
        assert await manager._from_source("omdb", MOVIE, {CONF_OMDB_KEY: "api-secret"})
        assert fetch.await_args_list[0].kwargs["params"]["t"] == MOVIE["eventname"]
    with patch.object(
        manager,
        "_fetch",
        AsyncMock(return_value={"Response": "True", "Poster": "http://localhost/secret"}),
    ) as fetch:
        assert await manager._from_source("omdb", MOVIE, {CONF_OMDB_KEY: "api-secret"}) is None
        assert fetch.await_count == 1


async def test_custom_download_limits_and_no_receiver_auth(
    hass, entry, aiohttp_server, socket_enabled, monkeypatch
):
    async def cover(request):
        assert "Authorization" not in request.headers
        assert request.query["title"] == MOVIE["eventname"]
        return web.Response(body=picture(), content_type="image/jpeg")

    app = web.Application()
    app.router.add_get("/cover", cover)
    server = await aiohttp_server(app)
    manager = RecordingImages(hass, SimpleNamespace(entry=entry))
    options = {CONF_IMAGE_URL: str(server.make_url("/cover")) + "?title={title}"}
    assert await manager._from_source("custom", MOVIE, options) == picture()
    monkeypatch.setattr("custom_components.enigma2_connect.recording_images.MAX_IMAGE_BYTES", 100)
    with pytest.raises(ValueError, match="too large"):
        await manager._from_source("custom", MOVIE, options)


async def test_pending_generation_stops_on_unload(hass, entry, tmp_path):
    manager = RecordingImages(hass, SimpleNamespace(entry=entry))
    manager.cache = tmp_path
    started = asyncio.Event()

    async def generate(*args):
        started.set()
        await asyncio.Event().wait()

    with patch.object(manager, "_from_source", side_effect=generate):
        request = asyncio.create_task(manager.async_image(MOVIE))
        await started.wait()
        await manager.async_close()
        with pytest.raises(asyncio.CancelledError):
            await request


def test_growing_recording_changes_thumbnail_position(entry):
    assert image_version(entry, {**MOVIE, "length": "5:00"}) != image_version(entry, MOVIE)
    assert image_version(entry, {**MOVIE, "length": "11:00"}) == image_version(entry, MOVIE)


async def test_authenticated_thumbnail_and_browse(hass, entry, receiver, hass_client):
    receiver[0]["movielist"] = {"directory": "/media/hdd/movie", "movies": [MOVIE]}
    await setup(hass, entry)
    player = EnigmaMediaPlayer(entry.runtime_data)
    player.hass = hass
    node = (await player.async_browse_media()).children[0]
    assert node.thumbnail == recording_thumbnail(entry, MOVIE)
    assert "secret" not in node.thumbnail and "/media/hdd" not in node.thumbnail
    client = await hass_client()
    with patch.object(
        entry.runtime_data.recording_images, "async_image", AsyncMock(return_value=picture())
    ) as image:
        unauthorized = await client.get(node.thumbnail, headers={"Authorization": "Bearer invalid"})
        assert unauthorized.status == 401
        image.assert_not_awaited()
        response = await client.get(node.thumbnail)
        assert response.status == 200
        assert response.content_type == "image/jpeg"
        image.assert_awaited_once()
        assert (await client.get(node.thumbnail + "wrong")).status == 404
        image.assert_awaited_once()
    receiver[2].assert_not_awaited()
    entry.runtime_data.async_set_updated_data(replace(entry.runtime_data.data, movies=[]))
    assert (await client.get(node.thumbnail)).status == 404


async def test_real_ffmpeg_seek_without_receiver_commands(
    hass, aiohttp_server, socket_enabled, tmp_path
):
    binary = await hass.async_add_executor_job(shutil.which, "ffmpeg")
    if not binary:
        pytest.skip("FFmpeg binary required for real frame extraction")
    video = tmp_path / "test.ts"
    process = await asyncio.create_subprocess_exec(
        binary,
        "-loglevel",
        "error",
        "-f",
        "lavfi",
        "-i",
        "color=red:s=64x36:r=25:d=660",
        "-vf",
        "drawbox=c=blue:t=fill:enable='gte(t,360)'",
        "-c:v",
        "mpeg2video",
        "-threads",
        "1",
        "-f",
        "mpegts",
        str(video),
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await process.communicate()
    assert process.returncode == 0, stderr.decode()
    requests = []

    async def file(request):
        assert request.query == {"action": "download", "file": MOVIE["filename"]}
        assert request.headers.get("Authorization", "").startswith("Basic ")
        requests.append(request.headers.get("Range"))
        return web.FileResponse(video)

    app = web.Application()
    app.router.add_get("/file", file)
    server = await aiohttp_server(app)
    async with aiohttp.ClientSession() as session:
        receiver = OpenWebifClient(session, server.host, server.port, "root", "receiver-secret")
        original = asyncio.create_subprocess_exec

        async def spawn(*args, **kwargs):
            assert "receiver-secret" not in str(args)
            assert "Authorization" not in str(args)
            return await original(*args, **kwargs)

        with patch("asyncio.create_subprocess_exec", side_effect=spawn):
            blue = await extract_snapshot(receiver, {**MOVIE, "length": "11:00"}, 10, binary)
            red = await extract_snapshot(receiver, MOVIE, 2, binary)
    assert blue and red
    for content, expected in ((blue, 2), (red, 0)):
        rgb = Image.open(BytesIO(content)).convert("RGB").getpixel((20, 20))
        assert rgb[expected] > 200 and sum(rgb) - rgb[expected] < 80
    assert any(value and value != "bytes=0-" for value in requests)


def test_image_normalization_rejects_html_and_bounds_size():
    with pytest.raises((ValueError, OSError)):
        normalize_image(b"<html>not an image</html>")
    content = BytesIO()
    Image.new("RGB", (1800, 900), "blue").save(content, "PNG")
    image = Image.open(BytesIO(normalize_image(content.getvalue())))
    assert image.format == "JPEG" and image.size == (640, 320)
