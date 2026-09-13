# SPDX-License-Identifier: Apache-2.0
"""Screen messages through the current notify entity interface."""

from homeassistant.components.notify import NotifyEntity, NotifyEntityFeature

from .entity import EnigmaEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([EnigmaNotify(entry.runtime_data, "message")])


class EnigmaNotify(EnigmaEntity, NotifyEntity):
    _attr_supported_features = NotifyEntityFeature.TITLE

    async def async_send_message(self, message: str, title: str | None = None) -> None:
        options = self.coordinator.entry.options
        await self.coordinator.perform(
            self.coordinator.client.command,
            "message",
            text=f"{title}\n{message}" if title else message,
            type=options.get("message_type", 1),
            timeout=options.get("message_timeout", 10),
            refresh=False,
        )
