# SPDX-License-Identifier: Apache-2.0
"""Keyframe index validation and real lossless VOD playback."""

import asyncio
import json
import math
import struct
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest
from aiohttp import web

from custom_components.enigma2_connect.api import OpenWebifClient
from custom_components.enigma2_connect.media_stream import StreamSession
from custom_components.enigma2_connect.stream_remux import MAX_INDEX_BYTES, RecordingRemux
from custom_components.enigma2_connect.stream_vod import RecordingVOD


def index_bytes(points):
    return b"".join(struct.pack(">QQ", offset, pts) for offset, pts in points)


def test_index_and_immutable_original_timestamps():
    data = index_bytes((i * 188, (2 + i * 2) * 90000) for i in range(10))
    remux = RecordingRemux.parse(data, 10000, 2, 20, 1.5, False)
    assert remux.points == (2, 10, 18, 22) and remux.duration == 20
    args = remux.arguments(1, "http://127.0.0.1/private")
    assert args[args.index("-c:v") + 1] == "copy"
    assert args[args.index("-c:a") + 1] == "aac"
    assert "-vf" not in args and "-r" not in args
    assert "amount=0" in args[args.index("-bsf:v") + 1]
    assert "atrim=start=10.000000:end=18.000000" in args


@pytest.mark.parametrize(
    "data,start,duration,origin",
    [
        (b"", 2, 20, 1),
        (b"x" * 33, 2, 20, 1),
        (b"x" * (MAX_INDEX_BYTES + 16), 2, 20, 1),
        (index_bytes([(0, 180000), (188, 360000)]), math.nan, 20, 1),
        (index_bytes([(0, 180000), (188, 360000)]), 2, 20, 3),
        (index_bytes([(0, 180000), (189, 360000)]), 2, 20, 1),
        (index_bytes([(188, 180000), (0, 360000)]), 2, 20, 1),
        (index_bytes([(0, 180000), (188, 180000)]), 2, 20, 1),
        (index_bytes([(0, 180000), (188, 2000000)]), 2, 20, 1),
        (index_bytes([(0, 180000), (188, 360000)]), 2, 20, 1),
        (index_bytes([(0, 0), (188, 360000)]), 2, 3, 1),
        (index_bytes([(0, 180000), (188, 450000)]), 2, 3, 1),
        (index_bytes([(0, (1 << 33) - 1), (188, 10)]), 2, 20, 1),
    ],
    ids=[
        "empty",
        "misaligned_length",
        "oversized",
        "nonfinite",
        "origin",
        "unaligned_offset",
        "unordered_offset",
        "duplicate_pts",
        "pts_jump",
        "stale_end",
        "wrong_start",
        "end_overrun",
        "pts_wrap",
    ],
)
def test_reject_invalid_stale_or_discontinuous_index(data, start, duration, origin):
    with pytest.raises(ValueError, match="Recording index"):
        RecordingRemux.parse(data, 10000, start, duration, origin, False)


@pytest.mark.parametrize(
    "mode",
    [
        "copy",
        "audio",
        "forced",
        "missing",
        "oversize",
        "bad",
        "failed",
        "old_ffmpeg",
        "tail",
        "help_failed",
    ],
)
async def test_vod_selects_remux_or_safe_fallback(hass, mode, caplog):
    metadata = {
        "format": {"start_time": "1", "duration": "20"},
        "streams": [
            {
                "codec_type": "video",
                "codec_name": "h264",
                "profile": "High",
                "pix_fmt": "yuv420p",
                "field_order": "progressive",
                "level": 40,
                "start_time": "2",
                "duration": "20",
            },
            {
                "codec_type": "audio",
                "codec_name": "mp2" if mode == "audio" else "aac",
                "profile": "LC",
                "sample_rate": "48000",
                "channels": 2,
            },
        ],
    }
    if mode == "tail":
        metadata["streams"][0]["duration"] = "19.22"
    data = index_bytes((i * 188, (2 + i * 2) * 90000) for i in range(10))
    if mode == "oversize":
        data = b"x" * (MAX_INDEX_BYTES + 1)
    if mode == "bad":
        data = b"invalid"

    async def chunks(size):
        for i in range(0, len(data), 7):
            yield data[i : i + 7]

    client = MagicMock()
    client.get.return_value = MagicMock(
        __aenter__=AsyncMock(
            return_value=SimpleNamespace(
                status=404 if mode == "missing" else 200,
                content=SimpleNamespace(iter_chunked=chunks),
            )
        ),
        __aexit__=AsyncMock(return_value=False),
    )
    vod = RecordingVOD(
        hass, client, "ffmpeg", "http://127.0.0.1/private", "test", compatible=mode == "forced"
    )
    calls = []

    async def run(binary, args, limit):
        if binary == "ffprobe":
            return json.dumps(metadata).encode()
        if "-h" in args:
            if mode == "help_failed":
                raise OSError("unavailable")
            return b"amount drop" if mode != "old_ffmpeg" else b"amount"
        calls.append(args)
        if mode == "failed" and "-copyts" in args:
            raise ValueError("Recording conversion failed")
        return b"segment"

    with (
        patch.object(vod, "_size", AsyncMock(return_value=10000)),
        patch.object(vod, "_run", side_effect=run),
    ):
        await vod.prepare()
        if mode in ("copy", "audio", "tail"):
            assert vod.remux is not None and vod.segment_count == 3
            assert vod.processing == "recording_vod+copy_video+" + (
                "encode_audio" if mode == "audio" else "copy_audio"
            )
            assert b"#EXT-X-TARGETDURATION:8" in vod.playlist()
            if mode == "tail":
                assert vod.duration == pytest.approx(19.22)
                assert b"#EXTINF:3.220000," in vod.playlist()
            else:
                assert b"#EXTINF:4.000000," in vod.playlist()
            assert await vod.read("segment00000002.ts") == b"segment"
        else:
            assert vod.remux is None and vod.duration == 20
            assert vod.processing == "recording_vod+encode_video+encode_audio"
            assert "libx264" in calls[-1]
        if mode == "forced":
            client.get.assert_not_called()
    await vod.async_close()


