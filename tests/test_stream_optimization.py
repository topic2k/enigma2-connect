# SPDX-License-Identifier: Apache-2.0
"""Codec decisions, receiver discovery, direct HLS and optimized fallback."""

import asyncio
import json
import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest
from aiohttp import web
from yarl import URL

from custom_components.enigma2_connect.api import OpenWebifClient
from custom_components.enigma2_connect.media_stream import MediaStreamView
from custom_components.enigma2_connect.stream_codec import (
    codec_details,
    copy_codecs,
    failure_reason,
    probe,
)
from custom_components.enigma2_connect.stream_receiver import (
    ReceiverHLS,
    discover_hls,
    discover_transcoded,
    fetch,
    receiver_url,
)

from . import test_media_stream as fixtures

configured = fixtures.configured
spawn = fixtures.spawn

VIDEO = {
    "codec_type": "video",
    "codec_name": "h264",
    "profile": "High",
    "pix_fmt": "yuv420p",
    "field_order": "progressive",
    "level": 41,
}
AUDIO = {
    "codec_type": "audio",
    "codec_name": "aac",
    "profile": "LC",
    "channels": 2,
    "sample_rate": "48000",
}
MODULE = "custom_components.enigma2_connect.media_stream."


@pytest.mark.parametrize(
    ("video", "audio", "expected"),
    [
        (VIDEO, AUDIO, (True, True)),
        ({**VIDEO, "field_order": "tt"}, AUDIO, (False, True)),
        ({**VIDEO, "codec_name": "hevc"}, AUDIO, (False, True)),
        ({**VIDEO, "pix_fmt": "yuv420p10le"}, AUDIO, (False, True)),
        ({**VIDEO, "level": 51}, AUDIO, (False, True)),
        (VIDEO, {**AUDIO, "codec_name": "ac3"}, (True, False)),
        (VIDEO, {**AUDIO, "channels": 6}, (True, False)),
        (VIDEO, {**AUDIO, "profile": "HE-AAC"}, (True, False)),
        (VIDEO, None, (True, True)),
        ({}, AUDIO, (False, True)),
    ],
)
def test_browser_copy_policy(video, audio, expected):
    assert copy_codecs([video] + ([audio] if audio else [])) == expected


@pytest.mark.parametrize("payload", [b"invalid", b"{}", b"[]", b'{"streams":[1]}', b"x" * 65537])
async def test_probe_rejects_malformed_output(payload):
    process = MagicMock(
        returncode=0,
        wait=AsyncMock(),
        communicate=AsyncMock(return_value=(b"", b"")),
        stdout=SimpleNamespace(read=AsyncMock(side_effect=[payload, b""])),
    )
    with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=process)):
        assert await probe("ffmpeg", "http://127.0.0.1/private") == (False, False)


async def test_probe_credentials_binary_and_cancellation(caplog):
    caplog.set_level(logging.DEBUG, logger="custom_components.enigma2_connect.stream_codec")
    payload = json.dumps({"streams": [VIDEO, AUDIO]}).encode()
    process = MagicMock(
        returncode=0,
        wait=AsyncMock(),
        communicate=AsyncMock(return_value=(b"", b"")),
        stdout=SimpleNamespace(read=AsyncMock(side_effect=[payload, b""])),
    )
    with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=process)) as create:
        assert await probe(
            "/opt/ffmpeg", "http://127.0.0.1/private", stream_id="test-session", stage="original"
        ) == (True, True)
        assert "[stream=test-session] Input original: container=mpegts" in caplog.text
        assert "'codec_name': 'h264'" in caplog.text and "'codec_name': 'aac'" in caplog.text
        assert "Copy compatibility original: video=True audio=True" in caplog.text
        assert "127.0.0.1" not in caplog.text and "private" not in caplog.text
        assert create.call_args.args[0] == "/opt/ffprobe"
    process.returncode = None
    process.stdout.read = AsyncMock(side_effect=asyncio.CancelledError)
    with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=process)):
        with pytest.raises(asyncio.CancelledError):
            await probe("ffmpeg", "http://127.0.0.1/private")
    process.kill.assert_called_once()
    with patch("asyncio.create_subprocess_exec", side_effect=FileNotFoundError):
        assert await probe("ffmpeg", "http://127.0.0.1/private") == (False, False)


