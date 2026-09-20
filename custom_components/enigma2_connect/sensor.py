# SPDX-License-Identifier: Apache-2.0
"""EPG and measured tuner data, without invented zero values."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

    from .coordinator import EnigmaConfigEntry, EnigmaCoordinator

from dataclasses import dataclass
from typing import Callable

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import EntityCategory, UnitOfInformation, UnitOfTime
from homeassistant.core import callback

from .entity import EnigmaEntity
from .models import Snapshot, number, signal_snr_db

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class Description(SensorEntityDescription):
    value: Callable[[Snapshot], str | int | float | None]


DESCRIPTIONS = (
    Description(
        key="ram_free",
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.MEBIBYTES,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value=lambda d: d.system.ram_free_bytes,
    ),
    Description(
        key="ram_total",
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.MEBIBYTES,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value=lambda d: d.system.ram_total_bytes,
    ),
    Description(
        key="uptime",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_unit_of_measurement=UnitOfTime.HOURS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value=lambda d: d.system.uptime_seconds,
    ),
    Description(key="channel", value=lambda d: d.state.channel),
    Description(key="now", value=lambda d: d.state.title),
    Description(key="next", value=lambda d: d.state.next_title),
    Description(
        key="signal",
        native_unit_of_measurement="%",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value=lambda d: number((d.signal or {}).get("snr")),
    ),
    Description(
        key="snr",
        native_unit_of_measurement="dB",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value=lambda d: signal_snr_db(d.signal),
    ),
    Description(
        key="ber",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value=lambda d: number((d.signal or {}).get("ber")),
    ),
    Description(key="recordings", value=lambda d: len(d.movies) if d.movies is not None else None),
    Description(key="timers", value=lambda d: len(d.timers) if d.timers is not None else None),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EnigmaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities(
        EnigmaSensor(entry.runtime_data, description) for description in DESCRIPTIONS
    )

    known_mounts: set[str] = set()

    @callback
    def add_disks() -> None:
        entities = []
        for disk in entry.runtime_data.data.system.disks:
            if disk.mount not in known_mounts:
                known_mounts.add(disk.mount)
                entities.append(EnigmaDiskSensor(entry.runtime_data, disk.mount))
        if entities:
            async_add_entities(entities)

    add_disks()
    entry.async_on_unload(entry.runtime_data.async_add_listener(add_disks))


class EnigmaSensor(EnigmaEntity, SensorEntity):
    entity_description: Description

    def __init__(self, coordinator: EnigmaCoordinator, description: Description) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description
        self._attr_translation_key = description.key

    @property
    def native_value(self) -> str | int | float | None:
        value = self.entity_description.value(self.coordinator.data)
        return value[:255] if isinstance(value, str) else value


class EnigmaDiskSensor(EnigmaEntity, SensorEntity):
    """Free filesystem space keyed by mount, stable across list reordering."""

    _attr_translation_key = "disk_free"
    _attr_device_class = SensorDeviceClass.DATA_SIZE
    _attr_native_unit_of_measurement = UnitOfInformation.BYTES
    _attr_suggested_unit_of_measurement = UnitOfInformation.GIBIBYTES
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: EnigmaCoordinator, mount: str) -> None:
        super().__init__(coordinator, f"disk_free_{mount}")
        self._mount = mount
        self._attr_translation_key = "disk_free"
        self._attr_translation_placeholders = {"mount": mount}

    @property
    def native_value(self) -> float | None:
        return next(
            (
                disk.free_bytes
                for disk in self.coordinator.data.system.disks
                if disk.mount == self._mount
            ),
            None,
        )

    @property
    def available(self) -> bool:
        return super().available and self.native_value is not None
