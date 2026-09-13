# SPDX-License-Identifier: Apache-2.0
"""Standard remote actions, including validated atomic sequences."""

from homeassistant.components.remote import RemoteEntity, RemoteEntityFeature
from homeassistant.exceptions import ServiceValidationError

from .const import DOMAIN, KEYS
from .entity import EnigmaEntity

PARALLEL_UPDATES = 0


def key_codes(command):
    result = []
    for key in command:
        try:
            code = KEYS[str(key)] if str(key) in KEYS else int(key)
        except ValueError, TypeError:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="unknown_remote_key",
                translation_placeholders={"key": str(key)},
            ) from None
        if not 0 <= code <= 0x2FF:
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="invalid_key_code"
            )
        result.append(code)
    return result


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([EnigmaRemote(entry.runtime_data, "remote")])


class EnigmaRemote(EnigmaEntity, RemoteEntity):
    _attr_supported_features = RemoteEntityFeature(0)

    @property
    def suggested_object_id(self):
        # Keep the technical suffix independent of the translated control label.
        return "remote"

    @property
    def is_on(self):
        return not self.coordinator.data.state.standby

    async def async_turn_on(self, **kwargs):
        await self.coordinator.perform(self.coordinator.client.command, "powerstate", newstate=4)

    async def async_turn_off(self, **kwargs):
        await self.coordinator.perform(self.coordinator.client.command, "powerstate", newstate=5)

    async def async_send_command(self, command, **kwargs):
        codes = key_codes([command] if isinstance(command, str) else command)
        repeats = kwargs.get("num_repeats", 1)
        delay = kwargs.get("delay_secs", 0.3)
        if (
            not codes
            or not 1 <= repeats <= 100
            or len(codes) * repeats > 500
            or not 0 <= delay <= 5
        ):
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="invalid_sequence"
            )
        await self.coordinator.perform(
            self.coordinator.client.keys,
            codes * repeats,
            delay=delay,
            hold=kwargs.get("hold_secs", 0) > 0,
        )
