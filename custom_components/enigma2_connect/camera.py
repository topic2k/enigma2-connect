# SPDX-License-Identifier: Apache-2.0
"""Authenticated screenshot fetch with bounded caching."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

    from .coordinator import EnigmaConfigEntry, EnigmaCoordinator

import asyncio
from time import monotonic

from homeassistant.components.camera import Camera

from .api import ReceiverError
from .entity import EnigmaEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EnigmaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities([EnigmaCamera(entry.runtime_data)])


class EnigmaCamera(EnigmaEntity, Camera):
    _attr_content_type = "image/jpeg"

    def __init__(self, coordinator: EnigmaCoordinator) -> None:
        Camera.__init__(self)
        EnigmaEntity.__init__(self, coordinator, "screenshot")
        self._image: bytes | None = None
        self._fetched = 0.0
        self._image_lock = asyncio.Lock()

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        if not self.available or self.coordinator.data.state.standby:
            return None
        # Check the cache inside the lock so concurrent viewers share one capture.
        async with self._image_lock:
            if self._image is not None and monotonic() - self._fetched < 5:
                return self._image
            try:
                self._image = await self.coordinator.client.screenshot()
            except ReceiverError:
                return None
            self._fetched = monotonic()
            return self._image