async def test_cache_also_has_a_total_byte_limit(hass):
    vod = RecordingVOD(hass, MagicMock(), "ffmpeg", "http://127.0.0.1/private", "test")
    vod.remux = RecordingRemux((1, 9, 17, 25), 1, True)
    vod.duration, vod.size = 24, 100
    payload = b"x" * (12 * 1024 * 1024)
    with (
        patch.object(vod, "_size", AsyncMock(return_value=100)),
        patch.object(vod, "_run", AsyncMock(return_value=payload)),
    ):
        for i in range(3):
            await vod.read(f"segment{i:08d}.ts")
    assert list(vod.cache) == [1, 2]
    await vod.async_close()


@pytest.mark.parametrize("audio_codec", ["aac", "mp2"])
async def test_real_remux_preserves_packet_hashes_and_hls_seek(
    hass, entry, aiohttp_server, socket_enabled, tmp_path, audio_codec
):
    async def command(binary, *args):
        p = await asyncio.create_subprocess_exec(
            binary, *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        try:
            out, err = await asyncio.wait_for(p.communicate(), 45)
        finally:
            if p.returncode is None:
                p.kill()
                await p.communicate()
        assert p.returncode == 0, err
        return out, err

    help_text, _ = await command("ffmpeg", "-hide_banner", "-h", "bsf=noise")
    if b"drop" not in help_text:
        pytest.skip("FFmpeg noise drop packet filtering unavailable; VOD falls back to encoding")
    source = tmp_path / "source.ts"
    await command(
        "ffmpeg",
        "-v",
        "error",
        "-f",
        "lavfi",
        "-i",
        "testsrc2=s=320x180:r=50:d=20",
        "-f",
        "lavfi",
        "-i",
        "sine=sample_rate=48000",
        "-t",
        "20",
        "-c:v",
        "libx264",
        "-preset",
        "ultrafast",
        "-g",
        "100",
        "-bf",
        "2",
        "-flags",
        "+cgop",
        "-sc_threshold",
        "0",
        "-c:a",
        audio_codec,
        "-threads",
        "2",
        str(source),
    )

    async def packets(path):
        out, _ = await command(
            "ffprobe",
            "-v",
            "error",
            "-show_packets",
            "-show_data_hash",
            "sha256",
            "-show_entries",
            "packet=codec_type,pts_time,dts_time,pos,flags,data_hash",
            "-of",
            "json",
            str(path),
        )
        return json.loads(out)["packets"]

    original = await packets(source)
    video = [p for p in original if p["codec_type"] == "video"]
    data = index_bytes(
        (int(p["pos"]), round(float(p["pts_time"]) * 90000)) for p in video if "K" in p["flags"]
    )
    range_requests = []

    async def receiver(request):
        assert request.headers.get("Authorization", "").startswith("Basic ")
        if request.query.get("file", "").endswith(".ap"):
            return web.Response(body=data)
        range_requests.append(request.headers.get("Range"))
        return web.FileResponse(source)

    async def hls(request):
        return web.Response(body=await stream.vod.read(request.match_info["filename"]))

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
            await stream.async_play(server.make_url("/file?file=/movie.ts"), recording=True)
            assert stream.vod.remux is not None, stream.processing
            assert stream.processing == "recording_vod+copy_video+" + (
                "copy_audio" if audio_codec == "aac" else "encode_audio"
            )
            outputs = {}
            for i in (2, 0, 1):
                path = tmp_path / f"segment{i}.ts"
                path.write_bytes(await stream.vod.read(f"segment{i:08d}.ts"))
                outputs[i] = await packets(path)
                _, errors = await command(
                    "ffmpeg", "-v", "error", "-i", str(path), "-f", "null", "-"
                )
                assert not errors, errors
            rendered = [
                p for i in sorted(outputs) for p in outputs[i] if p["codec_type"] == "video"
            ]
            assert [p["data_hash"] for p in rendered] == [p["data_hash"] for p in video]
            assert len(rendered) == 1000  # Original 50 fps retained, not reduced to 25 fps.
            dts = [float(p["dts_time"]) for p in rendered]
            assert all(a < b for a, b in zip(dts, dts[1:]))
            if audio_codec == "aac":
                audio = [
                    p["data_hash"]
                    for p in original
                    if p["codec_type"] == "audio"
                    and float(video[0]["pts_time"])
                    <= float(p["pts_time"])
                    < float(video[0]["pts_time"]) + 20
                ]
                assert [
                    p["data_hash"]
                    for i in sorted(outputs)
                    for p in outputs[i]
                    if p["codec_type"] == "audio"
                ] == audio
            stream.vod.cache.clear()
            _, errors = await command(
                "ffmpeg",
                "-v",
                "error",
                "-ss",
                "10",
                "-i",
                str(server.make_url("/hls/index.m3u8")),
                "-t",
                "5",
                "-f",
                "null",
                "-",
            )
            assert not errors, errors
            _, errors = await command(
                "ffmpeg",
                "-v",
                "error",
                "-i",
                str(server.make_url("/hls/index.m3u8")),
                "-f",
                "null",
                "-",
            )
            assert not errors, errors
            assert any(r and r != "bytes=0-0" for r in range_requests)
        finally:
            await stream.async_close()
