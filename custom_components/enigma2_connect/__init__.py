# SPDX-License-Identifier: Apache-2.0
"""Enigma2 Connect: a local OpenWebif integration."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any

from homeassistant.const import EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import Event, HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .api import OpenWebifClient, power_command_middleware
from .channel_media import ChannelPiconView
from .const import DEFAULT_INTERVAL, DOMAIN
from .coordinator import EnigmaConfigEntry, EnigmaCoordinator
from .media_stream import MediaStreamView
from .recording_images import RecordingThumbnailView, async_check_snapshot_support
from .services import register_services

PLATFORMS = [
    Platform.MEDIA_PLAYER,
    Platform.REMOTE,
    Platform.NOTIFY,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.CAMERA,
    Platform.CALENDAR,
    Platform.BUTTON,
]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    register_services(hass)
    hass.http.register_view(RecordingThumbnailView(hass))
    hass.http.register_view(ChannelPiconView(hass))
    hass.http.register_view(MediaStreamView(hass))
    return True


async def async_setup_entry(hass: HomeAssistant, entry: EnigmaConfigEntry) -> bool:
    coordinator = EnigmaCoordinator(
        hass,
        entry,
        OpenWebifClient(
            async_create_clientsession(
                hass,
                verify_ssl=entry.data.get("verify_ssl", True),
                middlewares=(power_command_middleware,),
            ),
            **dict(entry.data),
        ),
        entry.options.get("scan_interval", DEFAULT_INTERVAL),
    )
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    async def stop_stream(_event: Event) -> None:
        await coordinator.media_stream.async_close()

    entry.async_on_unload(hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, stop_stream))
    await async_check_snapshot_support(hass, entry)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    coordinator.recording_images.async_start()
    return True


async def async_unload_entry(hass: HomeAssistant, entry: EnigmaConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        await entry.runtime_data.media_stream.async_close()
        await entry.runtime_data.recording_images.async_close()
    return unloaded


async def async_remove_entry(hass: HomeAssistant, entry: EnigmaConfigEntry) -> None:
    """Discard the receiver-specific repair when its configuration is removed."""
    ir.async_delete_issue(hass, DOMAIN, f"{entry.entry_id}_snapshot_binary")
