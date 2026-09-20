# SPDX-License-Identifier: Apache-2.0
"""On-demand EPG lookup and guarded event-based recording."""

from __future__ import annotations

from dataclasses import asdict
from time import time

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
from .models import JsonObject
from .workflow_models import DataFormatError, EpgEvent, Timer, parse_list


class EpgError(ReceiverError):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class EpgWorkflow:
    def __init__(self, client: OpenWebifClient) -> None:
        self.client = client
        # No retries after an uncertain write, including cancellation. Memory-only:
        # inspect receiver timers before retrying after an integration reload.
        self._attempts: dict[tuple[str, int], float] = {}

    @staticmethod
    def _results(data: JsonObject) -> JsonObject:
        try:
            events = parse_list(data, "events", EpgEvent.parse)
        except DataFormatError as err:
            raise EpgError("epg_data") from err
        now = time()
        unique = {
            (e.service_reference, e.event_id, e.begin, e.end): e for e in events if e.end > now
        }
        ordered = sorted(unique.values(), key=lambda e: (e.begin, e.service_reference, e.event_id))
        return {"events": [asdict(e) for e in ordered], "truncated": False}

    async def search(self, query: str) -> JsonObject:
        # The presence of `full` enables description search. Leave it absent.
        return self._results(await self.client.get("epgsearch", search=query))

    async def _event(self, expected: JsonObject) -> EpgEvent:
        data = await self.client.get(
            "event", sRef=expected["service_reference"], idev=expected["event_id"]
        )
        try:
            row = data.get("event")
            if not isinstance(row, dict):
                raise DataFormatError("Missing event")
            event = EpgEvent.parse(
                {
                    **row,
                    "begin_timestamp": row.get("begin"),
                    "duration_sec": row.get("duration"),
                    "sname": row.get("channel"),
                }
            )
        except DataFormatError as err:
            raise EpgError("epg_changed") from err
        if (
            any(
                asdict(event)[key] != expected[key]
                for key in ("service_reference", "event_id", "begin", "end")
            )
            or event.end <= time()
            or not event.title
        ):
            raise EpgError("epg_changed")
        return event

    async def similar(self, expected: JsonObject) -> JsonObject:
        event = await self._event(expected)
        return self._results(
            await self.client.get(
                "epgsimilar", sRef=event.service_reference, eventid=event.event_id
            ),
        )

    async def _timers(self) -> tuple[Timer, ...]:
        try:
            return parse_list(await self.client.get("timerlist"), "timers", Timer.parse)
        except DataFormatError as err:
            raise EpgError("recording_timer_data") from err

    @staticmethod
    def _existing(timers: tuple[Timer, ...], event: EpgEvent) -> Timer | None:
        for timer in timers:
            identity = timer.identity
            if identity.service_reference != event.service_reference or timer.state == 3:
                continue
            # A stored series interval need not represent its next occurrence.
            # Do not guess receiver wall-time recurrence or change disabled timers.
            if timer.repeated != 0:
                raise EpgError("epg_timer_ambiguous")
            if identity.end <= event.begin or identity.begin >= event.end:
                continue
            if (
                timer.disabled is False
                and timer.justplay is False
                and timer.state is not None
                and identity.begin <= max(event.begin, time())
                and identity.end >= event.end
            ):
                return timer
            raise EpgError("epg_timer_ambiguous")
        return None

    async def record(self, expected: JsonObject) -> JsonObject:
        async with self.client.command_lock:
            self._attempts = {k: v for k, v in self._attempts.items() if v > time()}
            event = await self._event(expected)
            before = await self._timers()
            event = await self._event(expected)
            if existing := self._existing(before, event):
                return {"created": False, "timer": existing.identity.response()}
            key = (event.service_reference, event.event_id)
            if key in self._attempts:
                raise CommandUnconfirmed("Event recording was already requested")
            self._attempts[key] = event.end
            try:
                command_response(
                    "timeraddbyeventid",
                    await self.client.get(
                        "timeraddbyeventid",
                        sRef=event.service_reference,
                        eventid=event.event_id,
                        justplay=0,
                        afterevent=3,
                    ),
                )
            except CommandUnconfirmed:
                raise
            except AuthenticationError, UnsupportedError, CommandRejectedError, ConnectionError:
                self._attempts.pop(key)
                raise
            try:
                new = tuple(
                    t
                    for t in await self._timers()
                    if t.identity not in {old.identity for old in before}
                )
                matching = [
                    t
                    for t in new
                    if t.event_id == event.event_id
                    and t.identity.service_reference == event.service_reference
                ]
                confirmed = self._existing(tuple(matching), event)
                if len(matching) != 1 or confirmed is None:
                    raise DataFormatError("No unique confirmed timer")
            except AuthenticationError:
                raise
            except (DataFormatError, ReceiverError) as err:
                raise CommandUnconfirmed("Event timer could not be confirmed") from err
            self._attempts[key] = min(event.end, time() + 10)
            return {"created": True, "timer": confirmed.identity.response()}