@pytest.fixture
async def upstream(aiohttp_server, socket_enabled):
    state = {
        "playlist": "#EXTM3U\n#EXT-X-TARGETDURATION:2\n#EXT-X-MEDIA-SEQUENCE:1\n#EXTINF:2,Sender\none.ts\n",
        "status": 200,
        "calls": [],
    }

    async def handler(request):
        state["calls"].append((request.path, dict(request.query)))
        assert request.headers["Authorization"].startswith("Basic ")
        if request.path == "/web/streamhls.m3u":
            return web.Response(status=307, headers={"Location": state["hls"]})
        if request.path == "/web/video.m3u":
            return web.Response(text=state["transcoded"])
        if request.path == "/stream.m3u8":
            return web.Response(status=state["status"], text=state["playlist"])
        return web.Response(body=b"video")

    app = web.Application()
    app.router.add_get("/{path:.*}", handler)
    server = await aiohttp_server(app)
    state["hls"] = str(server.make_url("/stream.m3u8"))
    state["transcoded"] = "#EXTM3U\n" + str(server.make_url("/channel?bitrate=2000000"))
    async with aiohttp.ClientSession() as session:
        client = OpenWebifClient(session, server.host, server.port, "root", "secret")
        yield client, state


async def test_receiver_discovery_does_not_zap(upstream):
    client, state = upstream
    assert await discover_hls(client, "channel") == URL(state["hls"])
    result = await discover_transcoded(client, client.base_url.with_path("/channel"))
    assert result.query == {"bitrate": "2000000"}
    assert all("zap" not in query for _, query in state["calls"])
    assert [path for path, _ in state["calls"]] == ["/web/streamhls.m3u", "/web/video.m3u"]
    assert "device" in state["calls"][1][1]


@pytest.mark.parametrize(
    "address",
    [
        "http://foreign.invalid/video.ts",
        "file:///etc/passwd",
        "//receiver/video",
        "http://127.0.0.1/file#fragment",
    ],
)
async def test_receiver_addresses_are_confined(upstream, address):
    client, _ = upstream
    with pytest.raises(ValueError):
        receiver_url(client, address)


async def test_embedded_auth_is_stripped(upstream):
    client, state = upstream
    value = URL(state["hls"]).with_user("unexpected").with_password("secret")
    assert receiver_url(client, str(value)).user is None


async def test_hls_rewrite_limits_and_rotation(upstream):
    client, state = upstream
    remote = ReceiverHLS(client, URL(state["hls"]))
    content = (await remote.playlist()).decode()
    assert "http" not in content and "Sender" not in content
    filename = content.splitlines()[-1]
    assert filename.startswith("remote") and await remote.read(filename) == b"video"
    with pytest.raises(FileNotFoundError):
        await remote.read("unknown.ts")
    for i in range(3):
        state["playlist"] = "#EXTM3U\n#EXT-X-TARGETDURATION:2\n" + "".join(
            f"#EXTINF:2,\nsegment{j}.ts\n" for j in range(i * 64, (i + 1) * 64)
        )
        await remote.playlist()
    assert len(remote.segments) == 128 and filename not in remote.segments
    with pytest.raises(ValueError):
        await fetch(client, URL(state["hls"]), 5)
    state["status"] = 302
    with pytest.raises(ValueError):
        await remote.playlist()


@pytest.mark.parametrize(
    "playlist",
    [
        "#EXTM3U\nhttp://receiver:8001/channel\n",
        '#EXTM3U\n#EXT-X-TARGETDURATION:2\n#EXT-X-KEY:METHOD=AES-128,URI="key"\none.ts\n',
        '#EXTM3U\n#EXT-X-TARGETDURATION:2\n#EXT-X-MAP:URI="init.mp4"\none.ts\n',
        "#EXTM3U\n#EXT-X-TARGETDURATION:2\nhttp://foreign.invalid/one.ts\n",
        "#EXTM3U\n#EXT-X-TARGETDURATION:2\none.m4s\n",
        "#EXTM3U\n#EXT-X-TARGETDURATION:60\none.ts\n",
        "<html>not a playlist</html>",
    ],
)
async def test_hls_unsupported_formats_fall_back(upstream, playlist):
    client, state = upstream
    state["playlist"] = playlist
    with pytest.raises(ValueError):
        await ReceiverHLS(client, URL(state["hls"])).playlist()


