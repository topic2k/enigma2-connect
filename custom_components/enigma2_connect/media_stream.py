# SPDX-License-Identifier: Apache-2.0
"""Bounded HLS playback with a private, authenticated receiver relay."""

from __future__ import annotations

import asyncio
import logging
import re
from contextlib import suppress
from pathlib import Path
from secrets import compare_digest, token_urlsafe
from tempfile import TemporaryDirectory
from time import monotonic
from typing import TYPE_CHECKING
from uuid import uuid4

import aiohttp
from aiohttp import web
from homeassistant.components.media_source import PlayMedia, Unresolvable
from homeassistant.config_entries import ConfigEntryState
from homeassistant.helpers.http import HomeAssistantView
from yarl import URL

from .const import DOMAIN
from .recording_management import reference_path
from .stream_codec import encoding_args, failure_reason, probe
from .stream_receiver import ReceiverHLS, discover_hls, discover_transcoded
from .stream_vod import RecordingVOD

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from homeassistant.core import HomeAssistant

    from .coordinator import EnigmaCoordinator

CONF_EXTERNAL_PLAYBACK = "external_playback"
CONF_STREAM_PORT = "stream_port"
CONF_STREAM_HTTPS = "stream_https"
CONF_STREAM_MODE = "stream_mode"
CONF_STREAM_LIMIT = "stream_limit"
DEFAULT_STREAM_LIMIT = 5
_LOGGER = logging.getLogger(__name__)
START_TIMEOUT = 30
IDLE_TIMEOUT = 120
MAX_LIFETIME = 6 * 3600
# HA's media dialog selects ha-hls-player only for this exact MIME spelling.
HLS_MIME = "application/x-mpegURL"


