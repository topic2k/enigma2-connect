# SPDX-License-Identifier: Apache-2.0
"""Explicit timeshift control, independent of playback pause inference."""

from .api import (
    AuthenticationError,
    CommandUnconfirmed,
    OpenWebifClient,
    ReceiverError,
    command_response,
)
from .models import JsonObject, ReceiverState, boolean


def parse_timeshift(data: JsonObject | None) -> bool | None:
    if not data or boolean(data.get("state")) is not True:
        return None
    return boolean(data.get("timeshiftEnabled"))


class TimeshiftError(ReceiverError):
    """Timeshift is unavailable or its outcome could not be confirmed."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


async def set_timeshift(client: OpenWebifClient, enabled: bool) -> None:
    async with client.command_lock:
        try:
            state = ReceiverState.parse(await client.get("statusinfo"))
        except ValueError as err:
            raise TimeshiftError("timeshift_unavailable") from err
        if state.standby:
            raise TimeshiftError("timeshift_unavailable")
        current = parse_timeshift(await client.get("tsstate"))
        if current is None:
            raise TimeshiftError("timeshift_unavailable")
        if current is enabled:
            return
        endpoint = "tsstart" if enabled else "tsstop"
        try:
            command_response(endpoint, await client.get(endpoint))
        except CommandUnconfirmed as err:
            raise TimeshiftError("timeshift_unconfirmed") from err
        try:
            actual = parse_timeshift(await client.get("tsstate"))
        except AuthenticationError:
            raise
        except ReceiverError as err:
            raise TimeshiftError("timeshift_unconfirmed") from err
        if actual is not enabled:
            raise TimeshiftError("timeshift_unconfirmed")
