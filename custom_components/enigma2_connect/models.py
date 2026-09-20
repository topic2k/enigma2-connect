# SPDX-License-Identifier: Apache-2.0
"""Home Assistant independent parsing of receiver data."""

from __future__ import annotations

import math
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime
from html import unescape
from typing import Any

# OpenWebif adds image-specific fields; validate values when projecting this
# transport boundary into the typed receiver state and service models below.
type JsonObject = dict[str, Any]


def boolean(value: Any) -> bool | None:
    """Do not confuse the string 'false' with True or missing with False."""
    if isinstance(value, bool):
        return value
    if str(value).lower() in ("true", "1"):
        return True
    if str(value).lower() in ("false", "0"):
        return False
    return None


def number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        result = float(
            str(value).strip().removesuffix("%").removesuffix("dB").removesuffix("°C").strip()
        )
    except TypeError, ValueError:
        return None
    return result if math.isfinite(result) else None


def signal_snr_db(signal: dict[str, Any] | None) -> float | None:
    """Ignore OpenWebif's integer percentage fallback in the dB field."""
    if not signal:
        return None
    raw = signal.get("snr_db")
    if type(raw) is int and raw == number(signal.get("snr")):
        return None
    return number(raw)


def text(value: Any) -> str | None:
    if value is None or value in ("", "N/A"):
        return None
    # Strip DVB emphasis markers that would otherwise leak into entity text.
    return unescape(str(value)).replace("\u0086", "").replace("\u0087", "")


def identity(info: dict[str, Any]) -> str | None:
    """Prefer a stable, non-loopback hardware address."""
    for iface in info.get("ifaces", []):
        if not isinstance(iface, dict):
            continue
        mac = re.sub(r"[:-]", "", str(iface.get("mac", ""))).lower()
        if re.fullmatch(r"[0-9a-f]{12}", mac) and mac not in ("000000000000", "ffffffffffff"):
            return mac
    return None


@dataclass(frozen=True)
class Service:
    reference: str
    name: str


def services(rows: list[Any], *, channels: bool = False) -> dict[str, Service]:
    """Preserve references; make duplicate display names selectable."""
    parsed: dict[str, Service] = {}
    for row in rows:
        if isinstance(row, (list, tuple)) and len(row) == 2:
            ref, name = row
        elif isinstance(row, dict):
            ref, name = row.get("servicereference"), row.get("servicename")
        else:
            continue
        if not isinstance(ref, str) or not name:
            continue
        if channels:
            try:
                flags = int(ref.split(":")[1])
            except ValueError, IndexError:
                continue
            # Bouquet navigation and marker entries are not selectable channels.
            if flags & (2 | 64 | 128 | 256 | 512):
                continue
        parsed.setdefault(ref, Service(ref, text(name) or "?"))
    names: dict[str, int] = {}
    for service in parsed.values():
        names[service.name] = names.get(service.name, 0) + 1
    return {
        s.name if names[s.name] == 1 else f"{s.name} [{s.reference}]": s for s in parsed.values()
    }


def epoch(value: str | int) -> int:
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        # Avoid silently interpreting timer input in the Home Assistant host timezone.
        raise ValueError("A timezone offset is required")
    return int(parsed.timestamp())


def timer_range(begin: str | int, end: str | int) -> tuple[int, int]:
    start, stop = epoch(begin), epoch(end)
    if stop <= start:
        raise ValueError("End must be after begin")
    return start, stop


@dataclass(frozen=True)
class ReceiverState:
    standby: bool
    channel: str | None = None
    reference: str | None = None
    title: str | None = None
    next_title: str | None = None
    volume: float | None = None
    muted: bool | None = None
    recording: bool | None = None
    streaming: bool | None = None
    description: str | None = None
    programme_start: int | None = None
    programme_end: int | None = None
    recording_playback: bool = False
    picon_path: str | None = None

    @classmethod
    def parse(cls, raw: dict[str, Any], current: dict[str, Any] | None = None) -> ReceiverState:
        standby = boolean(raw.get("inStandby"))
        if standby is None:
            raise ValueError("Missing or invalid standby state")
        next_event = (current or {}).get("next") or {}
        if not isinstance(next_event, dict):
            next_event = {}
        volume = number(raw.get("volume"))
        reference = text(raw.get("currservice_serviceref"))
        start = number(raw.get("currservice_begin_timestamp"))
        end = number(raw.get("currservice_end_timestamp"))
        current_info = (current or {}).get("info") or {}
        return cls(
            standby=standby,
            channel=text(raw.get("currservice_station")),
            reference=text(raw.get("currservice_serviceref")),
            title=text(raw.get("currservice_name")),
            next_title=text(next_event.get("title")),
            volume=max(0, min(100, volume)) / 100 if volume is not None else None,
            muted=boolean(raw.get("muted")),
            recording=boolean(raw.get("isRecording")),
            streaming=boolean(raw.get("isStreaming")),
            description=text(
                raw.get("currservice_fulldescription") or raw.get("currservice_description")
            ),
            programme_start=int(start) if start is not None and start > 0 else None,
            programme_end=int(end) if end is not None and end > 0 else None,
            recording_playback=bool(raw.get("currservice_filename"))
            or bool(
                reference and reference.startswith(("1:0:0:", "4097:0:0:")) and ":/" in reference
            ),
            picon_path=current_info.get("picon") if isinstance(current_info, dict) else None,
        )


def picon_candidates(
    reference: str, channel: str | None = None, hint: str | None = None
) -> list[str]:
    """Derive safe local picon paths from protocol metadata, never arbitrary URLs."""
    paths = []
    if isinstance(hint, str) and re.fullmatch(r"/picon/[A-Za-z0-9_-]+\.png", hint):
        paths.append(hint)
    fields = reference.split(":")
    if (
        len(fields) >= 10
        and fields[0] == "1"
        and fields[2] != "0"
        and all(re.fullmatch(r"[0-9a-fA-F]+", field) for field in fields[:10])
    ):
        paths.append("/picon/" + "_".join(fields[:10]) + ".png")
    if channel:
        name = channel
        if ":/" in reference:
            parts = reference.rsplit("/", 1)[-1].split(" - ")
            if len(parts) >= 3:
                name = parts[1]
        replacements: dict[str, str | int | None] = {"&": "and", "+": "plus", "*": "star"}
        expanded = name.translate(str.maketrans(replacements))
        normalized = unicodedata.normalize("NFKD", expanded).lower()
        filename = "".join(
            char for char in normalized if char in "abcdefghijklmnopqrstuvwxyz0123456789"
        )
        if filename:
            paths.append(f"/picon/{filename}.png")
    return list(dict.fromkeys(paths))


@dataclass(frozen=True)
class Snapshot:
    # All entities consume the same poll result. For optional lists, None means
    # unavailable; an empty list means the receiver reported no entries.
    state: ReceiverState
    signal: JsonObject | None = None
    info: JsonObject = field(default_factory=dict)
    timers: list[JsonObject] | None = None
    movies: list[JsonObject] | None = None
    bouquets: dict[str, Service] = field(default_factory=dict)
    channels: dict[str, Service] = field(default_factory=dict)
    bouquet: str | None = None
    movie_directory: str | None = None
    media_channels: dict[str, Service] | None = None
    recording_directories: tuple[str, ...] = ()
