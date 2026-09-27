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
        for key in ("standby", "recording", "streaming", "connection", "timeshift", "sleep_timer")
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
        if self.key == "sleep_timer":
            return super().available and self.coordinator.data.sleep_timer is not None
        if self.key == "timeshift":
            return super().available and self.coordinator.data.timeshift is not None
        # Keep connectivity visible as off when polling fails, rather than unavailable.
        return True if self.key == "connection" else super().available

    @property
    def is_on(self) -> bool | None:
        if self.key == "sleep_timer":
            timer = self.coordinator.data.sleep_timer
            return timer.enabled if timer else None
        if self.key == "timeshift":
            return self.coordinator.data.timeshift
        return (
            self.coordinator.last_update_success
            if self.key == "connection"
            else getattr(self.coordinator.data.state, self.key)
        )

    @property
    def extra_state_attributes(self) -> dict[str, str | int | None] | None:
        if self.key != "sleep_timer" or (timer := self.coordinator.data.sleep_timer) is None:
            return None
        return {"reported_minutes": timer.minutes, "action": timer.action}
