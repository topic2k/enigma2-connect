# SPDX-License-Identifier: Apache-2.0
"""External playback routing, capability access, lifecycle and real HLS media."""

import asyncio
import json
import shutil
from dataclasses import replace
from pathlib import Path
from time import monotonic
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest
from aiohttp import web
from homeassistant.components import media_source
from homeassistant.components.media_source import PlayMedia, Unresolvable
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.setup import async_setup_component
from yarl import URL

from custom_components.enigma2_connect.api import OpenWebifClient
from custom_components.enigma2_connect.channel_media import channel_identifier
from custom_components.enigma2_connect.const import DOMAIN
from custom_components.enigma2_connect.media_source import recording_identifier
from custom_components.enigma2_connect.media_stream import HLS_MIME, MediaStreamView
from custom_components.enigma2_connect.media_stream import StreamSession as MediaStream

from .conftest import REFERENCE
from .test_integration import setup

MOVIE = {"serviceref": "1:0:0:0:0:0:0:0:0:0:/media/hdd/movie/Film %: test.ts", "eventname": "Film"}
SOURCE = f"media-source://{DOMAIN}/"


@pytest.fixture
async def configured(hass, entry, receiver):
    hass.config_entries.async_update_entry(
        entry,
        options={
            "external_playback": True,
            "media_show_channels": True,
            "stream_mode": "compatible",
        },
    )
    receiver[0]["movielist"] = {"movies": [MOVIE]}
    await setup(hass, entry)
    assert await async_setup_component(hass, "media_source", {})
    session = MediaStream(hass, entry.runtime_data)
    entry.runtime_data.media_stream.sessions[session] = (URL("http://receiver.local/testing"), True)
    # Existing stream tests exercise the bounded fallback for receivers without ranges.
    with patch(
        "custom_components.enigma2_connect.media_stream.RecordingVOD.prepare",
        side_effect=ValueError("Recording byte ranges unavailable"),
    ):
        yield session


@pytest.fixture
def spawn(hass):
    processes = []

    async def create(*args, **kwargs):
        assert "secret" not in str(args) and "Authorization" not in str(args)
        assert "receiver.local" not in str(args)
        process = MagicMock(returncode=None, wait=AsyncMock(return_value=0))
        processes.append((process, args))
        await hass.async_add_executor_job(
            Path(args[-1]).write_text, "#EXTM3U\nsegment00000000.ts\n"
        )
        await hass.async_add_executor_job(
            Path(args[-1]).with_name("segment00000000.ts").write_bytes, b"video"
        )
        return process

    with patch("asyncio.create_subprocess_exec", side_effect=create):
        yield processes


async def test_options_external_defaults_and_save(hass, entry, receiver):
    await setup(hass, entry)
    with patch.object(hass.config_entries, "async_reload", new_callable=AsyncMock):
        flow = await hass.config_entries.options.async_init(entry.entry_id)
        form = await hass.config_entries.options.async_configure(
            flow["flow_id"], {"next_step_id": "settings"}
        )
        values = form["data_schema"]({})
        assert values["external_playback"] is False
        assert values["stream_port"] == 8001
        assert values["stream_mode"] == "auto"
        assert values["stream_limit"] == 5
        assert values["stream_https"] is False
        result = await hass.config_entries.options.async_configure(
            flow["flow_id"],
            {**values, "external_playback": True, "stream_port": 8443, "stream_https": True},
        )
        assert result["type"] == "create_entry"
        assert entry.options["external_playback"] and entry.options["stream_https"]
        assert entry.options["stream_port"] == 8443


async def test_resolve_live_and_recording_without_zapping(hass, entry, receiver, configured):
    movie_id = SOURCE + recording_identifier(entry, MOVIE)
    result = PlayMedia("/local/hls.m3u8", HLS_MIME)
    with patch.object(
        entry.runtime_data.media_stream, "async_play", AsyncMock(return_value=result)
    ) as play:
        assert await media_source.async_resolve_media(hass, movie_id, None) == result
        url = play.call_args.args[0]
        assert url.host == "receiver.local" and url.path == "/file"
        assert url.query == {"action": "download", "file": MOVIE["serviceref"].split(":", 10)[-1]}
        assert play.call_args.kwargs == {"recording": True}
        channel = next(iter(entry.runtime_data.data.media_channels.values()))
        channel_id = SOURCE + channel_identifier(entry, channel)
        await media_source.async_resolve_media(hass, channel_id, "media_player.cast")
        assert play.call_args.args[0] == URL("http://receiver.local:8001/" + REFERENCE)
        assert play.call_args.kwargs == {"recording": False}
        # The independently configured HTTPS stream port is honored.
        hass.config_entries.async_update_entry(
            entry, options={**entry.options, "stream_https": True, "stream_port": 8443}
        )
        await media_source.async_resolve_media(hass, channel_id, None)
        assert play.call_args.args[0] == URL("https://receiver.local:8443/" + REFERENCE)
    receiver[2].assert_not_awaited()


