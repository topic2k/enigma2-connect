# SPDX-License-Identifier: Apache-2.0
"""Keyframe-aligned recording remux using Enigma2's compact access-point index."""

from __future__ import annotations

import math
import struct
from dataclasses import dataclass

from .stream_codec import encoding_args

MAX_INDEX_BYTES = 4 * 1024 * 1024
MAX_REMUX_BYTES = 16 * 1024 * 1024


@dataclass(frozen=True)
class RecordingRemux:
    """Immutable source timestamps; MPEG-TS wrap/discontinuities are rejected."""

    points: tuple[float, ...]
    origin: float
    copy_audio: bool
    preroll: float = 10

    @classmethod
    def parse(
        cls, data: bytes, size: int, start: float, duration: float, origin: float, copy_audio: bool
    ) -> RecordingRemux:
        if not (32 <= len(data) <= MAX_INDEX_BYTES and len(data) % 16 == 0):
            raise ValueError("Recording index invalid")
        if not all(math.isfinite(value) for value in (start, duration, origin)) or not (
            0 <= origin <= start < start + duration < (1 << 33) / 90000
        ):
            raise ValueError("Recording index timeline unsupported")
        previous_offset, previous_pts = -1, -1
        times = []
        for offset, pts in struct.iter_unpack(">QQ", data):
            if not (
                previous_offset < offset < size
                and offset % 188 == 0
                and previous_pts < pts < 1 << 33
                and (previous_pts < 0 or pts - previous_pts <= 900000)
            ):
                raise ValueError("Recording index timeline unsupported")
            times.append(pts / 90000)
            previous_offset, previous_pts = offset, pts
        end = start + duration
        if not (start - 0.001 <= times[0] <= start + 5 and end - 10 <= times[-1] < end):
            raise ValueError("Recording index does not match recording")
        points = [times[0]]
        for timestamp in times[1:]:
            if timestamp - points[-1] >= 6.4 and end - timestamp >= 1:
                points.append(timestamp)
        return cls(
            tuple([*points, end]),
            origin,
            copy_audio,
            max(2.0, max(b - a for a, b in zip(times, times[1:])) + 1),
        )

    @property
    def duration(self) -> float:
        return self.points[-1] - self.points[0]

    def arguments(self, index: int, url: str) -> list[str]:
        start, end = self.points[index : index + 2]
        seek = max(0.0, start - self.origin - self.preroll)
        # Half a 90 kHz tick avoids rounding a boundary packet into its neighbour.
        packet_filter = (
            f"noise=amount=0:drop='lt(pts*tb,{start - 0.000005:.6f})"
            f"+gte(pts*tb,{end - 0.000005:.6f})'"
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
            "-copyts",
            "-ss",
            f"{seek:.6f}",
            "-t",
            f"{end - self.origin - seek + 1:.6f}",
            "-f",
            "mpegts",
            "-i",
            url,
            *encoding_args(True, self.copy_audio),
            "-bsf:v",
            packet_filter,
            *([] if self.copy_audio else ["-af", f"atrim=start={start:.6f}:end={end:.6f}"]),
            "-bsf:a",
            packet_filter,
            "-output_ts_offset",
            f"{1 - self.points[0]:.6f}",
            "-muxdelay",
            "0",
            "-f",
            "mpegts",
            "pipe:1",
        ]
