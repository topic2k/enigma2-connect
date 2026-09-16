# SPDX-License-Identifier: Apache-2.0
"""Seekable recording timelines, bounded resources and actual timestamp/content tests."""

import asyncio
import json
import math
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest
from aiohttp import web
from yarl import URL

from custom_components.enigma2_connect.api import OpenWebifClient
from custom_components.enigma2_connect.media_stream import StreamSession
from custom_components.enigma2_connect.stream_vod import RecordingVOD

from . import test_media_stream as fixtures
from . import test_stream_pool as pool_fixtures

configured = fixtures.configured
pool = pool_fixtures.pool


@pytest.fixture
def vod(hass):
    return RecordingVOD(hass, MagicMock(), "ffmpeg", "http://127.0.0.1/private", "session-test")


async def test_fixed_timeline_seek_order_and_bounded_cache(vod):
    vod.duration, vod.size = 80.5, 1000
    calls = []

    async def render(binary, args, limit):
        position = str(float(args[args.index("-output_ts_offset") + 1]) - 1)
        assert float(args[args.index("-ss") + 1]) == pytest.approx(max(0, float(position) - 10))
        calls.append(position)
        return position.encode()

    with (
        patch.object(vod, "_size", AsyncMock(return_value=1000)),
        patch.object(vod, "_run", side_effect=render),
    ):
        playlist = (await vod.read("index.m3u8")).decode()
        assert "#EXT-X-PLAYLIST-TYPE:VOD" in playlist and "#EXT-X-ENDLIST" in playlist
        assert "#EXTINF:3.700000," in playlist
        assert sum(
            float(line.split(":")[1].split(",")[0])
            for line in playlist.splitlines()
            if line.startswith("#EXTINF")
        ) == pytest.approx(80.5)
        assert "http" not in playlist and "private" not in playlist
        assert await vod.read("segment00000010.ts") == b"64.0"
        assert await vod.read("segment00000000.ts") == b"0.0"
        assert await vod.read("segment00000010.ts") == b"64.0"
        assert calls == ["64.0", "0.0"]
        for index in range(10):
            await vod.read(f"segment{index:08d}.ts")
        assert len(vod.cache) == 8 and 0 not in vod.cache
        assert await vod.read("segment00000000.ts") == b"0.0"
    for name in ("../file", "segment-1.ts", "segment00000014.ts"):
        with pytest.raises(FileNotFoundError):
            await vod.read(name)
    await vod.async_close()
    assert not vod.cache
    with pytest.raises(FileNotFoundError):
        await vod.read("index.m3u8")


async def test_shared_requests_cancellation_queue_limit_and_close(vod):
    vod.duration, vod.size = 120, 100
    entered, release = asyncio.Event(), asyncio.Event()

    async def render(*args):
        entered.set()
        await release.wait()
        return b"segment"

    with (
        patch.object(vod, "_size", AsyncMock(return_value=100)),
        patch.object(vod, "_run", side_effect=render) as run,
    ):
        first = asyncio.create_task(vod.read("segment00000000.ts"))
        await entered.wait()
        shared = asyncio.create_task(vod.read("segment00000000.ts"))
        await asyncio.sleep(0)
        first.cancel()
        with pytest.raises(asyncio.CancelledError):
            await first
        assert len(vod.pending) == 1
        others = [asyncio.create_task(vod.read(f"segment{i:08d}.ts")) for i in range(1, 4)]
        await asyncio.sleep(0)
        with pytest.raises(ValueError, match="queue full"):
            await vod.read("segment00000004.ts")
        release.set()
        assert await shared == b"segment"
        assert await asyncio.gather(*others) == [b"segment"] * 3
        assert run.await_count == 4 and not vod.pending
        release.clear()
        entered.clear()
        abandoned = asyncio.create_task(vod.read("segment00000005.ts"))
        await entered.wait()
        await vod.async_close()
        with pytest.raises(asyncio.CancelledError):
            await abandoned
        assert not vod.pending and not vod.cache


