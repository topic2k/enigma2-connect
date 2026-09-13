# SPDX-License-Identifier: Apache-2.0
"""Actual receiver states and transport reachability."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

    from .coordinator import EnigmaConfigEntry, EnigmaCoordinator

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.const import EntityCategory

from .entity import EnigmaEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EnigmaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities(
        EnigmaBinarySensor(entry.runtime_data, key)
        for key in ("standby", "recording", "streaming", "connection")
    )


class EnigmaBinarySensor(EnigmaEntity, BinarySensorEntity):
    def __init__(self, coordinator: EnigmaCoordinator, key: str) -> None:
        super().__init__(coordinator, key)
        self.key = key
        if key == "connection":
            self._attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
            self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def available(self) -> bool:
        # Keep connectivity visible as off when polling fails, rather than unavailable.
        return True if self.key == "connection" else super().available

    @property
    def is_on(self) -> bool | None:
        return (
            self.coordinator.last_update_success
            if self.key == "connection"
            else getattr(self.coordinator.data.state, self.key)
        )
