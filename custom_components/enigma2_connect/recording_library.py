# SPDX-License-Identifier: Apache-2.0
"""Read-only recording catalog and explicit metadata filters."""

from __future__ import annotations

from dataclasses import asdict
from pathlib import PurePosixPath

from .api import OpenWebifClient, ReceiverError
from .models import JsonObject
from .workflow_models import DataFormatError, Recording, parse_list

PROGRESS_FILTERS = ("all", "in_progress", "complete", "zero", "unknown")


class RecordingLibraryError(ReceiverError):
    reason = "recording_data"


def progress_group(value: int | None) -> str:
    if value is None:
        return "unknown"
    if value == 0:
        return "zero"
    return "complete" if value == 100 else "in_progress"


class RecordingLibrary:
    def __init__(self, client: OpenWebifClient) -> None:
        self.client = client

    async def list(
        self, query: str = "", tag: str = "", directory: str = "", progress: str = "all"
    ) -> JsonObject:
        data = await self.client.get("movielist", recursive=1)
        try:
            if data.get("result") in (False, "False", "false"):
                raise DataFormatError("Rejected catalog")
            recordings = parse_list(data, "movies", Recording.parse)
        except DataFormatError as err:
            raise RecordingLibraryError() from err
        rows: list[JsonObject] = []
        for recording, raw in zip(recordings, data["movies"], strict=True):
            filename = raw.get("filename")
            if not isinstance(filename, str) or not filename:
                filename = recording.service_reference.split(":", 10)[-1]
            path = PurePosixPath(filename)
            row = asdict(recording)
            row["title"] = recording.title or path.name or None
            row["directory"] = str(path.parent) if path.is_absolute() else None
            # OpenWebif also emits zero when stat fails. Do not imply an empty file.
            row["size_bytes"] = recording.size_bytes or None
            row["tags"] = list(recording.tags) if recording.tags is not None else None
            rows.append(row)
        available_tags = sorted({tag for row in rows for tag in row["tags"] or []})
        directories = sorted({row["directory"] for row in rows if row["directory"]})
        needle = query.strip().casefold()
        selected = [
            row
            for row in rows
            if (
                not needle
                or any(needle in (row[key] or "").casefold() for key in ("title", "service_name"))
            )
            and (not tag or tag in (row["tags"] or []))
            and (not directory or directory == row["directory"])
            and (progress == "all" or progress_group(row["progress_percent"]) == progress)
        ]
        selected.sort(key=lambda row: (-(row["recorded_at"] or 0), row["service_reference"]))
        return {
            "recordings": selected,
            "total": len(rows),
            "count": len(selected),
            "tags": available_tags,
            "directories": directories,
        }
