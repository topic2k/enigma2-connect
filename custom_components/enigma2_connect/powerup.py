# SPDX-License-Identifier: Apache-2.0
"""Wake from standby with the image's one-shot HDMI-CEC suppression."""

from .api import AuthenticationError, OpenWebifClient, ReceiverError
from .models import boolean


class QuietPowerupError(ReceiverError):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


async def powerup_without_tv(client: OpenWebifClient) -> None:
    """Never fall back to ordinary wake or replay an uncertain mutation."""
    async with client.command_lock:
        state = boolean((await client.get("powerstate")).get("instandby"))
        if state is None:
            raise QuietPowerupError("quiet_powerup_unavailable")
        if not state:
            return  # Do not arm suppression for a later, unrelated wake.
        try:
            support = await client.get("supports_powerup_without_waking_tv")
        except AuthenticationError:
            raise
        except ReceiverError as err:
            raise QuietPowerupError("quiet_powerup_unavailable") from err
        if support.get("result") is not True:
            raise QuietPowerupError("quiet_powerup_unavailable")
        try:
            armed = await client.get("set_powerup_without_waking_tv")
            if armed.get("result") is not True:
                raise QuietPowerupError("quiet_powerup_unconfirmed")
            await client.get("powerstate", newstate=4)
            after = await client.get("powerstate")
            if boolean(after.get("instandby")) is not False:
                raise QuietPowerupError("quiet_powerup_unconfirmed")
        except AuthenticationError:
            raise
        except ReceiverError as err:
            raise QuietPowerupError("quiet_powerup_unconfirmed") from err
