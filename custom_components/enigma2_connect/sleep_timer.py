# SPDX-License-Identifier: Apache-2.0
"""Receiver-owned sleep timer; verify mutations without replaying them."""

from .api import AuthenticationError, OpenWebifClient, ReceiverError
from .models import JsonObject, ReceiverState, SleepTimer, boolean


class SleepTimerError(ReceiverError):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def parse_sleep_timer(data: JsonObject | None) -> SleepTimer | None:
    if not data or ("result" in data and boolean(data["result"]) is not True):
        return None
    enabled = boolean(data.get("enabled"))
    if enabled is None:
        return None
    raw = str(data.get("minutes"))
    minutes = int(raw) if 1 <= len(raw) <= 3 and raw.isascii() and raw.isdecimal() else None
    action = data.get("action")
    return SleepTimer(enabled, minutes, action if action in ("standby", "shutdown") else None)


async def set_sleep_timer(client: OpenWebifClient, minutes: int | None = None) -> None:
    """None cancels; a duration always starts a fresh standby timer."""
    if minutes is not None and (type(minutes) is not int or not 1 <= minutes <= 999):
        raise SleepTimerError("sleep_timer_invalid")
    async with client.command_lock:
        try:
            state = ReceiverState.parse(await client.get("statusinfo"))
        except ValueError as err:
            raise SleepTimerError("sleep_timer_unavailable") from err
        if state.standby:
            raise SleepTimerError("sleep_timer_unavailable")
        current = parse_sleep_timer(await client.get("sleeptimer"))
        if current is None:
            raise SleepTimerError("sleep_timer_unavailable")
        if minutes is None and not current.enabled:
            return
        if minutes is None and current.action is None:
            raise SleepTimerError("sleep_timer_unavailable")
        try:
            reply = await client.get(
                "sleeptimer",
                cmd="set",
                enabled="True" if minutes is not None else "False",
                time=minutes if minutes is not None else 0,
                action="standby" if minutes is not None else current.action,
            )
            if "result" in reply and boolean(reply["result"]) is not True:
                raise SleepTimerError("sleep_timer_unconfirmed")
            after = parse_sleep_timer(await client.get("sleeptimer"))
        except AuthenticationError:
            raise
        except ReceiverError as err:
            raise SleepTimerError("sleep_timer_unconfirmed") from err
        if after is None or after.enabled != (minutes is not None):
            raise SleepTimerError("sleep_timer_unconfirmed")
        if minutes is not None and (after.action != "standby" or after.minutes != minutes):
            raise SleepTimerError("sleep_timer_unconfirmed")
