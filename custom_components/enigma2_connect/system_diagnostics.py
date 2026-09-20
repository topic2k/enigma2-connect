# SPDX-License-Identifier: Apache-2.0
"""Normalize optional OpenWebif about measurements without guessing missing values."""

from __future__ import annotations

import math
import posixpath
import re
from dataclasses import dataclass


def memory_bytes(value: object) -> float | None:
    """OpenWebif labels binary quantities kB/MB/GB/TB, including /proc RAM."""
    if not isinstance(value, str):
        return None
    match = re.fullmatch(r"([0-9]+(?:[.,][0-9]+)?)\s*(B|[KMGT]i?B)", value.strip(), re.I)
    if not match:
        return None
    unit = match[2].upper().replace("I", "")
    result = (
        float(match[1].replace(",", "."))
        * 1024 ** {"B": 0, "KB": 1, "MB": 2, "GB": 3, "TB": 4}[unit]
    )
    return result if math.isfinite(result) else None


def uptime_seconds(value: object) -> int | None:
    """Parse OpenWebif's optional Nd HH:MM duration (minute resolution)."""
    if not isinstance(value, str) or len(value) > 128:
        return None
    match = re.fullmatch(r"(?:(\d+)d\s+)?(\d+):([0-5]\d)", value.strip())
    if not match or (match[1] is not None and int(match[2]) >= 24):
        return None
    return int(match[1] or 0) * 86400 + int(match[2]) * 3600 + int(match[3]) * 60


@dataclass(frozen=True)
class DiskSpace:
    mount: str
    free_bytes: float | None


@dataclass(frozen=True)
class SystemDiagnostics:
    ram_free_bytes: float | None = None
    ram_total_bytes: float | None = None
    uptime_seconds: int | None = None
    disks: tuple[DiskSpace, ...] = ()

    @classmethod
    def parse(cls, info: object) -> SystemDiagnostics:
        if not isinstance(info, dict):
            return cls()
        disks: dict[str, DiskSpace] = {}
        rows = info.get("hdd")
        for row in rows if isinstance(rows, list) else []:
            if not isinstance(row, dict):
                continue
            mount = row.get("mount")
            if not isinstance(mount, str) or not mount.startswith("/"):
                continue
            mount = posixpath.normpath(mount)
            free = memory_bytes(row.get("free"))
            if mount in disks:
                # Ambiguous duplicate mounts must not depend on response order.
                free = None
            disks[mount] = DiskSpace(mount, free)
        return cls(
            memory_bytes(info.get("mem2")),
            memory_bytes(info.get("mem1")),
            uptime_seconds(info.get("uptime")),
            tuple(disks[key] for key in sorted(disks)),
        )
