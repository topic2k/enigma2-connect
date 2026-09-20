# SPDX-License-Identifier: Apache-2.0
"""Optional individual remote keys and catalog refresh."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

    from .coordinator import EnigmaConfigEntry, EnigmaCoordinator

from homeassistant.components.button import ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN, KEYS
from .entity import EnigmaEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EnigmaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities(
        [EnigmaKey(entry.runtime_data, name, code) for name, code in KEYS.items()]
        + [
            EnigmaRefresh(entry.runtime_data, "refresh"),
            EnigmaRecordNow(entry.runtime_data, "record_now"),
        ]
    )


class EnigmaKey(EnigmaEntity, ButtonEntity):
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: EnigmaCoordinator, name: str, code: int) -> None:
        super().__init__(coordinator, f"key_{name}")
        self.code = code

    async def async_press(self) -> None:
        await self.coordinator.perform(self.coordinator.client.keys, [self.code])


class EnigmaRecordNow(EnigmaEntity, ButtonEntity):
    async def async_press(self) -> None:
        await self.coordinator.async_record_now()


class EnigmaRefresh(EnigmaEntity, ButtonEntity):
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    async def async_press(self) -> None:
        self.coordinator.invalidate_lists()
        # A user action must wait for its own result, not a debounced future poll.
        await self.coordinator.async_refresh()
        if not self.coordinator.last_update_success:
            raise HomeAssistantError(translation_domain=DOMAIN, translation_key="cannot_update")