@pytest.mark.parametrize(
    "path", ["relative.ts", "/media/movie/../other.ts", "/media/movie/film.mkv"]
)
async def test_reject_unsupported_recording_path(hass, entry, configured, path):
    movie = {**MOVIE, "filename": path}
    entry.runtime_data.async_set_updated_data(replace(entry.runtime_data.data, movies=[movie]))
    with pytest.raises(Unresolvable):
        await media_source.async_resolve_media(
            hass, SOURCE + recording_identifier(entry, movie), None
        )
    assert configured.process is None


async def test_session_restart_token_rotation_and_pool_unload(
    hass, entry, configured, spawn, socket_enabled, hass_client_no_auth
):
    client = await hass_client_no_auth()
    playback = await configured.async_play(URL("http://receiver.local/file"), recording=True)
    # HA's media dialog matches this exact value before loading its HLS player.
    assert playback.mime_type == "application/x-mpegURL"
    url = playback.url
    playlist = await client.get(url)
    assert playlist.status == 200
    assert playlist.headers["Content-Type"].split(";")[0] == "application/x-mpegURL"
    response = await client.get(url.replace("index.m3u8", "segment00000000.ts"))
    assert response.content_type == "video/mp2t"
    assert await response.read() == b"video"
    assert response.headers["Cache-Control"] == "no-store"
    view = MediaStreamView(hass)
    for filename, token in [
        ("../secret", configured.token),
        ("index.m3u8.tmp", configured.token),
        ("segment00000001.ts", configured.token),
        ("index.m3u8", "wrong"),
    ]:
        with pytest.raises(web.HTTPNotFound):
            await view.get(None, entry.entry_id, token, filename)
    for entry_id in ("missing",):
        with pytest.raises(web.HTTPNotFound):
            await view.get(None, entry_id, configured.token, "index.m3u8")
    old_dir = configured.directory.name
    old_process = configured.process
    next_url = (
        await configured.async_play(URL("http://receiver.local:8001/channel"), recording=False)
    ).url
    assert next_url != url
    assert (await client.get(url)).status == 404
    old_process.kill.assert_called_once()
    assert not await hass.async_add_executor_job(Path(old_dir).exists)
    assert "-re" in spawn[0][1] and "-re" not in spawn[1][1]
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert configured.closed and configured.process is None and not configured.token
    assert (await client.get(next_url)).status == 404
    with pytest.raises(Unresolvable):
        await configured.async_play(URL("http://receiver.local"), recording=True)


async def test_expiry_missing_directory_and_disabled(
    hass, entry, configured, spawn, socket_enabled
):
    await configured.async_play(URL("http://receiver.local/file"), recording=True)
    view = MediaStreamView(hass)
    now = monotonic()
    for touched, started in [(now - 121, now), (now, now - 21601)]:
        configured.touched, configured.started = touched, started
        with pytest.raises(web.HTTPNotFound):
            await view.get(None, entry.entry_id, configured.token, "index.m3u8")
    configured.touched = configured.started = now
    directory = configured.directory
    configured.directory = None
    with pytest.raises(web.HTTPNotFound):
        await view.get(None, entry.entry_id, configured.token, "index.m3u8")
    configured.directory = directory
    hass.config_entries.async_update_entry(entry, options={})
    with pytest.raises(Unresolvable):
        await configured.async_play(URL("http://receiver.local"), recording=True)
    with pytest.raises(web.HTTPNotFound):
        await view.get(None, entry.entry_id, configured.token, "index.m3u8")
    await configured.async_close()