@pytest.mark.parametrize(
    "metadata",
    [
        {},
        {"format": {"duration": "nan"}},
        {"format": {"duration": -1}},
        {"format": {"duration": 86401}},
        {"format": {"duration": 12}, "streams": [1]},
        {"format": {"duration": 12}, "streams": [{"codec_type": "audio"}]},
    ],
)
async def test_invalid_duration_or_video_never_advertises_vod(vod, metadata):
    with (
        patch.object(vod, "_size", AsyncMock(return_value=100)),
        patch.object(vod, "_run", AsyncMock(return_value=json.dumps(metadata).encode())),
    ):
        with pytest.raises(ValueError):
            await vod.prepare()
    assert not vod.cache


async def test_preparation_and_changed_recording(vod):
    metadata = {
        "format": {"duration": "12.5"},
        "streams": [{"codec_type": "video", "codec_name": "h264"}],
    }
    with (
        patch.object(vod, "_size", AsyncMock(return_value=100)),
        patch.object(
            vod, "_run", AsyncMock(side_effect=[json.dumps(metadata).encode(), b"amount", b"first"])
        ),
    ):
        await vod.prepare()
    assert vod.duration == 12.5 and vod.cache[0] == b"first"
    with patch.object(vod, "_size", AsyncMock(return_value=101)):
        with pytest.raises(ValueError, match="segment unavailable"):
            await vod.read("segment00000001.ts")
    with (
        patch.object(vod, "_size", AsyncMock(side_effect=[100, 101])),
        patch.object(vod, "_run", AsyncMock(return_value=json.dumps(metadata).encode())),
    ):
        with pytest.raises(ValueError, match="size changed"):
            await vod.prepare()
    vod.binary = "/opt/ffmpeg.exe"
    with (
        patch.object(vod, "_size", AsyncMock(return_value=100)),
        patch.object(vod, "_run", AsyncMock(return_value=json.dumps(metadata).encode())) as run,
    ):
        await vod.prepare()
        assert run.call_args_list[0].args[0] == "/opt/ffprobe.exe"


@pytest.mark.parametrize(
    ("status", "headers", "valid"),
    [
        (206, {"Content-Range": "bytes 0-0/123", "Content-Length": "1"}, True),
        (200, {"Content-Length": "123"}, False),
        (206, {"Content-Range": "bytes 1-1/123", "Content-Length": "1"}, False),
        (206, {"Content-Range": "bytes 0-0/123", "Content-Length": "2"}, False),
    ],
)
async def test_range_support_is_verified(vod, status, headers, valid):
    context = MagicMock(
        __aenter__=AsyncMock(return_value=SimpleNamespace(status=status, headers=headers)),
        __aexit__=AsyncMock(return_value=False),
    )
    vod.client.get.return_value = context
    if valid:
        assert await vod._size() == 123
    else:
        with pytest.raises(ValueError, match="byte ranges unavailable"):
            await vod._size()


@pytest.mark.parametrize(
    ("payload", "exit_code", "valid"),
    [(b"ts", 0, True), (b"", 0, False), (b"ts", 1, False), (b"large", None, False)],
)
async def test_subprocess_is_bounded_and_reaped(vod, payload, exit_code, valid):
    process = MagicMock(
        returncode=exit_code,
        stdout=SimpleNamespace(read=AsyncMock(side_effect=[payload, b""])),
        wait=AsyncMock(),
        communicate=AsyncMock(),
    )
    with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=process)):
        if valid:
            assert await vod._run("ffmpeg", [], 4) == b"ts"
        else:
            with pytest.raises(ValueError):
                await vod._run("ffmpeg", [], 4)
    process.communicate.assert_awaited_once()
    assert process.kill.called == (exit_code is None)


