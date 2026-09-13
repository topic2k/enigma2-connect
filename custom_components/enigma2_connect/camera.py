# SPDX-License-Identifier: Apache-2.0
"""Authenticated screenshot fetch with bounded caching."""

import asyncio
from time import monotonic

from homeassistant.components.camera import Camera

from .api import ReceiverError
from .entity import EnigmaEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([EnigmaCamera(entry.runtime_data)])


class EnigmaCamera(EnigmaEntity, Camera):
    _attr_content_type = "image/jpeg"

    def __init__(self, coordinator):
        Camera.__init__(self)
        EnigmaEntity.__init__(self, coordinator, "screenshot")
        self._image = None
        self._fetched = 0.0
        self._image_lock = asyncio.Lock()

    async def async_camera_image(self, width=None, height=None):
        if not self.available or self.coordinator.data.state.standby:
            return None
        async with self._image_lock:
            if self._image is not None and monotonic() - self._fetched < 5:
                return self._image
            try:
                self._image = await self.coordinator.client.screenshot()
            except ReceiverError:
                return None
            self._fetched = monotonic()
            return self._image
