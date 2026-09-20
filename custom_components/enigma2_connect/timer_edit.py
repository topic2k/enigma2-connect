# SPDX-License-Identifier: Apache-2.0
"""Read, preserve and confirm receiver timer edits under the command lock."""

from __future__ import annotations

import asyncio
from typing import Literal

from .api import (
    AuthenticationError,
    CommandRejectedError,
    CommandUnconfirmed,
    OpenWebifClient,
    ReceiverError,
    command_response,
)
from .models import JsonObject, boolean
from .workflow_models import DataFormatError, TimerIdentity, integer, parse_list, tags

WEEKDAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


class TimerEditError(ReceiverError):
    def __init__(
        self, reason: Literal["timer_edit_data", "timer_edit_missing", "timer_edit_scope"]
    ) -> None:
        super().__init__(reason)
        self.reason = reason


class TimerEditRejected(CommandRejectedError):
    def __init__(self, response: JsonObject, timer_state: str) -> None:
        super().__init__(response)
        self.timer_state = timer_state


def options(data: JsonObject) -> JsonObject:
    """Convert only explicitly supplied user options to OpenWebif parameters."""
    result = dict(data)
    if "weekdays" in result:
        result["repeated"] = sum(1 << WEEKDAYS.index(day) for day in set(result.pop("weekdays")))
    if "tags" in result:
        result["tags"] = " ".join(result["tags"])
    for key in ("disabled", "justplay"):
        if key in result:
            result[key] = int(result[key])
    for source, target in (("directory", "dirname"), ("recording_type", "recordingtype")):
        if source in result:
            result[target] = result.pop(source)
    return result


def preserved(row: JsonObject) -> JsonObject:
    """Never let endpoint defaults silently reset fields omitted by the user."""
    identity = TimerIdentity.parse(row)
    result: JsonObject = {
        "sRef": identity.service_reference,
        "begin": identity.begin,
        "end": identity.end,
    }
    for key in ("name", "description", "dirname"):
        value = row.get(key)
        if not isinstance(value, str):
            raise DataFormatError("Missing timer text")
        result[key] = "" if key == "dirname" and value == "None" else value
    for key in (
        "disabled",
        "justplay",
        "allow_duplicate",
        "vpsplugin_enabled",
        "vpsplugin_overwrite",
    ):
        value = boolean(row.get(key))
        if value is None:
            raise DataFormatError("Missing timer option")
        result[key] = int(value)
    for key, limit in (("repeated", 127), ("afterevent", 3)):
        value = integer(row.get(key), maximum=limit)
        if value is None:
            raise DataFormatError("Missing timer number")
        result[key] = value
    value = row.get("vpsplugin_time")
    if value in (None, -1, "-1"):
        if "vpsplugin_time" not in row:
            raise DataFormatError("Unknown VPS time")
        result["vpsplugin_time"] = -1
    else:
        parsed = integer(value)
        if parsed is None:
            raise DataFormatError("Invalid VPS time")
        result["vpsplugin_time"] = parsed
    tag_values = tags(row.get("tags"))
    if tag_values is None:
        raise DataFormatError("Missing tags")
    result["tags"] = " ".join(tag_values)
    # Absence leaves these image-specific fields unchanged at the endpoint.
    for key in ("always_zap", "pipzap", "hasendtime"):
        if key in row and row[key] not in (-1, "-1"):
            value = boolean(row[key])
            if value is None:
                raise DataFormatError("Invalid image-specific option")
            result[key] = int(value)
    if "recordingtype" in row:
        if row["recordingtype"] not in ("normal", "descrambled", "scrambled"):
            raise DataFormatError("Invalid recording type")
        result["recordingtype"] = row["recordingtype"]
    for key in ("marginbefore", "marginafter"):
        if key in row:
            value = integer(row[key])
            if value is None or value % 60:
                raise DataFormatError("Unsupported timer margin")
            result[key] = value // 60
    return result


class TimerEditor:
    def __init__(self, client: OpenWebifClient) -> None:
        self.client = client
        self._uncertain: set[TimerIdentity] = set()

    async def _rows(self) -> tuple[JsonObject, ...]:
        data = await self.client.get("timerlist")
        parse_list(data, "timers", TimerIdentity.parse)
        return tuple(data["timers"])

    async def edit(self, old: TimerIdentity, changes: JsonObject, scope: str) -> JsonObject:
        async with self.client.command_lock:
            if old in self._uncertain:
                raise CommandUnconfirmed("An earlier edit remains unconfirmed")
            try:
                rows = await self._rows()
                # OpenWebif matches only the first eleven service-reference fields.
                matches = [
                    row
                    for row in rows
                    if (
                        ":".join(row["serviceref"].strip().split(":")[:11])
                        == ":".join(old.service_reference.split(":")[:11])
                        and TimerIdentity.parse(row).begin == old.begin
                        and TimerIdentity.parse(row).end == old.end
                    )
                ]
                if len(matches) != 1 or TimerIdentity.parse(matches[0]) != old:
                    raise TimerEditError("timer_edit_missing")
                before = preserved(matches[0])
            except DataFormatError as err:
                raise TimerEditError("timer_edit_data") from err
            desired = {**before, **options(changes)}
            if (before["repeated"] or desired["repeated"]) and scope != "series":
                raise TimerEditError("timer_edit_scope")
            if desired["end"] <= desired["begin"]:
                raise TimerEditError("timer_edit_data")
            params = {
                **desired,
                "channelOld": old.service_reference,
                "beginOld": old.begin,
                "endOld": old.end,
                "returntimer": 1,
            }
            try:
                command_response("timerchange", await self.client.get("timerchange", **params))
            except CommandRejectedError as err:
                state = "unknown"
                try:
                    after = await self._rows()
                    remaining = [row for row in after if TimerIdentity.parse(row) == old]
                    state = (
                        "unchanged"
                        if len(remaining) == 1 and preserved(remaining[0]) == before
                        else "changed"
                    )
                except AuthenticationError, asyncio.CancelledError:
                    self._uncertain.add(old)
                    raise
                except DataFormatError, ReceiverError:
                    pass
                raise TimerEditRejected(err.response, state) from err
            except CommandUnconfirmed, asyncio.CancelledError:
                self._uncertain.add(old)
                raise
            try:
                rows = await self._rows()
                expected = TimerIdentity(desired["sRef"], desired["begin"], desired["end"])
                matches = [row for row in rows if TimerIdentity.parse(row) == expected]
                if len(matches) != 1:
                    raise DataFormatError("Edited timer not uniquely confirmed")
                actual = preserved(matches[0])
                if any(actual.get(key) != value for key, value in desired.items()):
                    raise DataFormatError("Edited options differ")
            except AuthenticationError, asyncio.CancelledError:
                self._uncertain.add(old)
                raise
            except (DataFormatError, ReceiverError) as err:
                self._uncertain.add(old)
                raise CommandUnconfirmed("Edited timer could not be confirmed") from err
            return {"action": "timer_edit", "timer": expected.response()}
