# SPDX-License-Identifier: Apache-2.0
"""Enigma2 Connect: a local OpenWebif integration."""

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .api import OpenWebifClient, power_command_middleware
from .const import DEFAULT_INTERVAL, DOMAIN
from .coordinator import EnigmaConfigEntry, EnigmaCoordinator
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


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    register_services(hass)
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
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: EnigmaConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