@pytest.mark.parametrize("duration", [19.2, 20.0], ids=["aligned", "short_tail"])
async def test_real_recording_seek_decodes_requested_colours(
    hass, entry, aiohttp_server, socket_enabled, tmp_path, duration
):
    source = tmp_path / "colours.ts"
    process = await asyncio.create_subprocess_exec(
        "ffmpeg",
        "-v",
        "error",
        "-f",
        "lavfi",
        "-i",
        f"color=red:s=160x90:r=25:d=6.4[r];color=blue:s=160x90:r=25:d=6.4[b];color=green:s=160x90:r=25:d={duration - 12.8}[g];[r][b][g]concat=n=3:v=1:a=0",
        "-f",
        "lavfi",
        "-i",
        "sine=frequency=440:sample_rate=48000",
        "-t",
        str(duration),
        "-c:v",
        "mpeg2video",
        "-g",
        "25",
        "-c:a",
        "mp2",
        "-threads",
        "1",
        str(source),
    )
    assert await process.wait() == 0
    ranges = []
    requested = []

    async def hls(request):
        filename = request.match_info["filename"]
        requested.append(filename)
        return web.Response(
            body=await stream.vod.read(filename),
            content_type="application/x-mpegURL" if filename.endswith("m3u8") else "video/mp2t",
        )

    async def receiver(request):
        assert request.headers.get("Authorization", "").startswith("Basic ")
        ranges.append(request.headers.get("Range"))
        return web.FileResponse(source)

    app = web.Application()
    app.router.add_get("/file", receiver)
    app.router.add_get("/hls/{filename}", hls)
    server = await aiohttp_server(app)
    hass.config_entries.async_update_entry(entry, options={"external_playback": True})
    async with aiohttp.ClientSession() as client:
        stream = StreamSession(
            hass,
            SimpleNamespace(
                entry=entry,
                client=OpenWebifClient(client, server.host, server.port, "root", "secret"),
            ),
        )
        try:
            await stream.async_play(server.make_url("/file"), recording=True)
            assert stream.vod is not None, stream.processing
            assert stream.directory is None and stream.process is None
            assert abs(stream.vod.duration - duration) < 0.1
            playlist = await stream.vod.read("index.m3u8")
            assert b"#EXT-X-ENDLIST" in playlist
            assert playlist.count(b"#EXTINF:") == math.ceil(duration / 6.4)
            for index, expected in [(2, 1), (0, 0), (1, 2)] + (
                [(3, 1)] if duration == 20.0 else []
            ):
                segment = tmp_path / f"segment{index}.ts"
                segment.write_bytes(await stream.vod.read(f"segment{index:08d}.ts"))
                decode = await asyncio.create_subprocess_exec(
                    "ffmpeg",
                    "-v",
                    "error",
                    "-i",
                    str(segment),
                    "-frames:v",
                    "1",
                    "-vf",
                    "scale=1:1",
                    "-f",
                    "rawvideo",
                    "-pix_fmt",
                    "rgb24",
                    "pipe:1",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                frame, errors = await decode.communicate()
                assert decode.returncode == 0 and not errors
                assert len(frame) == 3 and max(range(3), key=frame.__getitem__) == expected, (
                    index,
                    frame,
                )
            assert any(value and value != "bytes=0-0" for value in ranges)
            stream.vod.cache.clear()
            # A real HLS client must select the late segment from the full timeline.
            decode = await asyncio.create_subprocess_exec(
                "ffmpeg",
                "-v",
                "error",
                "-ss",
                "12.8",
                "-i",
                str(server.make_url("/hls/index.m3u8")),
                "-frames:v",
                "1",
                "-vf",
                "scale=1:1",
                "-f",
                "rawvideo",
                "-pix_fmt",
                "rgb24",
                "pipe:1",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            frame, errors = await decode.communicate()
            assert decode.returncode == 0 and not errors, errors
            assert len(frame) == 3 and max(range(3), key=frame.__getitem__) == 1
            assert "segment00000002.ts" in requested
            # Decode the complete presentation across the segment boundaries.
            decode = await asyncio.create_subprocess_exec(
                "ffmpeg",
                "-v",
                "error",
                "-i",
                str(server.make_url("/hls/index.m3u8")),
                "-f",
                "null",
                "-",
                stderr=asyncio.subprocess.PIPE,
            )
            _, errors = await decode.communicate()
            assert decode.returncode == 0 and not errors, errors
        finally:
            await stream.async_close()
        assert stream.vod is None and stream.runner is None


@pytest.mark.parametrize(
    ("video_duration", "container_duration", "expected"),
    [("12.8", "12.82", 12.8), (None, "12.82", 12.8), ("N/A", "12.5", 12.5)],
)
async def test_duration_prefers_video_and_avoids_empty_tail(
    vod, video_duration, container_duration, expected
):
    metadata = {
        "format": {"duration": container_duration},
        "streams": [{"codec_type": "video", "duration": video_duration}],
    }
    with (
        patch.object(vod, "_size", AsyncMock(return_value=100)),
        patch.object(
            vod, "_run", AsyncMock(side_effect=[json.dumps(metadata).encode(), b"amount", b"first"])
        ),
    ):
        await vod.prepare()
    assert vod.duration == expected


async def test_non_object_probe_and_invalid_numeric_duration(vod):
    for metadata in (
        [],
        {"streams": [{"codec_type": "video"}], "format": {"duration": "nan"}},
        {"streams": [{"codec_type": "video"}], "format": {"duration": 86401}},
    ):
        with (
            patch.object(vod, "_size", AsyncMock(return_value=100)),
            patch.object(vod, "_run", AsyncMock(return_value=json.dumps(metadata).encode())),
        ):
            with pytest.raises(ValueError):
                await vod.prepare()


async def test_vod_ha_urls_parallel_sessions_and_cleanup(
    hass, entry, pool, socket_enabled, hass_client_no_auth
):
    async def prepare(self):
        self.duration, self.size = 18, 100
        self.cache[0] = b"first"

    client = await hass_client_no_auth()
    with (
        patch.object(RecordingVOD, "prepare", prepare),
        patch.object(RecordingVOD, "_size", AsyncMock(return_value=100)),
        patch.object(RecordingVOD, "_run", AsyncMock(return_value=b"late segment")),
    ):
        first = await pool.async_play(URL("http://receiver.local/file?file=one.ts"), recording=True)
        second = await pool.async_play(
            URL("http://receiver.local/file?file=two.ts"), recording=True
        )
        assert first.url != second.url and len(pool.sessions) == 2
        for playback in (first, second):
            response = await client.get(playback.url)
            assert response.status == 200 and "#EXT-X-PLAYLIST-TYPE:VOD" in await response.text()
            response = await client.get(playback.url.replace("index.m3u8", "segment00000002.ts"))
            assert response.status == 200 and await response.read() == b"late segment"
            response = await client.get(playback.url.replace("index.m3u8", "segment00000003.ts"))
            assert response.status == 404
        sessions = list(pool.sessions)
        await sessions[0].async_close()
        assert (await client.get(first.url)).status == 404
        assert (await client.get(second.url)).status == 200
        sessions[1].vod.cache.clear()
        with patch.object(RecordingVOD, "_size", AsyncMock(return_value=101)):
            assert (
                await client.get(second.url.replace("index.m3u8", "segment00000002.ts"))
            ).status == 502
        await hass.config_entries.async_unload(entry.entry_id)
        assert not pool.sessions and sessions[1].vod is None


async def test_cancelled_subprocess_is_killed_and_drained(vod):
    entered = asyncio.Event()

    async def read(size):
        entered.set()
        await asyncio.Event().wait()

    process = MagicMock(returncode=None, stdout=SimpleNamespace(read=read), communicate=AsyncMock())
    with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=process)):
        task = asyncio.create_task(vod._run("ffmpeg", [], 4))
        await entered.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    process.kill.assert_called_once()
    process.communicate.assert_awaited_once()