async def test_direct_hls_has_no_encoder_and_keeps_token_checks(hass, entry, configured, upstream):
    receiver_client, state = upstream
    configured.coordinator.client = receiver_client
    hass.config_entries.async_update_entry(entry, options={**entry.options, "stream_mode": "auto"})
    with (
        patch(MODULE + "probe", AsyncMock(return_value=(True, True))),
        patch("asyncio.create_subprocess_exec") as create,
    ):
        result = await configured.async_play(
            receiver_client.base_url.with_path("/channel"), recording=False
        )
        create.assert_not_called()
    assert configured.processing == "receiver_hls"
    assert configured.process is None and configured.directory is None and configured.runner is None
    view = MediaStreamView(hass)
    response = await view.get(None, entry.entry_id, configured.token, "index.m3u8")
    assert response.headers["Content-Type"].split(";")[0] == "application/x-mpegURL"
    filename = response.body.decode().splitlines()[-1]
    segment = await view.get(None, entry.entry_id, configured.token, filename)
    assert segment.body == b"video"
    assert "secret" not in result.url
    with pytest.raises(web.HTTPNotFound):
        await view.get(None, entry.entry_id, "invalid", filename)
    state["status"] = 500
    with pytest.raises(web.HTTPBadGateway):
        await view.get(None, entry.entry_id, configured.token, "index.m3u8")
    await configured.async_close()
    assert configured.remote is None


@pytest.mark.parametrize(
    ("codecs", "expected"),
    [
        ((True, True), ("copy", "copy")),
        ((True, False), ("copy", "aac")),
        ((False, True), ("libx264", "copy")),
    ],
)
async def test_transcode_only_incompatible_tracks(
    hass, entry, configured, spawn, socket_enabled, codecs, expected
):
    hass.config_entries.async_update_entry(entry, options={**entry.options, "stream_mode": "auto"})
    with patch(MODULE + "probe", AsyncMock(return_value=codecs)):
        await configured.async_play(URL("http://receiver.local/file"), recording=True)
    args = spawn[-1][1]
    assert (args[args.index("-c:v") + 1], args[args.index("-c:a") + 1]) == expected
    assert ("-vf" in args) == (not codecs[0])


async def test_receiver_transcoding_and_start_fallback(
    hass, entry, configured, spawn, socket_enabled, caplog
):
    caplog.set_level(logging.DEBUG, logger="custom_components.enigma2_connect.media_stream")
    hass.config_entries.async_update_entry(entry, options={**entry.options, "stream_mode": "auto"})
    candidate = URL("http://receiver.local:8002/channel")
    with (
        patch(MODULE + "discover_hls", side_effect=ValueError),
        patch(MODULE + "discover_transcoded", AsyncMock(return_value=candidate)),
        patch(MODULE + "probe", AsyncMock(side_effect=[(False, False), (True, True)])),
    ):
        await configured.async_play(URL("http://receiver.local:8001/channel"), recording=False)
    assert configured.processing == "receiver_transcoding+copy_video+copy_audio"
    assert (
        f"[stream={configured.stream_id}] Started: processing=receiver_transcoding+copy_video+copy_audio"
        in caplog.text
    )
    assert "Receiver HLS unavailable: ValueError" in caplog.text
    assert configured.token not in caplog.text
    original_start = configured._start
    calls = []

    async def failed_copy(source, *, recording, compatible):
        calls.append(compatible)
        if not compatible:
            raise OSError("cannot remux http://root:secret@receiver.local/private-token")
        await original_start(source, recording=recording, compatible=compatible)

    with patch.object(configured, "_start", side_effect=failed_copy):
        await configured.async_play(URL("http://receiver.local/file"), recording=True)
    assert calls == [False, True] and configured.processing == "encode_video+encode_audio"
    logs = "\n".join(
        record.getMessage() for record in caplog.records if record.name.endswith("media_stream")
    )
    assert "Start failed: mode=auto reason=OSError" in logs
    assert "Retrying compatibility mode" in logs
    assert "Input original: not_probed (compatibility mode)" in logs
    assert "bounds=1280x720 fps=25 target=2000k" in logs
    assert all(
        value not in logs
        for value in ("secret", "receiver.local", "private-token", configured.token)
    )


