# SPDX-License-Identifier: Apache-2.0
"""Extract one frame through a bounded, temporary loopback file relay."""

import asyncio
import re
from contextlib import suppress
from pathlib import PurePosixPath
from secrets import token_urlsafe

import aiohttp
from aiohttp import web

from .recordings import recording_path

MAX_VIDEO_BYTES = 64 * 1024 * 1024
SNAPSHOT_TIMEOUT = 45


def recording_duration(movie):
    """Return the duration actually reported for the recording file, if known."""
    parts = str(movie.get("length", "")).split(":")
    if len(parts) == 2 and all(part.isascii() and part.isdigit() for part in parts):
        length = int(parts[0]) * 60 + int(parts[1])
        if length > 0:
            return length
    return None


def snapshot_position(movie, minutes):
    position = float(minutes) * 60
    if (length := recording_duration(movie)) is not None and position >= length:
        return length / 2
    return position


async def extract_snapshot(client, movie, minutes=10, binary="ffmpeg"):
    """Seek on the file, keeping receiver credentials out of FFmpeg arguments/logs."""
    path = recording_path(movie)
    if not path.is_absolute():
        path = PurePosixPath(movie.get("serviceref", "").split(":", 10)[-1])
    if not path.is_absolute():
        return None
    file_url = client.base_url.with_path("/file").with_query(action="download", file=str(path))
    transferred = 0

    async def relay(request):
        nonlocal transferred
        headers = {**client.headers, "Accept-Encoding": "identity"}
        if byte_range := request.headers.get("Range"):
            if not re.fullmatch(r"bytes=(?:\d+-\d*|-\d+)", byte_range):
                raise web.HTTPBadRequest()
            headers["Range"] = byte_range
        try:
            async with client.session.request(
                request.method,
                file_url,
                headers=headers,
                ssl=client.verify_ssl,
                timeout=aiohttp.ClientTimeout(total=None, sock_connect=10, sock_read=10),
                allow_redirects=False,
            ) as upstream:
                if upstream.status not in (200, 206):
                    raise web.HTTPBadGateway()
                response = web.StreamResponse(
                    status=upstream.status,
                    headers={
                        key: upstream.headers[key]
                        for key in (
                            "Content-Length",
                            "Content-Range",
                            "Accept-Ranges",
                            "Content-Type",
                        )
                        if key in upstream.headers
                    },
                )
                await response.prepare(request)
                if request.method != "HEAD":
                    async for chunk in upstream.content.iter_chunked(64 * 1024):
                        transferred += len(chunk)
                        if transferred > MAX_VIDEO_BYTES:
                            response.force_close()
                            if request.transport:
                                request.transport.close()
                            break
                        await response.write(chunk)
                return response
        except aiohttp.ClientError, TimeoutError, ConnectionError:
            raise web.HTTPBadGateway() from None

    app = web.Application()
    token = token_urlsafe(24)
    app.router.add_get(f"/{token}", relay)
    runner = web.AppRunner(app, access_log=None, shutdown_timeout=1)
    process = None
    try:
        async with asyncio.timeout(SNAPSHOT_TIMEOUT):
            await runner.setup()
            await web.TCPSite(runner, "127.0.0.1", 0).start()
            port = runner.addresses[0][1]
            # No shell; only our loopback URL reaches the child process.
            process = await asyncio.create_subprocess_exec(
                binary,
                "-hide_banner",
                "-loglevel",
                "error",
                "-nostdin",
                "-protocol_whitelist",
                "http,tcp",
                "-rw_timeout",
                "10000000",
                "-ss",
                str(snapshot_position(movie, minutes)),
                "-i",
                f"http://127.0.0.1:{port}/{token}",
                "-map",
                "0:v:0",
                "-frames:v",
                "1",
                "-an",
                "-sn",
                "-dn",
                "-vf",
                "scale=640:640:force_original_aspect_ratio=decrease",
                "-threads",
                "1",
                "-f",
                "image2pipe",
                "-vcodec",
                "mjpeg",
                "pipe:1",
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )
            output, _ = await process.communicate()
            if process.returncode == 0 and output.startswith(b"\xff\xd8\xff"):
                return output
    except OSError, TimeoutError, ValueError:
        pass
    finally:
        if process and process.returncode is None:
            with suppress(ProcessLookupError):
                process.kill()
            await process.wait()
        await runner.cleanup()
    return None
