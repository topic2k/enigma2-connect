# SPDX-License-Identifier: Apache-2.0
"""Actual receiver states and transport reachability."""

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.helpers.entity import EntityCategory

from .entity import EnigmaEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities(
        EnigmaBinarySensor(entry.runtime_data, key)
        for key in ("standby", "recording", "streaming", "connection")
    )


class EnigmaBinarySensor(EnigmaEntity, BinarySensorEntity):
    def __init__(self, coordinator, key):
        super().__init__(coordinator, key)
        self.key = key
        if key == "connection":
            self._attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
            self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def available(self):
        return True if self.key == "connection" else super().available

    @property
    def is_on(self):
        return (
            self.coordinator.last_update_success
            if self.key == "connection"
            else getattr(self.coordinator.data.state, self.key)
        )
