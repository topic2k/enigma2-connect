# SPDX-License-Identifier: Apache-2.0
"""Shared device identity for all receiver entities."""

from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo, format_mac
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import EnigmaCoordinator
from .models import identity


class EnigmaEntity(CoordinatorEntity[EnigmaCoordinator]):
    _attr_has_entity_name = True

    def __init__(self, coordinator: EnigmaCoordinator, key: str) -> None:
        super().__init__(coordinator)
        assert coordinator.entry.unique_id is not None  # Every supported config flow sets an ID.
        self._attr_unique_id = f"{coordinator.entry.unique_id}_{key}"
        self._attr_translation_key = key
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.entry.unique_id)},
            name=coordinator.entry.title,
            manufacturer=coordinator.info.get("brand"),
            model=coordinator.info.get("model"),
            sw_version=coordinator.info.get("webifver"),
            configuration_url=str(coordinator.client.base_url),
        )
        if mac := identity(coordinator.info):
            self._attr_device_info["connections"] = {(CONNECTION_NETWORK_MAC, format_mac(mac))}
