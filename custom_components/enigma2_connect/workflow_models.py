# SPDX-License-Identifier: Apache-2.0
"""Validated projections for recording workflows, independent of Home Assistant."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from .models import JsonObject, boolean, text


class DataFormatError(ValueError):
    """The receiver did not provide a supported workflow data shape."""


def integer(value: Any, *, minimum: int = 0, maximum: int | None = None) -> int | None:
    """Accept JSON integers and decimal strings, never bools or rounded floats."""
    if isinstance(value, str) and re.fullmatch(r"[0-9]+", value):
        try:
            value = int(value)
        except ValueError:
            return None
    if type(value) is not int or value < minimum or (maximum is not None and value > maximum):
        return None
    return value


def required_integer(row: JsonObject, key: str, *, minimum: int = 0) -> int:
    value = integer(row.get(key), minimum=minimum)
    if value is None:
        raise DataFormatError("Missing or invalid integer field")
    return value


def reference(row: JsonObject, key: str) -> str:
    value = row.get(key)
    if not isinstance(value, str) or not value.strip():
        raise DataFormatError("Missing service reference")
    # Opaque identifiers are not HTML-decoded, case-folded or URL-decoded.
    return value.strip()


def label(value: Any) -> str | None:
    return text(value) if isinstance(value, str) else None


def tags(value: Any) -> tuple[str, ...] | None:
    if isinstance(value, str):
        return tuple(value.split())
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return tuple(value)
    return None


def parse_list[T](data: JsonObject, field: str, parser: Callable[[JsonObject], T]) -> tuple[T, ...]:
    """Never turn unavailable or partially malformed data into an empty catalog."""
    rows = data.get(field)
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise DataFormatError("Missing or invalid list")
    return tuple(parser(row) for row in rows)


@dataclass(frozen=True)
class TimerIdentity:
    service_reference: str
    begin: int
    end: int

    @classmethod
    def parse(cls, row: JsonObject) -> TimerIdentity:
        identity = cls(
            reference(row, "serviceref"),
            required_integer(row, "begin"),
            required_integer(row, "end"),
        )
        # Images can expose zero-duration zap timers. Preserve their exact identity.
        if identity.end < identity.begin:
            raise DataFormatError("Invalid timer interval")
        return identity

    def response(self) -> JsonObject:
        return {"service_reference": self.service_reference, "begin": self.begin, "end": self.end}


@dataclass(frozen=True)
class Timer:
    identity: TimerIdentity
    name: str | None
    service_name: str | None
    disabled: bool | None
    justplay: bool | None
    repeated: int | None
    event_id: int | None
    directory: str | None
    tags: tuple[str, ...] | None
    state: int | None

    @classmethod
    def parse(cls, row: JsonObject) -> Timer:
        directory = row.get("dirname")
        return cls(
            TimerIdentity.parse(row),
            label(row.get("name")),
            label(row.get("servicename")),
            boolean(row.get("disabled")),
            boolean(row.get("justplay")),
            integer(row.get("repeated"), maximum=127),
            integer(row.get("eit")),
            directory if isinstance(directory, str) and directory not in ("", "None") else None,
            tags(row.get("tags")),
            integer(row.get("state"), maximum=3),
        )


@dataclass(frozen=True)
class TimerConflict:
    identity: TimerIdentity
    name: str | None
    service_name: str | None

    @classmethod
    def parse(cls, row: JsonObject) -> TimerConflict:
        return cls(TimerIdentity.parse(row), label(row.get("name")), label(row.get("servicename")))


@dataclass(frozen=True)
class EpgEvent:
    service_reference: str
    event_id: int
    begin: int
    end: int
    title: str | None
    service_name: str | None
    description: str | None

    @classmethod
    def parse(cls, row: JsonObject) -> EpgEvent:
        begin = required_integer(row, "begin_timestamp", minimum=1)
        duration = required_integer(row, "duration_sec", minimum=1)
        return cls(
            reference(row, "sref"),
            required_integer(row, "id"),
            begin,
            begin + duration,
            label(row.get("title")),
            label(row.get("sname")),
            label(row.get("longdesc")) or label(row.get("shortdesc")),
        )


@dataclass(frozen=True)
class Recording:
    service_reference: str
    title: str | None
    service_name: str | None
    recorded_at: int | None
    duration: int | None
    size_bytes: int | None
    tags: tuple[str, ...] | None
    progress_percent: int | None = None

    @classmethod
    def parse(cls, row: JsonObject) -> Recording:
        duration = None
        length = row.get("length")
        if isinstance(length, str) and re.fullmatch(r"[0-9]+:[0-5][0-9]", length):
            minutes, seconds = length.split(":")
            parsed_minutes = integer(minutes)
            if parsed_minutes is not None:
                duration = parsed_minutes * 60 + int(seconds)
        return cls(
            reference(row, "serviceref"),
            label(row.get("eventname")),
            label(row.get("servicename")),
            integer(row.get("recordingtime"), minimum=1),
            duration,
            integer(row.get("filesize")),
            tags(row.get("tags")),
            integer(row.get("lastseen"), maximum=100),
        )
