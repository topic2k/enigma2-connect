# SPDX-License-Identifier: Apache-2.0
"""Optional individual remote keys and catalog refresh."""

from homeassistant.components.button import ButtonEntity
from homeassistant.helpers.entity import EntityCategory

from .const import KEYS
from .entity import EnigmaEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities(
        [EnigmaKey(entry.runtime_data, name, code) for name, code in KEYS.items()]
        + [EnigmaRefresh(entry.runtime_data, "refresh")]
    )


class EnigmaKey(EnigmaEntity, ButtonEntity):
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator, name, code):
        super().__init__(coordinator, f"key_{name}")
        self.code = code

    async def async_press(self):
        await self.coordinator.perform(self.coordinator.client.keys, [self.code])


class EnigmaRefresh(EnigmaEntity, ButtonEntity):
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    async def async_press(self):
        self.coordinator.invalidate_lists()
        await self.coordinator.async_request_refresh()