class StreamSession:
    """One independent playback session; MediaStream manages admission and sharing."""

    def __init__(self, hass: HomeAssistant, coordinator: EnigmaCoordinator) -> None:
        self.hass = hass
        self.coordinator = coordinator
        self.stream_id = uuid4().hex[:12]
        self.token = ""
        self.directory: TemporaryDirectory[str] | None = None
        self.process: asyncio.subprocess.Process | None = None
        self.runner: web.AppRunner | None = None
        self.watcher: asyncio.Task[None] | None = None
        self.lock = asyncio.Lock()
        self.remote: ReceiverHLS | None = None
        self.vod: RecordingVOD | None = None
        self.processing = ""
        self.closed = False
        self.touched = self.started = 0.0

    def media(self) -> PlayMedia:
        return PlayMedia(
            f"/api/{DOMAIN}/stream/{self.coordinator.entry.entry_id}/{self.token}/index.m3u8",
            HLS_MIME,
        )

    async def async_play(self, source: URL, *, recording: bool) -> PlayMedia:
        async with self.lock:
            if self.closed or not self.coordinator.entry.options.get(CONF_EXTERNAL_PLAYBACK, False):
                raise Unresolvable(translation_domain=DOMAIN, translation_key="stream_disabled")
            await self._cleanup()
            compatible = self.coordinator.entry.options.get(CONF_STREAM_MODE) == "compatible"
            _LOGGER.debug(
                "[stream=%s] Start requested: kind=%s mode=%s",
                self.stream_id,
                "recording" if recording else "live",
                "compatible" if compatible else "auto",
            )
            for force in [True] if compatible else [False, True]:
                try:
                    async with asyncio.timeout(START_TIMEOUT):
                        await self._start(source, recording=recording, compatible=force)
                        if not self.remote and not self.vod:
                            assert self.directory and self.process
                            playlist = Path(self.directory.name) / "index.m3u8"
                            while not await self.hass.async_add_executor_job(playlist.is_file):
                                if self.process.returncode is not None:
                                    raise OSError("Stream did not start")
                                await asyncio.sleep(0.2)
                    self.started = self.touched = monotonic()
                    self.watcher = self.hass.async_create_background_task(
                        self._watch(), f"{DOMAIN} HLS cleanup"
                    )
                    _LOGGER.debug(
                        "[stream=%s] Started: processing=%s output=HLS/MPEG-TS variants=1",
                        self.stream_id,
                        self.processing,
                    )
                    return self.media()
                except (OSError, TimeoutError) as error:
                    _LOGGER.debug(
                        "[stream=%s] Start failed: mode=%s reason=%s",
                        self.stream_id,
                        "compatible" if force else "auto",
                        failure_reason(error),
                    )
                    await self._cleanup()
                    if force:
                        raise Unresolvable(
                            translation_domain=DOMAIN, translation_key="stream_failed"
                        ) from None
                    _LOGGER.debug("[stream=%s] Retrying compatibility mode", self.stream_id)
                except asyncio.CancelledError:
                    _LOGGER.debug("[stream=%s] Start cancelled", self.stream_id)
                    await self._cleanup()
                    raise
            raise AssertionError("No streaming attempt")

    async def _loopback(self, source: URL) -> str:
        if self.runner:
            await self.runner.cleanup()
        app = web.Application()
        private_path = f"/{token_urlsafe(32)}"
        app.router.add_get(private_path, self._relay_handler(source))
        if source.path == "/file" and source.query.get("file", "").endswith(".ts"):
            app.router.add_get(
                private_path + "/index",
                self._relay_handler(source.update_query(file=source.query["file"] + ".ap")),
            )
        self.runner = web.AppRunner(app, access_log=None, shutdown_timeout=1)
        await self.runner.setup()
        await web.TCPSite(self.runner, "127.0.0.1", 0).start()
        port = self.runner.addresses[0][1]
        route = next(iter(app.router.resources())).canonical
        return f"http://127.0.0.1:{port}{route}"

    async def _start(self, source: URL, *, recording: bool, compatible: bool = False) -> None:
        self.token = token_urlsafe(32)
        manager = self.hass.data.get("ffmpeg")
        binary = manager.binary if manager else "ffmpeg"
        client = self.coordinator.client
        if recording:
            self.vod = RecordingVOD(
                self.hass,
                client.session,
                binary,
                await self._loopback(source),
                self.stream_id,
                compatible=compatible,
            )
            try:
                async with asyncio.timeout(20):
                    await self.vod.prepare()
            except (
                aiohttp.ClientError,
                OSError,
                TimeoutError,
                ValueError,
                TypeError,
                AttributeError,
            ) as error:
                _LOGGER.debug(
                    "[stream=%s] VOD unavailable; using bounded playback: %s",
                    self.stream_id,
                    failure_reason(error),
                )
                await self.vod.async_close()
                self.vod = None
            else:
                self.processing = self.vod.processing
                return
        copy_video = copy_audio = False
        receiver_transcoding = False
        if not compatible and not recording:
            try:
                hls_source = await discover_hls(client, source.path.lstrip("/"))
                if source.scheme == "https" and hls_source.scheme != "https":
                    raise ValueError("Receiver HLS does not support required HTTPS")
                remote = ReceiverHLS(client, hls_source)
                await remote.playlist()
                assert remote.first_segment
                if all(
                    await probe(
                        binary,
                        await self._loopback(remote.first_segment),
                        stream_id=self.stream_id,
                        stage="receiver_hls",
                    )
                ):
                    assert self.runner
                    await self.runner.cleanup()
                    self.runner = None
                    self.remote = remote
                    self.processing = "receiver_hls"
                    return
                _LOGGER.debug(
                    "[stream=%s] Receiver HLS rejected: incompatible_or_unknown_codecs",
                    self.stream_id,
                )
            except (aiohttp.ClientError, OSError, TimeoutError, ValueError) as error:
                _LOGGER.debug(
                    "[stream=%s] Receiver HLS unavailable: %s",
                    self.stream_id,
                    failure_reason(error),
                )
        local_url = await self._loopback(source)
        if not compatible:
            copy_video, copy_audio = await probe(
                binary, local_url, stream_id=self.stream_id, stage="original"
            )
            if not recording and not (copy_video and copy_audio):
                try:
                    candidate = await discover_transcoded(client, source)
                    if source.scheme == "https" and candidate.scheme != "https":
                        raise ValueError("Receiver transcoding does not support required HTTPS")
                    candidate_url = await self._loopback(candidate)
                    candidate_video, candidate_audio = await probe(
                        binary,
                        candidate_url,
                        stream_id=self.stream_id,
                        stage="receiver_transcoding",
                    )
                    # Never trade a compatible original video for software encoding.
                    if candidate_video and (candidate_audio or not copy_video):
                        source = candidate
                        copy_video, copy_audio = candidate_video, candidate_audio
                        receiver_transcoding = True
                    else:
                        _LOGGER.debug(
                            "[stream=%s] Receiver transcoding rejected: no_compatible_improvement",
                            self.stream_id,
                        )
                except (aiohttp.ClientError, OSError, TimeoutError, ValueError) as error:
                    _LOGGER.debug(
                        "[stream=%s] Receiver transcoding unavailable: %s",
                        self.stream_id,
                        failure_reason(error),
                    )
                local_url = await self._loopback(source)
        else:
            _LOGGER.debug(
                "[stream=%s] Input original: not_probed (compatibility mode)", self.stream_id
            )
        _LOGGER.debug(
            "[stream=%s] HA output: video=%s audio=%s",
            self.stream_id,
            "source_copy"
            if copy_video
            else "h264/main level=3.1 bounds=1280x720 fps=25 target=2000k maxrate=2500k",
            "source_copy_or_absent"
            if copy_audio
            else "aac channels=2 sample_rate=48000 bitrate=128k",
        )
        self.processing = (
            ("receiver_transcoding+" if receiver_transcoding else "")
            + ("copy_video" if copy_video else "encode_video")
            + ("+copy_audio" if copy_audio else "+encode_audio")
        )
        self.directory = await self.hass.async_add_executor_job(TemporaryDirectory)
        # Neither credentials nor receiver addresses reach FFmpeg or its logs.
        self.process = await asyncio.create_subprocess_exec(
            binary,
            "-hide_banner",
            "-loglevel",
            "error",
            "-nostdin",
            "-protocol_whitelist",
            "http,tcp",
            "-rw_timeout",
            "10000000",
            *(["-re"] if recording else []),
            "-f",
            "mpegts",
            "-i",
            local_url,
            *encoding_args(copy_video, copy_audio),
            "-f",
            "hls",
            "-hls_time",
            "2",
            "-hls_list_size",
            "8",
            "-hls_flags",
            "delete_segments+temp_file+independent_segments",
            "-hls_segment_filename",
            str(Path(self.directory.name) / "segment%08d.ts"),
            str(Path(self.directory.name) / "index.m3u8"),
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )

    def _relay_handler(self, source: URL) -> Callable[[web.Request], Awaitable[web.StreamResponse]]:
        async def relay(request: web.Request) -> web.StreamResponse:
            client = self.coordinator.client
            headers = {**client.headers, "Accept-Encoding": "identity"}
            if byte_range := request.headers.get("Range"):
                if not re.fullmatch(r"bytes=(?:\d+-\d*|-\d+)", byte_range):
                    raise web.HTTPBadRequest()
                headers["Range"] = byte_range
            try:
                async with client.session.request(
                    request.method,
                    source,
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
                            for key in ("Content-Length", "Content-Range", "Accept-Ranges")
                            if key in upstream.headers
                        },
                    )
                    await response.prepare(request)
                    if request.method != "HEAD":
                        async for chunk in upstream.content.iter_chunked(64 * 1024):
                            await response.write(chunk)
                    return response
            except aiohttp.ClientError, TimeoutError, ConnectionError:
                raise web.HTTPBadGateway() from None

        return relay

    def expired(self) -> bool:
        now = monotonic()
        return now - self.touched > IDLE_TIMEOUT or now - self.started > MAX_LIFETIME

    async def _watch(self) -> None:
        while True:
            await asyncio.sleep(15)
            async with self.lock:
                expired = self.expired()
                if expired or (self.process and self.process.returncode not in (None, 0)):
                    _LOGGER.debug(
                        "[stream=%s] Stopping: expired=%s process_exit=%s",
                        self.stream_id,
                        expired,
                        self.process.returncode if self.process else None,
                    )
                    await self._cleanup()
                    return

    async def _cleanup(self) -> None:
        if self.token:
            _LOGGER.debug("[stream=%s] Releasing playback resources", self.stream_id)
        self.token = ""
        self.remote = None
        if self.vod:
            await self.vod.async_close()
            self.vod = None
        self.processing = ""
        if self.watcher and self.watcher is not asyncio.current_task():
            self.watcher.cancel()
            await asyncio.gather(self.watcher, return_exceptions=True)
        self.watcher = None
        if self.process:
            if self.process.returncode is None:
                with suppress(ProcessLookupError):
                    self.process.kill()
            await self.process.wait()
            self.process = None
        if self.runner:
            await self.runner.cleanup()
            self.runner = None
        if self.directory:
            await self.hass.async_add_executor_job(self.directory.cleanup)
            self.directory = None

    async def async_close(self) -> None:
        async with self.lock:
            self.closed = True
            await self._cleanup()


