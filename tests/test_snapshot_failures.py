# SPDX-License-Identifier: Apache-2.0
"""Exercise the real loopback relay and subprocess cleanup with a fake decoder."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import aiohttp
import pytest
from aiohttp import web

from custom_components.enigma2_connect.api import OpenWebifClient
from custom_components.enigma2_connect.recording_snapshot import (
    extract_snapshot,
    recording_duration,
)

from .test_recording_images import MOVIE


@pytest.mark.parametrize("length", ["0:00", "unknown", "１:００"])
def test_unknown_recording_duration(length):
    assert recording_duration({"length": length}) is None


async def test_relative_recording_without_absolute_reference_never_starts_decoder():
    with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as spawn:
        assert (
            await extract_snapshot(None, {"filename": "relative.ts", "serviceref": "invalid"})
            is None
        )
        spawn.assert_not_awaited()


@pytest.mark.parametrize("mode", ["head", "bad-range", "upstream-error", "limited", "timeout"])
async def test_relay_request_bounds_and_errors(aiohttp_server, socket_enabled, monkeypatch, mode):
    upstream_calls = []

    async def file(request):
        upstream_calls.append(request.method)
        assert request.headers["Authorization"].startswith("Basic ")
        assert request.headers["Accept-Encoding"] == "identity"
        assert request.query["file"] == MOVIE["filename"]
        return web.Response(status=503 if mode == "upstream-error" else 200, body=b"video-data")

    app = web.Application()
    app.router.add_get("/file", file)
    server = await aiohttp_server(app)
    if mode == "limited":
        monkeypatch.setattr(
            "custom_components.enigma2_connect.recording_snapshot.MAX_VIDEO_BYTES", 4
        )
    process = SimpleNamespace(returncode=None, kill=Mock(), wait=AsyncMock())
    async with aiohttp.ClientSession() as upstream:
        client = OpenWebifClient(upstream, server.host, server.port, "root", "private-secret")

        async def spawn(*args, **kwargs):
            url = args[args.index("-i") + 1]
            assert "private-secret" not in str(args)
            assert "127.0.0.1" in url

            async def communicate():
                async with aiohttp.ClientSession() as downstream:
                    if mode == "head":
                        async with downstream.head(url) as response:
                            assert response.status == 200
                            assert await response.read() == b""
                    elif mode == "bad-range":
                        async with downstream.get(
                            url, headers={"Range": "bytes=0-2,5-9"}
                        ) as response:
                            assert response.status == 400
                    elif mode == "timeout":
                        with patch.object(upstream, "request", side_effect=TimeoutError()):
                            async with downstream.get(url) as response:
                                assert response.status == 502
                    else:
                        async with downstream.get(url) as response:
                            if mode == "upstream-error":
                                assert response.status == 502
                            else:
                                with pytest.raises(aiohttp.ClientPayloadError):
                                    await response.read()
                process.returncode = 1
                return b"", b""

            process.communicate = communicate
            return process

        with patch("asyncio.create_subprocess_exec", side_effect=spawn):
            # Use the absolute service reference when filename itself is relative.
            assert await extract_snapshot(client, {**MOVIE, "filename": "relative.ts"}) is None
    process.kill.assert_not_called()
    if mode in ("bad-range", "timeout"):
        assert not upstream_calls


@pytest.mark.parametrize("mode", ["cancel", "timeout", "missing-binary", "bad-output"])
async def test_decoder_failure_cleans_up_process(socket_enabled, mode):
    process = SimpleNamespace(returncode=None, kill=Mock(), wait=AsyncMock())
    started = asyncio.Event()
    relay_url = None

    async def spawn(*args, **kwargs):
        nonlocal relay_url
        relay_url = args[args.index("-i") + 1]
        if mode == "missing-binary":
            raise FileNotFoundError()

        async def communicate():
            started.set()
            if mode == "cancel":
                await asyncio.Event().wait()
            if mode == "timeout":
                raise TimeoutError()
            process.returncode = 0
            return b"not-a-jpeg", b""

        process.communicate = communicate
        return process

    async with aiohttp.ClientSession() as session:
        client = OpenWebifClient(session, "receiver.local")
        with patch("asyncio.create_subprocess_exec", side_effect=spawn):
            if mode == "cancel":
                task = asyncio.create_task(extract_snapshot(client, MOVIE))
                await asyncio.wait_for(started.wait(), 3)
                task.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await task
            else:
                assert await extract_snapshot(client, MOVIE) is None
        if mode in ("cancel", "timeout"):
            process.kill.assert_called_once()
            process.wait.assert_awaited_once()
        else:
            process.kill.assert_not_called()
        with pytest.raises(aiohttp.ClientConnectorError):
            await session.get(relay_url)