@pytest.mark.parametrize(
    "playlist",
    [
        "<html>Unavailable</html>",
        "#EXTM3U\n",
        "#EXTM3U\nhttp://foreign.invalid/a\nhttp://foreign.invalid/b\n",
        "#EXTM3U\n{base}/wrong-path\n",
        "#EXTM3U\n{base}/channel\n",
    ],
)
async def test_transcoding_unavailable_or_invalid(upstream, playlist):
    client, state = upstream
    state["transcoded"] = playlist.format(base=client.base_url)
    with pytest.raises(ValueError):
        await discover_transcoded(client, client.base_url.with_path("/channel"))


async def test_hls_endpoint_missing_and_blank_lines(upstream):
    client, state = upstream
    state["playlist"] += "\n"
    await ReceiverHLS(client, URL(state["hls"])).playlist()
    response = MagicMock(status=404)
    context = MagicMock(
        __aenter__=AsyncMock(return_value=response), __aexit__=AsyncMock(return_value=False)
    )
    with patch.object(client.session, "get", return_value=context):
        with pytest.raises(ValueError):
            await discover_hls(client, "channel")


@pytest.mark.parametrize("failure", [TimeoutError(), None])
async def test_probe_timeout_and_failed_process(failure):
    process = MagicMock(
        returncode=None if failure else 1,
        wait=AsyncMock(),
        communicate=AsyncMock(return_value=(b"", b"")),
        stdout=SimpleNamespace(read=AsyncMock(side_effect=failure, return_value=b"")),
    )
    with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=process)):
        assert await probe("ffmpeg.exe", "http://127.0.0.1/private") == (False, False)
    if failure:
        process.kill.assert_called_once()


@pytest.mark.parametrize("candidate", [None, (False, True)])
async def test_unusable_receiver_transcoding_keeps_original(
    hass, entry, configured, spawn, socket_enabled, candidate
):
    hass.config_entries.async_update_entry(entry, options={**entry.options, "stream_mode": "auto"})
    with (
        patch(MODULE + "discover_hls", side_effect=ValueError),
        patch(
            MODULE + "discover_transcoded",
            AsyncMock(
                side_effect=ValueError if candidate is None else None,
                return_value=URL("http://receiver.local:8002/channel"),
            ),
        ),
        patch(MODULE + "probe", AsyncMock(side_effect=[(True, False), candidate])),
    ):
        await configured.async_play(URL("http://receiver.local:8001/channel"), recording=False)
    assert configured.processing == "copy_video+encode_audio"


async def test_inflight_hls_request_invalidated_by_session_cleanup(hass, entry, configured):
    configured.token = "old"
    from time import monotonic

    configured.started = configured.touched = monotonic()

    async def replaced(filename):
        configured.token = "new"
        return b"old video"

    configured.remote = SimpleNamespace(read=replaced)
    with pytest.raises(web.HTTPNotFound):
        await MediaStreamView(hass).get(None, entry.entry_id, "old", "index.m3u8")
    configured.remote = None