class MediaStream:
    """Per-receiver stream pool; reserve slots before asynchronous startup."""

    def __init__(self, hass: HomeAssistant, coordinator: EnigmaCoordinator) -> None:
        self.hass = hass
        self.coordinator = coordinator
        self.sessions: dict[StreamSession, tuple[URL, bool]] = {}
        self.pending: dict[StreamSession, asyncio.Task[PlayMedia]] = {}
        self.lock = asyncio.Lock()
        self.closed = False

    def find(self, token: str) -> StreamSession | None:
        return next(
            (
                session
                for session in self.sessions
                if session.token and compare_digest(token.encode(), session.token.encode())
            ),
            None,
        )

    def recording_in_use(self, service_reference: str) -> bool:
        """Caller holds admission lock; include already reserved starting streams."""
        target = reference_path(service_reference)
        return any(
            recording
            and (not source.query.get("file") or reference_path(source.query["file"]) == target)
            for source, recording in self.sessions.values()
        )

    async def _prune(self) -> None:
        stale = [
            session
            for session in self.sessions
            if session not in self.pending
            and (
                not session.token
                or session.expired()
                or (session.process and session.process.returncode not in (None, 0))
            )
        ]
        for session in stale:
            _LOGGER.debug("[stream=%s] Releasing stale pool slot", session.stream_id)
            await session.async_close()
            self.sessions.pop(session, None)

    async def async_play(self, source: URL, *, recording: bool) -> PlayMedia:
        async with self.lock:
            if self.closed or not self.coordinator.entry.options.get(CONF_EXTERNAL_PLAYBACK, False):
                raise Unresolvable(translation_domain=DOMAIN, translation_key="stream_disabled")
            if recording and self.coordinator.recording_manager.blocks_stream(
                source.query.get("file")
            ):
                raise Unresolvable(translation_domain=DOMAIN, translation_key="recording_pending")
            await self._prune()
            shared = next(
                (
                    session
                    for session, key in self.sessions.items()
                    if not recording and key == (source, False)
                ),
                None,
            )
            if shared:
                _LOGGER.debug(
                    "[stream=%s] Live request shared: starting=%s",
                    shared.stream_id,
                    shared in self.pending,
                )
                if shared not in self.pending:
                    shared.touched = monotonic()
                    return shared.media()
                task = self.pending[shared]
            else:
                limit = self.coordinator.entry.options.get(CONF_STREAM_LIMIT, DEFAULT_STREAM_LIMIT)
                if limit and len(self.sessions) >= limit:
                    _LOGGER.debug(
                        "Stream request rejected: reason=stream_limit active=%s limit=%s",
                        len(self.sessions),
                        limit,
                    )
                    raise Unresolvable(
                        translation_domain=DOMAIN,
                        translation_key="stream_limit_reached",
                        translation_placeholders={"limit": str(limit)},
                    )
                session = StreamSession(self.hass, self.coordinator)
                self.sessions[session] = (source, recording)
                _LOGGER.debug(
                    "[stream=%s] Pool slot reserved: active=%s limit=%s",
                    session.stream_id,
                    len(self.sessions),
                    limit,
                )
                task = self.hass.async_create_background_task(
                    self._start_session(session, source, recording=recording),
                    f"{DOMAIN} stream startup",
                    eager_start=False,
                )
                self.pending[session] = task
        # One cancelled resolver must not cancel startup for another viewer.
        # An abandoned startup is bounded by the session's startup/idle timeouts.
        return await asyncio.shield(task)

    async def _start_session(
        self, session: StreamSession, source: URL, *, recording: bool
    ) -> PlayMedia:
        try:
            return await session.async_play(source, recording=recording)
        except Exception, asyncio.CancelledError:
            await session.async_close()
            self.sessions.pop(session, None)
            raise
        finally:
            self.pending.pop(session, None)

    async def async_close(self) -> None:
        async with self.lock:
            self.closed = True
            tasks = list(self.pending.values())
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            await asyncio.gather(*(session.async_close() for session in list(self.sessions)))
            self.sessions.clear()
            self.pending.clear()


