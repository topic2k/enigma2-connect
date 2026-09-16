# SPDX-License-Identifier: Apache-2.0
"""Conservative browser codec selection with a cancellable, bounded probe."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from contextlib import suppress
from pathlib import Path
from typing import Any

_LOGGER = logging.getLogger(__name__)
_FIELDS = (
    "codec_name",
    "profile",
    "pix_fmt",
    "field_order",
    "level",
    "width",
    "height",
    "avg_frame_rate",
    "bit_rate",
    "channels",
    "sample_rate",
)


def codec_details(streams: list[dict[str, Any]], kind: str) -> dict[str, str]:
    """Log only bounded technical fields, never tags, titles or source URLs."""
    track = next((item for item in streams if item.get("codec_type") == kind), {})
    return (
        {
            key: value if re.fullmatch(r"[A-Za-z0-9 ._/()-]{1,64}", value) else "unknown"
            for key in _FIELDS
            if (value := str(track.get(key, "unknown")))
        }
        if track
        else {"track": "absent"}
    )


def failure_reason(error: Exception) -> str:
    """Only known local validation messages are safe; exceptions may contain URLs."""
    known = {
        "Invalid receiver stream address",
        "Unexpected receiver response",
        "Receiver response exceeds limit",
        "Receiver HLS unavailable",
        "Receiver playlist unavailable",
        "Unexpected receiver playlist",
        "No separate transcoded source",
        "Not an HLS playlist",
        "Unsupported HLS tag",
        "Unsupported HLS segment",
        "Unsupported HLS window",
        "Receiver HLS does not support required HTTPS",
        "Receiver transcoding does not support required HTTPS",
        "Stream did not start",
        "Recording byte ranges unavailable",
        "Recording output limit exceeded",
        "Recording conversion failed",
        "Recording metadata unavailable",
        "Recording duration unavailable",
        "Recording video unavailable",
        "Recording size changed",
        "Recording segment unavailable",
        "Recording index unavailable",
        "Recording packet filter unavailable",
        "Recording index invalid",
        "Recording index timeline unsupported",
        "Recording index does not match recording",
    }
    message = str(error)
    return message if type(error) is ValueError and message in known else type(error).__name__


def copy_codecs(streams: list[dict[str, Any]]) -> tuple[bool, bool]:
    """Keep only widely supported progressive H.264 and AAC-LC stereo."""
    video = next((item for item in streams if item.get("codec_type") == "video"), {})
    audio = next((item for item in streams if item.get("codec_type") == "audio"), {})
    return (
        video.get("codec_name") == "h264"
        and video.get("pix_fmt") == "yuv420p"
        and video.get("profile") in ("Constrained Baseline", "Baseline", "Main", "High")
        and video.get("field_order") == "progressive"
        and 0 < video.get("level", 0) <= 42,
        not audio
        or (
            audio.get("codec_name") == "aac"
            and audio.get("profile") == "LC"
            and 0 < audio.get("channels", 0) <= 2
            and str(audio.get("sample_rate")) in ("44100", "48000")
        ),
    )


async def probe(
    binary: str, url: str, *, stream_id: str = "unassigned", stage: str = "source"
) -> tuple[bool, bool]:
    """Inspect only our private MPEG-TS relay; never give ffprobe receiver URLs."""
    path = Path(binary)
    name = "ffprobe.exe" if path.name.lower().endswith(".exe") else "ffprobe"
    executable = str(path.with_name(name)) if path.parent != Path(".") else name
    process = None
    try:
        process = await asyncio.create_subprocess_exec(
            executable,
            "-v",
            "error",
            "-protocol_whitelist",
            "http,tcp",
            "-rw_timeout",
            "4000000",
            "-analyzeduration",
            "2000000",
            "-probesize",
            "2000000",
            "-f",
            "mpegts",
            "-i",
            url,
            "-show_entries",
            "stream=codec_type," + ",".join(_FIELDS),
            "-of",
            "json",
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        async with asyncio.timeout(6):
            assert process.stdout
            output = bytearray()
            while chunk := await process.stdout.read(65537 - len(output)):
                output.extend(chunk)
                if len(output) > 65536:
                    _LOGGER.debug("[stream=%s] Probe %s failed: output_limit", stream_id, stage)
                    return False, False
            await process.wait()
        if process.returncode:
            _LOGGER.debug(
                "[stream=%s] Probe %s failed: exit_code=%s", stream_id, stage, process.returncode
            )
            return False, False
        streams = json.loads(output).get("streams", [])
        if not isinstance(streams, list) or not all(isinstance(item, dict) for item in streams):
            _LOGGER.debug("[stream=%s] Probe %s failed: invalid_streams", stream_id, stage)
            return False, False
        _LOGGER.debug(
            "[stream=%s] Input %s: container=mpegts video=%s audio=%s",
            stream_id,
            stage,
            codec_details(streams, "video"),
            codec_details(streams, "audio"),
        )
        if not any(item.get("codec_type") == "video" for item in streams):
            _LOGGER.debug("[stream=%s] Probe %s failed: no_video", stream_id, stage)
            return False, False
        result = copy_codecs(streams)
        _LOGGER.debug(
            "[stream=%s] Copy compatibility %s: video=%s audio=%s", stream_id, stage, *result
        )
        return result
    except (OSError, TimeoutError, ValueError, TypeError, AttributeError) as error:
        _LOGGER.debug("[stream=%s] Probe %s failed: %s", stream_id, stage, failure_reason(error))
        return False, False
    finally:
        if process:
            if process.returncode is None:
                with suppress(ProcessLookupError):
                    process.kill()
            # Drain remaining pipe data after killing a timed-out/oversized probe.
            # wait() alone can hang while asyncio has paused a full stdout pipe.
            await process.communicate()


def encoding_args(copy_video: bool, copy_audio: bool) -> list[str]:
    """Shared track mapping and browser-compatible output settings."""
    return [
        "-map",
        "0:v:0",
        "-map",
        "0:a:0?",
        "-sn",
        "-dn",
        *(
            ["-c:v", "copy"]
            if copy_video
            else [
                "-vf",
                "yadif,scale=1280:720:force_original_aspect_ratio=decrease:force_divisible_by=2",
                "-r",
                "25",
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-pix_fmt",
                "yuv420p",
                "-profile:v",
                "main",
                "-level:v",
                "3.1",
                "-b:v",
                "2000k",
                "-maxrate",
                "2500k",
                "-bufsize",
                "5000k",
                "-threads",
                "2",
                "-g",
                "50",
                "-keyint_min",
                "50",
                "-sc_threshold",
                "0",
            ]
        ),
        *(
            ["-c:a", "copy"]
            if copy_audio
            else [
                "-c:a",
                "aac",
                "-b:a",
                "128k",
                "-ac",
                "2",
                "-ar",
                "48000",
            ]
        ),
    ]