async def test_real_receiver_hls_is_relayed_without_encoder(
    hass, entry, aiohttp_server, socket_enabled, tmp_path
):
    import shutil

    from custom_components.enigma2_connect.media_stream import StreamSession as MediaStream

    binary = await hass.async_add_executor_job(shutil.which, "ffmpeg")
    if not binary:
        pytest.skip("FFmpeg required for synthetic receiver HLS")
    video = tmp_path / "source.ts"
    generate = await asyncio.create_subprocess_exec(
        binary,
        "-v",
        "error",
        "-f",
        "lavfi",
        "-i",
        "testsrc2=s=160x90:r=25",
        "-t",
        "4",
        "-c:v",
        "libx264",
        "-g",
        "25",
        "-threads",
        "1",
        "-f",
        "mpegts",
        str(video),
    )
    assert await generate.wait() == 0

    async def handler(request):
        assert request.headers["Authorization"].startswith("Basic ")
        if request.path == "/web/streamhls.m3u":
            return web.Response(
                status=307, headers={"Location": str(request.url.origin().with_path("/live.m3u8"))}
            )
        if request.path == "/live.m3u8":
            return web.Response(text="#EXTM3U\n#EXT-X-TARGETDURATION:4\n#EXTINF:4,\nsource.ts\n")
        return web.FileResponse(video)

    app = web.Application()
    app.router.add_get("/{path:.*}", handler)
    server = await aiohttp_server(app)
    hass.config_entries.async_update_entry(entry, options={"external_playback": True})
    async with aiohttp.ClientSession() as session:
        client = OpenWebifClient(session, server.host, server.port, "root", "secret")
        stream = MediaStream(hass, SimpleNamespace(entry=entry, client=client))
        try:
            with patch(
                "asyncio.create_subprocess_exec", wraps=asyncio.create_subprocess_exec
            ) as create:
                await stream.async_play(server.make_url("/channel"), recording=False)
            assert stream.processing == "receiver_hls"
            assert stream.process is None and stream.directory is None
            assert len(create.call_args_list) == 1 and create.call_args.args[0].endswith("ffprobe")
            playlist = (await stream.remote.playlist()).decode()
            assert await stream.remote.read(
                playlist.splitlines()[-1]
            ) == await hass.async_add_executor_job(video.read_bytes)
        finally:
            await stream.async_close()


async def test_https_requirement_applies_to_receiver_candidates(
    hass, entry, configured, spawn, socket_enabled
):
    hass.config_entries.async_update_entry(
        entry, options={**entry.options, "stream_mode": "auto", "stream_https": True}
    )
    with (
        patch(
            MODULE + "discover_hls",
            AsyncMock(return_value=URL("http://receiver.local:8090/live.m3u8")),
        ),
        patch(
            MODULE + "discover_transcoded",
            AsyncMock(return_value=URL("http://receiver.local:8002/channel")),
        ),
        patch(MODULE + "probe", AsyncMock(return_value=(True, False))) as inspect,
        patch(MODULE + "ReceiverHLS") as remote,
    ):
        await configured.async_play(URL("https://receiver.local:8443/channel"), recording=False)
    remote.assert_not_called()
    inspect.assert_awaited_once()
    assert configured.processing == "copy_video+encode_audio"


def test_codec_diagnostics_only_include_bounded_technical_fields():
    details = codec_details(
        [
            {
                **VIDEO,
                "width": 1920,
                "height": 1080,
                "avg_frame_rate": "25/1",
                "bit_rate": "2500000",
                "tags": {"title": "private-title"},
                "profile": "http://user:secret@receiver/\ninjected",
                "pix_fmt": "x" * 65,
            },
        ],
        "video",
    )
    assert details["width"] == "1920" and details["height"] == "1080"
    assert details["avg_frame_rate"] == "25/1" and details["bit_rate"] == "2500000"
    assert details["profile"] == details["pix_fmt"] == "unknown"
    assert "tags" not in details and "secret" not in str(details)
    assert codec_details([], "audio") == {"track": "absent"}


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (ValueError("Unsupported HLS tag"), "Unsupported HLS tag"),
        (ValueError("No separate transcoded source"), "No separate transcoded source"),
        (
            ValueError("Receiver HLS does not support required HTTPS"),
            "Receiver HLS does not support required HTTPS",
        ),
        (ValueError("http://user:secret@receiver/token"), "ValueError"),
        (TimeoutError("secret"), "TimeoutError"),
    ],
)
def test_failure_diagnostics_do_not_expose_upstream_messages(error, expected):
    assert failure_reason(error) == expected
