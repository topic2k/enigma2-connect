# SPDX-License-Identifier: Apache-2.0
"""Guarded recording writes with fresh catalogs and explicit confirmation."""

from __future__ import annotations

import asyncio
import json
from hashlib import sha256
from pathlib import PurePosixPath
from urllib.parse import quote

from .api import (
    AuthenticationError,
    CommandRejectedError,
    CommandUnconfirmed,
    ConnectionError,
    OpenWebifClient,
    ReceiverError,
    UnsupportedError,
    command_response,
)
from .models import JsonObject, ReceiverState
from .workflow_models import DataFormatError, Recording, Timer, parse_list


class RecordingManagementError(ReceiverError):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def revision(recording: Recording) -> str:
    """Bind a user's choice to its identity and stable observed metadata."""
    values = [
        recording.service_reference,
        recording.title,
        recording.recorded_at,
        recording.duration,
        recording.size_bytes,
    ]
    return sha256(json.dumps(values, ensure_ascii=False).encode()).hexdigest()


def safe_path(value: str) -> PurePosixPath:
    path = PurePosixPath(value)
    if (
        not value.startswith("/")
        or value.startswith("//")
        or ".." in path.parts
        or any(ord(c) < 32 for c in value)
        or "\\" in value
    ):
        raise RecordingManagementError("recording_path")
    return path


def movie_path(recording: Recording) -> PurePosixPath:
    parts = recording.service_reference.split(":", 10)
    if len(parts) != 11:
        raise RecordingManagementError("recording_path")
    path = safe_path(parts[-1])
    if not path.suffix or path == PurePosixPath("/"):
        raise RecordingManagementError("recording_path")
    return path


def reference_path(value: object) -> PurePosixPath | None:
    """Read a raw file path or service reference without decoding literal percent signs."""
    if not isinstance(value, str) or not value:
        return None
    parts = value.split(":", 10)
    path = value if value.startswith("/") else parts[-1] if len(parts) == 11 else value
    return safe_path(path) if path.startswith("/") else None