@pytest.mark.parametrize(
    "failure", [OSError("binary missing"), TimeoutError(), asyncio.CancelledError()]
)
async def test_start_failure_cleans_up(hass, configured, failure):
    with patch.object(configured, "_start", side_effect=failure):
        with pytest.raises(
            asyncio.CancelledError if isinstance(failure, asyncio.CancelledError) else Unresolvable
        ):
            await configured.async_play(URL("http://receiver.local/file"), recording=True)
    assert not configured.token and configured.process is None


async def test_process_exits_before_playlist(hass, configured, socket_enabled):
    process = MagicMock(returncode=1, wait=AsyncMock(return_value=1))
    with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=process)):
        with pytest.raises(Unresolvable):
            await configured.async_play(URL("http://receiver.local/file"), recording=True)
    assert configured.directory is None and configured.runner is None
    process.kill.assert_not_called()


async def test_watch_idle_failure_and_shutdown(hass, configured, spawn, socket_enabled):
    await configured.async_play(URL("http://receiver.local/file"), recording=True)
    configured.watcher.cancel()
    await asyncio.gather(configured.watcher, return_exceptions=True)
    configured.watcher = None
    with patch(
        "custom_components.enigma2_connect.media_stream.asyncio.sleep", new_callable=AsyncMock
    ):
        with patch.object(configured, "expired", side_effect=[False, True]):
            await configured._watch()
    assert configured.process is None
    await configured.async_play(URL("http://receiver.local/file"), recording=True)
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()
    assert configured.closed and not configured.token


@pytest.mark.parametrize("status", [200, 206, 302, 401, 404, 500])
async def test_relay_headers_errors_and_ranges(
    hass, configured, aiohttp_server, socket_enabled, status
):
    seen = []

    async def upstream(request):
        seen.append(request)
        assert request.headers["Authorization"].startswith("Basic ")
        return web.Response(
            status=status, body=b"transport", headers={"Location": "http://must-not-follow.invalid"}
        )

    app = web.Application()
    app.router.add_get("/source", upstream)
    server = await aiohttp_server(app)
    relay_app = web.Application()
    relay_app.router.add_get("/relay", configured._relay_handler(server.make_url("/source")))
    relay = await aiohttp_server(relay_app)
    async with aiohttp.ClientSession() as client:
        response = await client.get(relay.make_url("/relay"), headers={"Range": "bytes=0-"})
        assert response.status == (status if status in (200, 206) else 502)
        assert len(seen) == 1 and seen[0].headers["Range"] == "bytes=0-"
        assert (
            await client.get(relay.make_url("/relay"), headers={"Range": "bytes=0-1,4-5"})
        ).status == 400
        if status == 200:
            head = await client.head(relay.make_url("/relay"))
            assert head.status == 200 and await head.read() == b""
        with patch.object(
            configured.coordinator.client.session,
            "request",
            side_effect=aiohttp.ClientConnectionError(),
        ):
            assert (await client.get(relay.make_url("/relay"))).status == 502


