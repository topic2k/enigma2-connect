# SPDX-License-Identifier: Apache-2.0
"""Selections share coordinator data; no startup dispatcher race."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

    from .coordinator import EnigmaConfigEntry, EnigmaCoordinator
    from .models import Service

from homeassistant.components.select import SelectEntity
from homeassistant.exceptions import ServiceValidationError

from .const import DOMAIN
from .entity import EnigmaEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EnigmaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities(
        [EnigmaSelect(entry.runtime_data, kind) for kind in ("bouquet", "channel")]
        + [EnigmaAudioSelect(entry.runtime_data)]
    )


class EnigmaSelect(EnigmaEntity, SelectEntity):
    def __init__(self, coordinator: EnigmaCoordinator, kind: str) -> None:
        super().__init__(coordinator, f"select_{kind}")
        self.kind = kind

    @property
    def items(self) -> dict[str, Service]:
        return (
            self.coordinator.data.bouquets
            if self.kind == "bouquet"
            else self.coordinator.data.channels
        )

    @property
    def options(self) -> list[str]:
        return list(self.items)

    @property
    def current_option(self) -> str | None:
        reference = (
            self.coordinator.data.bouquet
            if self.kind == "bouquet"
            else self.coordinator.data.state.reference
        )
        return next(
            (name for name, item in self.items.items() if item.reference == reference), None
        )

    async def async_select_option(self, option: str) -> None:
        if option not in self.items:
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="unknown_selection"
            )
        reference = self.items[option].reference
        if self.kind == "bouquet":
            await self.coordinator.select_bouquet(reference)
        else:
            await self.coordinator.perform(self.coordinator.client.command, "zap", sRef=reference)


class EnigmaAudioSelect(EnigmaEntity, SelectEntity):
    def __init__(self, coordinator: EnigmaCoordinator) -> None:
        super().__init__(coordinator, "select_audio_track")

    @property
    def available(self) -> bool:
        return (
            super().available
            and not self.coordinator.data.state.standby
            and bool(self.coordinator.data.audio_tracks)
        )

    @property
    def options(self) -> list[str]:
        return [track.option for track in self.coordinator.data.audio_tracks or ()]

    @property
    def current_option(self) -> str | None:
        return next(
            (track.option for track in self.coordinator.data.audio_tracks or () if track.active),
            None,
        )

    async def async_select_option(self, option: str) -> None:
        track = next(
            (track for track in self.coordinator.data.audio_tracks or () if track.option == option),
            None,
        )
        if not self.available or track is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="unknown_selection"
            )
        await self.coordinator.select_audio_track(self.coordinator.data.state.reference, track)