class RecordingManager:
    def __init__(self, client: OpenWebifClient) -> None:
        self.client = client
        # One unresolved write blocks subsequent writes. Never resend automatically.
        self.pending: JsonObject | None = None
        self.last: JsonObject = {"status": "idle"}

    async def _catalog(self, directory: str | None = None) -> tuple[Recording, ...]:
        data = await self.client.get(
            "movielist", **({"dirname": directory} if directory else {"recursive": 1})
        )
        try:
            rows = parse_list(data, "movies", Recording.parse)
            if len({row.service_reference for row in rows}) != len(rows):
                raise DataFormatError("Ambiguous catalog")
        except DataFormatError as err:
            raise RecordingManagementError("recording_data") from err
        if directory and safe_path(str(data.get("directory", ""))) != safe_path(directory):
            raise RecordingManagementError("recording_destination")
        return rows

    def blocks_stream(self, path: str | None) -> bool:
        """Only unresolved file operations block readers of their affected paths."""
        if self.pending is None or self.pending.get("action") == "rename":
            return False
        source = reference_path(self.pending.get("service_reference"))
        requested = reference_path(path)
        return (
            source is None
            or requested is None
            or requested in (source, reference_path(self.pending.get("target_path")))
        )

    async def _check_activity(self, action: str, source: PurePosixPath) -> None:
        raw = await self.client.get("statusinfo")
        timer_data = await self.client.get("timerlist")
        try:
            state = ReceiverState.parse(raw)
            timers = parse_list(timer_data, "timers", Timer.parse)
        except ValueError:
            raise RecordingManagementError("recording_data") from None
        # A filename may omit the .ts suffix. Match exactly, never by title/substrings.
        known_running = False
        for timer, original in zip(timers, timer_data["timers"], strict=True):
            if timer.disabled is True or timer.justplay is True or timer.state in (0, 3):
                continue
            path = reference_path(original.get("filename"))
            if path is None:
                raise RecordingManagementError("recording_activity_unknown")
            if source in (path, PurePosixPath(f"{path}.ts")):
                raise RecordingManagementError("recording_busy")
            known_running |= timer.state == 2
        if state.recording is None or (state.recording and not known_running):
            raise RecordingManagementError("recording_activity_unknown")
        if action == "rename":
            return
        if state.recording_playback:
            paths = {
                reference_path(raw.get("currservice_filename")),
                reference_path(state.reference),
            } - {None}
            if not paths:
                raise RecordingManagementError("recording_activity_unknown")
            if source in paths:
                raise RecordingManagementError("recording_busy")
        # Optional per-client information; the global isStreaming flag cannot
        # identify a file and does not account for every external HTTP reader.
        try:
            about = await self.client.get("about")
        except UnsupportedError:
            return
        info = about.get("info", {})
        streams = info.get("streams", []) if isinstance(info, dict) else None
        if not isinstance(streams, list) or not all(
            isinstance(item, dict) and isinstance(item.get("ref"), str) for item in streams
        ):
            raise RecordingManagementError("recording_data")
        if any(reference_path(item["ref"]) == source for item in streams):
            raise RecordingManagementError("recording_busy")

    async def _check(self) -> JsonObject:
        if self.pending is None:
            return self.last
        operation = self.pending
        rows = await self._catalog(operation["source_directory"])
        old = next(
            (row for row in rows if row.service_reference == operation["service_reference"]), None
        )
        complete = False
        if operation["action"] == "rename":
            complete = bool(
                old
                and old.title == operation["title"]
                and old.recorded_at == operation["recorded_at"]
                and old.size_bytes == operation["size_bytes"]
            )
        elif operation["action"] == "delete":
            complete = old is None
        else:
            destination = await self._catalog(operation["directory"])
            complete = old is None and any(
                str(movie_path(row)) == operation["target_path"]
                and row.recorded_at == operation["recorded_at"]
                and row.size_bytes == operation["size_bytes"]
                for row in destination
            )
        result = {
            "status": "completed" if complete else "pending",
            "action": operation["action"],
            "service_reference": operation["service_reference"],
            "deletion_policy": "receiver_may_delete_permanently",
        }
        if complete:
            self.pending = None
            self.last = result
        return result

    async def status(self) -> JsonObject:
        async with self.client.command_lock:
            return await self._check()

    async def manage(
        self,
        service_reference: str,
        expected_revision: str,
        action: str,
        title: str = "",
        directory: str = "",
        confirm_delete: bool = False,
    ) -> JsonObject:
        async with self.client.command_lock:
            if self.pending is not None:
                raise RecordingManagementError("recording_pending")
            self.last = {"status": "idle"}
            if action not in ("rename", "move", "delete"):
                raise RecordingManagementError("recording_input")
            if action == "delete" and not confirm_delete:
                raise RecordingManagementError("recording_confirm")
            if action == "rename" and (
                not title.strip() or len(title) > 200 or any(ord(c) < 32 for c in title)
            ):
                raise RecordingManagementError("recording_input")
            rows = await self._catalog()
            selected = next(
                (row for row in rows if row.service_reference == service_reference), None
            )
            if selected is None or revision(selected) != expected_revision:
                raise RecordingManagementError("recording_stale")
            if selected.recorded_at is None or not selected.size_bytes:
                raise RecordingManagementError("recording_data")
            source = movie_path(selected)
            params: JsonObject = {"sRef": service_reference}
            operation: JsonObject = {
                "action": action,
                "service_reference": service_reference,
                "source_directory": str(source.parent),
                "recorded_at": selected.recorded_at,
                "size_bytes": selected.size_bytes,
                "title": title.strip(),
                "directory": directory,
            }
            if action == "rename":
                # movieinfo edits the displayed title without renaming media files.
                # It decodes its argument again; preserve literal percent sequences.
                endpoint = "movieinfo"
                params = {"sRef": quote(service_reference, safe=""), "title": title.strip()}
            elif action == "move":
                target_dir = safe_path(directory)
                locations = (await self.client.get("getlocations")).get("locations")
                known = {str(movie_path(row).parent) for row in rows}
                if not isinstance(locations, list) or not all(
                    isinstance(item, str) for item in locations
                ):
                    raise RecordingManagementError("recording_destination")
                known.update(str(safe_path(item)) for item in locations)
                if str(target_dir) not in known or target_dir == source.parent:
                    raise RecordingManagementError("recording_destination")
                targets = await self._catalog(str(target_dir))
                if any(movie_path(row).stem == source.stem for row in targets):
                    raise RecordingManagementError("recording_collision")
                operation["directory"] = str(target_dir)
                operation["target_path"] = str(target_dir / source.name)
                endpoint = "moviemove"
                params["dirname"] = str(target_dir)
            else:
                endpoint = "moviedelete"
                # Never pass force: on OpenWebif its mere presence enables it.
            await self._check_activity(action, source)
            fresh = await self._catalog(str(source.parent))
            if not any(
                row.service_reference == service_reference and revision(row) == expected_revision
                for row in fresh
            ):
                raise RecordingManagementError("recording_stale")
            self.pending = operation
            try:
                command_response(endpoint, await self.client.get(endpoint, **params))
            except CommandUnconfirmed, CommandRejectedError:
                pass
            except AuthenticationError, UnsupportedError, ConnectionError:
                self.pending = None
                raise
            # Cancellation leaves the unresolved write blocked for status checks.
            try:
                for attempt in range(3):
                    result = await self._check()
                    if result["status"] == "completed":
                        return result
                    if attempt < 2:
                        await asyncio.sleep(0.25)
            except ReceiverError:
                pass
            return {
                "status": "pending",
                "action": action,
                "service_reference": service_reference,
                "deletion_policy": "receiver_may_delete_permanently",
            }
