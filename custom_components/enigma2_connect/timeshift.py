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

CONF_RESTORE_TIMESHIFT_WARNING = "restore_timeshift_warning"
WARNING_KEYS = {"config.timeshift.check", "config.usage.check_timeshift"}


def parse_timeshift(data: JsonObject | None) -> bool | None:
    if not data or boolean(data.get("state")) is not True:
        return None
    return boolean(data.get("timeshiftEnabled"))


class TimeshiftError(ReceiverError):
    """Timeshift is unavailable or its outcome could not be confirmed."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def parse_warning(data: JsonObject) -> tuple[str, bool]:
    rows = data.get("configs")
    if not isinstance(rows, list):
        raise TimeshiftError("timeshift_warning_unavailable")
    matches = [
        row
        for row in rows
        if isinstance(row, dict)
        and isinstance(row.get("path"), str)
        and row["path"] in WARNING_KEYS
    ]
    if len(matches) != 1:
        raise TimeshiftError("timeshift_warning_unavailable")
    row = matches[0]
    value = row.get("data")
    if not isinstance(value, dict) or boolean(value.get("result")) is not True:
        raise TimeshiftError("timeshift_warning_unavailable")
    enabled = boolean(value.get("current"))
    if enabled is None:
        raise TimeshiftError("timeshift_warning_unavailable")
    return row["path"], enabled


async def read_warning(client: OpenWebifClient) -> tuple[str, bool]:
    try:
        return parse_warning(await client.get("config/Timeshift"))
    except AuthenticationError:
        raise
    except ReceiverError as err:
        raise TimeshiftError("timeshift_warning_unavailable") from err


async def restore_warning(client: OpenWebifClient, key: str) -> None:
    try:
        actual_key, enabled = await read_warning(client)
        if actual_key != key:
            raise TimeshiftError("timeshift_warning_restore_failed")
        if enabled:
            return
        try:
            command_response("saveconfig", await client.post("saveconfig", key=key, value="true"))
        except CommandUnconfirmed:
            # The POST may already have succeeded. Verify without replaying it.
            pass
        if await read_warning(client) != (key, True):
            raise TimeshiftError("timeshift_warning_restore_failed")
    except AuthenticationError:
        raise
    except ReceiverError as err:
        raise TimeshiftError("timeshift_warning_restore_failed") from err


async def set_timeshift(
    client: OpenWebifClient, enabled: bool, *, restore_save_warning: bool = False
) -> None:
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
        warning = await read_warning(client) if restore_save_warning else None
        try:
            await change_timeshift(client, enabled)
        finally:
            # Also restore after rejection, lost response or task cancellation.
            # Do not enable a warning that the user already had disabled.
            if warning is not None and warning[1]:
                await restore_warning(client, warning[0])


async def change_timeshift(client: OpenWebifClient, enabled: bool) -> None:
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
