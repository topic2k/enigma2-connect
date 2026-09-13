# SPDX-License-Identifier: Apache-2.0
"""Selections share coordinator data; no startup dispatcher race."""

from homeassistant.components.select import SelectEntity
from homeassistant.exceptions import ServiceValidationError

from .entity import EnigmaEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([EnigmaSelect(entry.runtime_data, kind) for kind in ("bouquet", "channel")])


class EnigmaSelect(EnigmaEntity, SelectEntity):
    def __init__(self, coordinator, kind):
        super().__init__(coordinator, f"select_{kind}")
        self.kind = kind

    @property
    def items(self):
        return (
            self.coordinator.data.bouquets
            if self.kind == "bouquet"
            else self.coordinator.data.channels
        )

    @property
    def options(self):
        return list(self.items)

    @property
    def current_option(self):
        reference = (
            self.coordinator.data.bouquet
            if self.kind == "bouquet"
            else self.coordinator.data.state.reference
        )
        return next(
            (name for name, item in self.items.items() if item.reference == reference), None
        )

    async def async_select_option(self, option):
        if option not in self.items:
            raise ServiceValidationError("Unknown selection")
        reference = self.items[option].reference
        if self.kind == "bouquet":
            await self.coordinator.select_bouquet(reference)
        else:
            await self.coordinator.perform(self.coordinator.client.command, "zap", sRef=reference)