@pytest.mark.parametrize(
    ("video_codec", "audio_codec", "processing"),
    [
        ("mpeg2video", "mp2", "encode_video+encode_audio"),
        ("libx264", "aac", "copy_video+copy_audio"),
        ("libx264", "mp2", "copy_video+encode_audio"),
    ],
)
async def test_real_ffmpeg_hls_transcodes_video_audio(
    hass, entry, aiohttp_server, socket_enabled, tmp_path, video_codec, audio_codec, processing
):
    binary = await hass.async_add_executor_job(shutil.which, "ffmpeg")
    if not binary:
        pytest.skip("FFmpeg required for real HLS test")
    video = tmp_path / "source.ts"
    generate = await asyncio.create_subprocess_exec(
        binary,
        "-loglevel",
        "error",
        "-f",
        "lavfi",
        "-i",
        "testsrc2=s=160x90:r=25",
        "-f",
        "lavfi",
        "-i",
        "sine=frequency=440:sample_rate=48000",
        "-t",
        "6",
        "-c:v",
        video_codec,
        "-g",
        "50",
        "-c:a",
        audio_codec,
        "-threads",
        "1",
        "-f",
        "mpegts",
        str(video),
    )
    assert await generate.wait() == 0
    requests = []

    async def upstream(request):
        assert request.headers.get("Authorization", "").startswith("Basic ")
        requests.append(request.path)
        # This receiver deliberately ignores Range: test the real linear fallback.
        return web.Response(body=await hass.async_add_executor_job(video.read_bytes))

    app = web.Application()
    app.router.add_get("/file", upstream)
    server = await aiohttp_server(app)
    hass.config_entries.async_update_entry(entry, options={"external_playback": True})
    async with aiohttp.ClientSession() as session:
        coordinator = SimpleNamespace(
            entry=entry, client=OpenWebifClient(session, server.host, server.port, "root", "secret")
        )
        stream = MediaStream(hass, coordinator)
        try:
            result = await stream.async_play(server.make_url("/file"), recording=True)
            assert result.mime_type == HLS_MIME and "secret" not in result.url
            assert stream.processing == processing
            playlist = Path(stream.directory.name) / "index.m3u8"
            content = await hass.async_add_executor_job(playlist.read_text)
            assert "#EXTM3U" in content and "segment00000000.ts" in content
            assert str(server.port) not in content and "secret" not in content
            segment = playlist.with_name("segment00000000.ts")
            # Decode actual HLS output, independently of mocked HA routing tests.
            probe = await asyncio.create_subprocess_exec(
                "ffprobe",
                "-v",
                "error",
                "-show_streams",
                "-of",
                "json",
                str(segment),
                stdout=asyncio.subprocess.PIPE,
            )
            output, _ = await probe.communicate()
            assert probe.returncode == 0
            streams = json.loads(output)["streams"]
            assert {item["codec_name"] for item in streams} == {"h264", "aac"}
            out_video = next(item for item in streams if item["codec_type"] == "video")
            assert out_video["height"] <= 720
            if video_codec == "libx264":
                assert out_video["width"] == 160 and out_video["height"] == 90
            decode = await asyncio.create_subprocess_exec(
                binary,
                "-v",
                "error",
                "-i",
                str(segment),
                "-f",
                "null",
                "-",
                stderr=asyncio.subprocess.PIPE,
            )
            _, errors = await decode.communicate()
            assert decode.returncode == 0 and not errors
            assert requests
        finally:
            await stream.async_close()
        assert stream.process is None and stream.directory is None


async def test_start_timeout_after_allocating_resources(hass, configured, socket_enabled):
    process = MagicMock(returncode=None, wait=AsyncMock(return_value=0))
    with (
        patch("asyncio.create_subprocess_exec", AsyncMock(return_value=process)),
        patch("custom_components.enigma2_connect.media_stream.START_TIMEOUT", 0.5),
    ):
        with pytest.raises(Unresolvable):
            await configured.async_play(URL("http://receiver.local/file"), recording=True)
    assert configured.directory is None and configured.runner is None and not configured.token
    process.kill.assert_called_once()


async def test_unicode_tokens_and_failed_process_watch(
    hass, entry, configured, spawn, socket_enabled
):
    hass.data["ffmpeg"] = SimpleNamespace(binary="ffmpeg")
    await configured.async_play(URL("http://receiver.local/file"), recording=True)
    with pytest.raises(web.HTTPNotFound):
        await MediaStreamView(hass).get(None, entry.entry_id, "ü-invalid", "index.m3u8")
    configured.watcher.cancel()
    await asyncio.gather(configured.watcher, return_exceptions=True)
    configured.watcher = None
    configured.process.returncode = 1
    with patch(
        "custom_components.enigma2_connect.media_stream.asyncio.sleep", new_callable=AsyncMock
    ):
        await configured._watch()
    assert configured.process is None and configured.directory is None
    with pytest.raises(web.HTTPNotFound):
        await MediaStreamView(hass).get(None, entry.entry_id, "old", "index.m3u8")


async def test_cast_cors_and_head(
    hass, entry, configured, spawn, socket_enabled, hass_client_no_auth
):
    client = await hass_client_no_auth()
    url = (await configured.async_play(URL("http://receiver.local/file"), recording=True)).url
    origin = "https://www.gstatic.com"
    for path in (url, url.replace("index.m3u8", "segment00000000.ts")):
        response = await client.get(path, headers={"Origin": origin})
        assert response.status == 200
        assert response.headers["Access-Control-Allow-Origin"] == origin
        head = await client.head(path, headers={"Origin": origin})
        assert head.status == 200 and await head.read() == b""
        assert head.headers["Access-Control-Allow-Origin"] == origin
    assert (
        await client.get(url.replace(configured.token, "invalid"), headers={"Origin": origin})
    ).status == 404
