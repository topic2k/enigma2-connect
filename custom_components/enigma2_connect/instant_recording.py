# SPDX-License-Identifier: Apache-2.0
"""Start the current programme once, with fresh receiver checks under its lock."""

from __future__ import annotations

from time import time
from typing import Literal

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
from .workflow_models import (
    DataFormatError,
    EpgEvent,
    Timer,
    TimerIdentity,
    integer,
    parse_list,
    reference,
)

type EventKey = tuple[str, int, int, int]


class InstantRecordingError(ReceiverError):
    """A known precondition failed; never include receiver text in the message."""

    def __init__(
        self,
        reason: Literal[
            "recording_no_epg", "recording_not_live", "recording_changed", "recording_timer_data"
        ],
    ) -> None:
        super().__init__(reason)
        self.reason = reason


def event_key(event: EpgEvent) -> EventKey:
    return event.service_reference, event.event_id, event.begin, event.end


class InstantRecording:
    def __init__(self, client: OpenWebifClient) -> None:
        self.client = client
        # Uncertain writes stay blocked until programme end. Confirmed writes also
        # cover ten seconds of receiver list lag. No persistence across HA reloads.
        self._attempts: dict[tuple[str, int], float] = {}

    async def _current(self) -> EpgEvent:
        raw = await self.client.get("statusinfo")
        try:
            state = ReceiverState.parse(raw)
            ref = reference(raw, "currservice_serviceref")
        except ValueError as err:
            raise InstantRecordingError("recording_not_live") from err
        if state.standby or state.recording_playback:
            raise InstantRecordingError("recording_not_live")
        current = await self.client.get("getcurrent")
        row = current.get("now")
        try:
            if not isinstance(row, dict):
                raise DataFormatError("Missing current event")
            event = EpgEvent.parse(row)
        except DataFormatError as err:
            raise InstantRecordingError("recording_no_epg") from err
        if event.service_reference != ref:
            raise InstantRecordingError("recording_changed")
        if not event.title or not event.begin <= time() < event.end:
            raise InstantRecordingError("recording_no_epg")
        return event

    async def _timers(self) -> tuple[Timer, ...]:
        data = await self.client.get("timerlist")
        try:
            return parse_list(data, "timers", Timer.parse)
        except DataFormatError as err:
            raise InstantRecordingError("recording_timer_data") from err

    @staticmethod
    def _existing(timers: tuple[Timer, ...], event: EpgEvent) -> TimerIdentity | None:
        now = time()
        for timer in timers:
            if timer.identity.service_reference != event.service_reference or timer.state == 3:
                continue
            if timer.disabled is True or timer.justplay is True:
                continue
            # A series can be running even when its stored interval is in the past.
            # Missing state cannot establish that it is safe to start another timer.
            if timer.state is None:
                raise InstantRecordingError("recording_timer_data")
            if timer.state != 2 and not timer.identity.begin <= now < timer.identity.end:
                continue
            if timer.disabled is None or timer.justplay is None:
                raise InstantRecordingError("recording_timer_data")
            return timer.identity
        return None

    async def start(self) -> JsonObject:
        """Serialize preflight, write and confirmation with all other HA commands."""
        async with self.client.command_lock:
            now = time()
            self._attempts = {key: until for key, until in self._attempts.items() if until > now}
            event = await self._current()
            timers = await self._timers()
            # Recheck after the list fetch: external remotes do not share our lock.
            if event_key(await self._current()) != event_key(event):
                raise InstantRecordingError("recording_changed")
            if existing := self._existing(timers, event):
                return {"started": False, "timer": existing.response()}
            key = (event.service_reference, event.event_id)
            if key in self._attempts:
                raise CommandUnconfirmed("A start was already requested for this programme")
            self._attempts[key] = event.end
            try:
                # Parameter PRESENCE enables infinite mode in OpenWebif, even =0.
                # Never pass infinite/undefinitely, and never fall back to that mode.
                data = command_response("recordnow", await self.client.get("recordnow"))
            except CommandUnconfirmed:
                raise
            except AuthenticationError, UnsupportedError, CommandRejectedError, ConnectionError:
                self._attempts.pop(key)
                raise
            # Cancellation and other ambiguous failures intentionally retain the guard.
            try:
                row = data.get("newtimer")
                if row is None:
                    identity = self._existing(await self._timers(), event)
                    if identity is None:
                        raise DataFormatError("No confirmed timer")
                else:
                    if not isinstance(row, dict):
                        raise DataFormatError("Invalid returned timer")
                    identity = TimerIdentity.parse(row)
                    if integer(row.get("eit")) != event.event_id:
                        raise DataFormatError("Different returned event")
                if (
                    identity.service_reference != event.service_reference
                    or not event.begin <= identity.begin < event.end
                    or identity.end <= time()
                ):
                    raise DataFormatError("Different returned programme")
            except AuthenticationError:
                raise
            except (DataFormatError, ReceiverError) as err:
                raise CommandUnconfirmed("Recording timer could not be confirmed") from err
            self._attempts[key] = min(event.end, time() + 10)
            return {"started": True, "timer": identity.response()}