class MediaStreamView(HomeAssistantView):
    url = f"/api/{DOMAIN}/stream/{{entry_id}}/{{token}}/{{filename}}"
    name = f"api:{DOMAIN}:stream"
    # Browser/Cast requests use a random, expiring capability issued only by
    # authenticated media-source resolution, including for every segment.
    requires_auth = False
    cors_allowed = True

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    async def get(
        self, request: web.Request, entry_id: str, token: str, filename: str
    ) -> web.Response:
        entry = self.hass.config_entries.async_get_entry(entry_id)
        if (
            not entry
            or entry.domain != DOMAIN
            or entry.state is not ConfigEntryState.LOADED
            or not entry.options.get(CONF_EXTERNAL_PLAYBACK, False)
        ):
            raise web.HTTPNotFound()
        stream = entry.runtime_data.media_stream.find(token)
        if (
            not stream
            or not stream.token
            or not compare_digest(token.encode(), stream.token.encode())
            or stream.expired()
            or not (stream.directory or stream.remote or stream.vod)
            or not re.fullmatch(
                r"index\.m3u8|segment[0-9]{8,}\.ts|remote[0-9a-f]{64}\.ts", filename
            )
        ):
            raise web.HTTPNotFound()
        try:
            if stream.vod:
                content = await stream.vod.read(filename)
            elif stream.remote:
                content = await stream.remote.read(filename)
            else:
                assert stream.directory
                content = await self.hass.async_add_executor_job(
                    (Path(stream.directory.name) / filename).read_bytes
                )
            # This session may have expired or been closed while upstream I/O ran.
            if not compare_digest(token.encode(), stream.token.encode()):
                raise web.HTTPNotFound()
        except OSError:
            raise web.HTTPNotFound() from None
        except aiohttp.ClientError, TimeoutError, ValueError:
            raise web.HTTPBadGateway() from None
        stream.touched = monotonic()
        return web.Response(
            body=content,
            content_type=HLS_MIME if filename == "index.m3u8" else "video/mp2t",
            headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"},
        )

    head = get
