# SPDX-License-Identifier: Apache-2.0
"""Seekable recording HLS with bounded, on-demand encoded segments."""

from __future__ import annotations

import asyncio
import json
import logging
import math
import re
from collections import OrderedDict
from contextlib import suppress
from pathlib import Path
from typing import TYPE_CHECKING, Any

import aiohttp

from .stream_codec import codec_details, copy_codecs, encoding_args, failure_reason
from .stream_remux import MAX_INDEX_BYTES, MAX_REMUX_BYTES, RecordingRemux

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)
# 6.4 s aligns 160 video frames (25 fps) and 300 AAC frames (48 kHz/1024).
SEGMENT_SECONDS = 6.4
MAX_DURATION = 24 * 3600
MAX_SEGMENT_BYTES = 4 * 1024 * 1024
CACHE_SEGMENTS = 8
MAX_PENDING = 4


class RecordingVOD:
    """A fixed recording timeline; only requested segments consume resources."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: aiohttp.ClientSession,
        binary: str,
        url: str,
        stream_id: str,
        *,
        compatible: bool = False,
    ) -> None:
        self.hass = hass
        self.client = client
        self.binary = binary
        self.url = url  # Private loopback URL, never the authenticated receiver URL.
        self.stream_id = stream_id
        self.duration = 0.0
        self.size = 0
        self.cache: OrderedDict[int, bytes] = OrderedDict()
        self.pending: dict[int, asyncio.Task[bytes | None]] = {}
        self.encoder = asyncio.Semaphore(1)
        self.closed = False
        self.packet_filter = False
        self.compatible = compatible
        self.remux: RecordingRemux | None = None
        self.processing = "recording_vod+encode_video+encode_audio"

    async def _size(self) -> int:
        async with self.client.get(
            self.url,
            headers={"Range": "bytes=0-0", "Accept-Encoding": "identity"},
            allow_redirects=False,
            timeout=aiohttp.ClientTimeout(total=5),
        ) as response:
            match = re.fullmatch(
                r"bytes 0-0/([1-9][0-9]*)", response.headers.get("Content-Range", "")
            )
            if response.status != 206 or not match or response.headers.get("Content-Length") != "1":
                raise ValueError("Recording byte ranges unavailable")
            return int(match[1])

    async def _run(self, binary: str, args: list[str], limit: int) -> bytes:
        process = await asyncio.create_subprocess_exec(
            binary,
            *args,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        try:
            assert process.stdout
            output = bytearray()
            while chunk := await process.stdout.read(min(65536, limit + 1 - len(output))):
                output.extend(chunk)
                if len(output) > limit:
                    raise ValueError("Recording output limit exceeded")
            await process.wait()
            if process.returncode or not output:
                _LOGGER.debug(
                    "[stream=%s] VOD subprocess failed: exit=%s empty=%s",
                    self.stream_id,
                    process.returncode,
                    not output,
                )
                raise ValueError("Recording conversion failed")
            return bytes(output)
        finally:
            if process.returncode is None:
                with suppress(ProcessLookupError):
                    process.kill()
            await process.communicate()

    async def prepare(self) -> None:
        """Require byte seeking and a bounded duration before promising VOD."""
        self.size = await self._size()
        path = Path(self.binary)
        name = "ffprobe.exe" if path.name.lower().endswith(".exe") else "ffprobe"
        executable = str(path.with_name(name)) if path.parent != Path(".") else name
        async with asyncio.timeout(10):
            output = await self._run(
                executable,
                [
                    "-v",
                    "error",
                    "-protocol_whitelist",
                    "http,tcp",
                    "-rw_timeout",
                    "5000000",
                    "-f",
                    "mpegts",
                    "-i",
                    self.url,
                    "-show_entries",
                    "format=duration,start_time:stream=duration,start_time,codec_type,codec_name,profile,width,height,avg_frame_rate,bit_rate,channels,sample_rate,pix_fmt,field_order,level",
                    "-of",
                    "json",
                ],
                65536,
            )
        metadata = json.loads(output)
        if not isinstance(metadata, dict):
            raise ValueError("Recording metadata unavailable")
        streams = metadata.get("streams", [])
        if not isinstance(streams, list) or not all(isinstance(item, dict) for item in streams):
            raise ValueError("Recording video unavailable")
        video: dict[str, Any] = next(
            (item for item in streams if item.get("codec_type") == "video"), {}
        )
        if not video:
            raise ValueError("Recording video unavailable")
        raw_duration = video.get("duration")
        if raw_duration in (None, "N/A"):
            raw_duration = metadata.get("format", {}).get("duration", 0)
        duration = float(raw_duration)
        if not math.isfinite(duration) or not 0 < duration <= MAX_DURATION:
            raise ValueError("Recording duration unavailable")
        source_duration = duration
        # Container duration may include a trailing audio packet past the video.
        # Never advertise an extra segment shorter than one output video frame.
        if duration >= SEGMENT_SECONDS and 0 < duration % SEGMENT_SECONDS < 1 / 25:
            duration -= duration % SEGMENT_SECONDS
        if self.size != await self._size():
            raise ValueError("Recording size changed")
        self.duration = duration
        _LOGGER.debug(
            "[stream=%s] Input recording_vod: container=mpegts duration=%.3f video=%s audio=%s",
            self.stream_id,
            duration,
            codec_details(streams, "video"),
            codec_details(streams, "audio"),
        )
        try:
            async with asyncio.timeout(2):
                capabilities = await self._run(
                    self.binary, ["-hide_banner", "-h", "bsf=noise"], 65536
                )
                self.packet_filter = b"drop" in capabilities
        except OSError, TimeoutError, ValueError:
            self.packet_filter = False
        # A compact receiver index gives exact copy boundaries without scanning the TS.
        copy_video, copy_audio = copy_codecs(streams)
        if copy_video and not self.compatible:
            try:
                if not self.packet_filter:
                    raise ValueError("Recording packet filter unavailable")
                async with self.client.get(
                    self.url + "/index",
                    allow_redirects=False,
                    timeout=aiohttp.ClientTimeout(total=5),
                ) as response:
                    if response.status != 200:
                        raise ValueError("Recording index unavailable")
                    data = bytearray()
                    async for chunk in response.content.iter_chunked(65536):
                        data.extend(chunk)
                        if len(data) > MAX_INDEX_BYTES:
                            raise ValueError("Recording index invalid")
                self.remux = RecordingRemux.parse(
                    bytes(data),
                    self.size,
                    float(video["start_time"]),
                    source_duration,
                    float(metadata["format"]["start_time"]),
                    copy_audio,
                )
                self.duration = self.remux.duration
                await self.read("segment00000000.ts")
                self.processing = "recording_vod+copy_video+" + (
                    "copy_audio" if copy_audio else "encode_audio"
                )
            except (
                aiohttp.ClientError,
                OSError,
                TimeoutError,
                ValueError,
                KeyError,
                TypeError,
            ) as error:
                _LOGGER.debug(
                    "[stream=%s] VOD remux unavailable: %s", self.stream_id, failure_reason(error)
                )
                self.remux = None
                self.duration = duration
                self.cache.clear()
        _LOGGER.debug(
            "[stream=%s] HA VOD output: processing=%s video=%s audio=%s",
            self.stream_id,
            self.processing,
            "source_copy"
            if self.remux
            else "h264/main level=3.1 bounds=1280x720 fps=25 target=2000k maxrate=2500k",
            "source_copy_or_absent"
            if self.remux and self.remux.copy_audio
            else "AAC stereo 48000Hz 128k",
        )
        # Validate real rendering before returning a complete timeline to the player.
        await self.read("segment00000000.ts")

    @property
    def segment_count(self) -> int:
        return (
            len(self.remux.points) - 1 if self.remux else math.ceil(self.duration / SEGMENT_SECONDS)
        )

    def segment_duration(self, index: int) -> float:
        if self.remux:
            return self.remux.points[index + 1] - self.remux.points[index]
        return min(SEGMENT_SECONDS, self.duration - index * SEGMENT_SECONDS)

    def playlist(self) -> bytes:
        lines = [
            "#EXTM3U",
            "#EXT-X-VERSION:3",
            f"#EXT-X-TARGETDURATION:{math.ceil(max(self.segment_duration(i) for i in range(self.segment_count)))}",
            "#EXT-X-MEDIA-SEQUENCE:0",
            "#EXT-X-PLAYLIST-TYPE:VOD",
            "#EXT-X-INDEPENDENT-SEGMENTS",
        ]
        for index in range(self.segment_count):
            seconds = self.segment_duration(index)
            lines.extend([f"#EXTINF:{seconds:.6f},", f"segment{index:08d}.ts"])
        return ("\n".join([*lines, "#EXT-X-ENDLIST", ""])).encode()

    async def read(self, filename: str) -> bytes:
        if self.closed:
            raise FileNotFoundError()
        if filename == "index.m3u8":
            return self.playlist()
        match = re.fullmatch(r"segment([0-9]{8,})\.ts", filename)
        if not match or int(match[1]) >= self.segment_count:
            raise FileNotFoundError()
        index = int(match[1])
        if index in self.cache:
            self.cache.move_to_end(index)
            return self.cache[index]
        if index not in self.pending:
            if len(self.pending) >= MAX_PENDING:
                raise ValueError("Recording request queue full")
            self.pending[index] = self.hass.async_create_background_task(
                self._render(index),
                f"enigma2_connect VOD segment {index}",
                eager_start=False,
            )
        result = await asyncio.shield(self.pending[index])
        if result is None:
            raise ValueError("Recording segment unavailable")
        return result

    def _encode_arguments(self, index: int) -> list[str]:
        start = round(index * SEGMENT_SECONDS, 6)
        seconds = min(SEGMENT_SECONDS, self.duration - start)
        seek = max(0.0, round(start - 10, 6))
        trim = round(start - seek, 6)
        args = encoding_args(False, False)
        args[args.index("-vf") + 1] = (
            f"trim=start={trim}:duration={seconds:.6f},setpts=PTS-{trim}/TB,fps=25:start_time=0,"
            + args[args.index("-vf") + 1]
        )
        args.extend(
            [
                "-af",
                f"atrim=start={trim}:duration={seconds:.6f},asetpts=PTS-{trim}/TB,aresample=48000:async=1:first_pts=0",
            ]
        )
        _LOGGER.debug(
            "[stream=%s] VOD render: segment=%s start=%s duration=%.3f",
            self.stream_id,
            index,
            start,
            seconds,
        )
        return [
            "-hide_banner",
            "-loglevel",
            "error",
            "-nostdin",
            "-protocol_whitelist",
            "http,tcp",
            "-rw_timeout",
            "5000000",
            "-ss",
            str(seek),
            "-f",
            "mpegts",
            "-i",
            self.url,
            "-t",
            f"{seconds:.6f}",
            *args,
            "-frames:v",
            str(max(1, round(seconds * 25))),
            "-frames:a",
            str(max(1, math.ceil(seconds * 48000 / 1024 - 1e-6))),
            # Newer FFmpeg counts encoder input frames and may flush an extra AAC packet.
            # Keep the same bounded output packet count as older versions.
            *(
                [
                    "-bsf:a",
                    f"noise=amount=0:drop='gte(n,{max(1, math.ceil(seconds * 48000 / 1024 - 1e-6))})'",
                ]
                if self.packet_filter
                else []
            ),
            "-output_ts_offset",
            str(start + 1),
            "-muxdelay",
            "0",
            "-f",
            "mpegts",
            "pipe:1",
        ]

    async def _render(self, index: int) -> bytes | None:
        try:
            async with self.encoder, asyncio.timeout(20):
                if self.size != await self._size():
                    raise ValueError("Recording size changed")
                if self.remux:
                    _LOGGER.debug(
                        "[stream=%s] VOD remux: segment=%s start=%.3f duration=%.3f",
                        self.stream_id,
                        index,
                        self.remux.points[index] - self.remux.points[0],
                        self.segment_duration(index),
                    )
                data = await self._run(
                    self.binary,
                    self.remux.arguments(index, self.url)
                    if self.remux
                    else self._encode_arguments(index),
                    MAX_REMUX_BYTES if self.remux else MAX_SEGMENT_BYTES,
                )
                self.cache[index] = data
                while (
                    len(self.cache) > CACHE_SEGMENTS
                    or sum(map(len, self.cache.values())) > CACHE_SEGMENTS * MAX_SEGMENT_BYTES
                ):
                    self.cache.popitem(last=False)
                return data
        except (aiohttp.ClientError, OSError, TimeoutError, ValueError) as error:
            _LOGGER.debug(
                "[stream=%s] VOD render failed: segment=%s reason=%s",
                self.stream_id,
                index,
                failure_reason(error),
            )
            return None
        finally:
            self.pending.pop(index, None)

    async def async_close(self) -> None:
        self.closed = True
        tasks = list(self.pending.values())
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        self.pending.clear()
        self.cache.clear()
