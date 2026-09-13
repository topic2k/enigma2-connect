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

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription, SensorStateClass
from homeassistant.const import EntityCategory

from .entity import EnigmaEntity
from .models import Snapshot, number, signal_snr_db

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class Description(SensorEntityDescription):
    value: Callable[[Snapshot], str | int | float | None]


DESCRIPTIONS = (
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
