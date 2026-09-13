# SPDX-License-Identifier: Apache-2.0
"""UI setup, reauthentication, reconfiguration and runtime options."""

from __future__ import annotations

import ipaddress
import re
from uuid import uuid4

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import AuthenticationError, OpenWebifClient, ReceiverError
from .channel_media import CONF_CHANNEL_BOUQUET, CONF_SHOW_CHANNELS
from .const import DEFAULT_INTERVAL, DOMAIN
from .media_source import CONF_RECORDINGS_LAYOUT, recordings_layout
from .models import ReceiverState, Service, identity
from .recording_images import (
    CONF_IMAGE_GENERATION,
    CONF_IMAGE_SOURCES,
    CONF_IMAGE_URL,
    CONF_OMDB_KEY,
    CONF_SNAPSHOT_MINUTES,
    CONF_TMDB_KEY,
    DEFAULT_IMAGE_SOURCES,
    IMAGE_SOURCES,
    validate_image_options,
)


def bouquet_selector(bouquets: dict[str, Service], selected: str) -> selector.SelectSelector:
    """Use a label-rendering dropdown while retaining unavailable saved bouquets."""
    choices = [{"value": "", "label": "—"}]
    choices.extend({"value": item.reference, "label": label} for label, item in bouquets.items())
    if selected and not any(choice["value"] == selected for choice in choices):
        # Older manually entered references may not occur in the receiver's catalog.
        match = re.search(r'FROM BOUQUET "([^"]+)"', selected)
        label = match[1] if match else "Bouquet"
        choices.append({"value": selected, "label": label})
    return selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=choices,
            custom_value=False,
            mode=selector.SelectSelectorMode.DROPDOWN,
        )
    )


def host(value: str) -> str:
    if not isinstance(value, str):
        raise vol.Invalid("Enter a hostname or IP address")
    value = value.strip().strip("[]").lower().rstrip(".")
    try:
        return str(ipaddress.ip_address(value))
    except ValueError:
        if (
            not value
            or len(value) > 253
            or any(
                not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label)
                for label in value.split(".")
            )
        ):
            raise vol.Invalid("Enter a hostname or IP address") from None
        return value


def schema(defaults: dict) -> vol.Schema:
    username = vol.Optional("username")
    password = vol.Optional("password")
    if "username" in defaults:
        username = vol.Optional("username", description={"suggested_value": defaults["username"]})
    if "password" in defaults:
        password = vol.Optional("password", description={"suggested_value": defaults["password"]})
    return vol.Schema(
        {
            vol.Required("host", default=defaults.get("host", "")): selector.TextSelector(),
            vol.Required(
                "port",
                default=defaults.get("port") or (443 if defaults.get("use_https") else 80),
            ): cv.port,
            username: selector.TextSelector(),
            password: selector.TextSelector(
                selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
            ),
            vol.Required("use_https", default=defaults.get("use_https", False)): bool,
            vol.Required("verify_ssl", default=defaults.get("verify_ssl", True)): bool,
        }
    )


def make_client(hass, data: dict) -> OpenWebifClient:
    return OpenWebifClient(
        async_get_clientsession(hass, verify_ssl=data.get("verify_ssl", True)), **data
    )


class EnigmaFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def _configure(self, step: str, user_input: dict | None):
        entry = (
            self._get_reauth_entry()
            if step == "reauth_confirm"
            else self._get_reconfigure_entry()
            if step == "reconfigure"
            else None
        )
        errors = {}
        if user_input is not None:
            data = dict(user_input)
            data.setdefault("port", 443 if data.get("use_https") else 80)
            try:
                data["host"] = host(data["host"])
                client = make_client(self.hass, data)
                result = await client.get("about")
                info = result.get("info")
                if not isinstance(info, dict) or not info.get("model"):
                    raise ValueError("Not an OpenWebif receiver")
                ReceiverState.parse(await client.get("statusinfo"))
                hardware_id = identity(info)
            except vol.Invalid:
                errors["host"] = "invalid_host"
            except AuthenticationError:
                errors["base"] = "invalid_auth"
            except ReceiverError:
                errors["base"] = "cannot_connect"
            except ValueError, TypeError:
                errors["base"] = "invalid_response"
            else:
                for existing in self._async_current_entries():
                    if entry and existing.entry_id == entry.entry_id:
                        continue
                    if existing.data["host"] == data["host"] or (
                        hardware_id and existing.unique_id == hardware_id
                    ):
                        return self.async_abort(reason="already_configured")
                unique_id = hardware_id or f"host:{data['host']}"
                if entry:
                    # Address changes must still point to the originally paired hardware.
                    # Host-based fallback IDs cannot provide that identity check.
                    if not entry.unique_id.startswith("host:") and hardware_id != entry.unique_id:
                        return self.async_abort(reason="wrong_device")
                    return self.async_update_reload_and_abort(entry, data_updates=data)
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=str(info["model"]),
                    data=data,
                    options={CONF_RECORDINGS_LAYOUT: recordings_layout(self.hass)},
                )
        return self.async_show_form(
            step_id=step,
            data_schema=schema(user_input or (dict(entry.data) if entry else {})),
            errors=errors,
        )

    async def async_step_user(self, user_input=None):
        return await self._configure("user", user_input)

    async def async_step_reauth(self, entry_data):
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None):
        return await self._configure("reauth_confirm", user_input)

    async def async_step_reconfigure(self, user_input=None):
        return await self._configure("reconfigure", user_input)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return EnigmaOptions()


class EnigmaOptions(config_entries.OptionsFlowWithReload):
    async def async_step_init(self, user_input=None):
        return self.async_show_menu(step_id="init", menu_options=["settings", "regenerate_images"])

    async def async_step_regenerate_images(self, user_input=None):
        if not self.config_entry.options.get(CONF_IMAGE_SOURCES, DEFAULT_IMAGE_SOURCES):
            return self.async_abort(reason="images_disabled")
        # A fresh namespace bypasses both disk and browser caches. Reload cancels
        # existing jobs and starts bounded preparation with the saved sources.
        return self.async_create_entry(
            title="",
            data={**self.config_entry.options, CONF_IMAGE_GENERATION: uuid4().hex},
        )

    async def async_step_settings(self, user_input=None):
        errors = {}
        if user_input is not None:
            try:
                user_input = dict(user_input)
                user_input["receiver_timezone"] = cv.time_zone(user_input["receiver_timezone"])
            except vol.Invalid:
                errors["receiver_timezone"] = "invalid_timezone"
            else:
                errors.update(validate_image_options(user_input))
            if not errors:
                if CONF_IMAGE_GENERATION in self.config_entry.options:
                    user_input[CONF_IMAGE_GENERATION] = self.config_entry.options[
                        CONF_IMAGE_GENERATION
                    ]
                layout = user_input.get(CONF_RECORDINGS_LAYOUT, recordings_layout(self.hass))
                user_input[CONF_RECORDINGS_LAYOUT] = layout
                # One media-source tile serves all receivers, so its layout is shared.
                for entry in self.hass.config_entries.async_entries(DOMAIN):
                    if entry.entry_id != self.config_entry.entry_id:
                        self.hass.config_entries.async_update_entry(
                            entry, options={**entry.options, CONF_RECORDINGS_LAYOUT: layout}
                        )
                return self.async_create_entry(title="", data=user_input)
        options = {**self.config_entry.options, **(user_input or {})}
        coordinator = getattr(self.config_entry, "runtime_data", None)
        bouquets = coordinator.data.bouquets if coordinator and coordinator.data else {}
        return self.async_show_form(
            step_id="settings",
            errors=errors,
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_RECORDINGS_LAYOUT, default=recordings_layout(self.hass)
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=["receivers", "merged"],
                            translation_key="recordings_layout",
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    ),
                    vol.Required(
                        "scan_interval", default=options.get("scan_interval", DEFAULT_INTERVAL)
                    ): vol.All(int, vol.Range(min=5, max=300)),
                    vol.Required(
                        CONF_SHOW_CHANNELS, default=options.get(CONF_SHOW_CHANNELS, False)
                    ): selector.BooleanSelector(),
                    vol.Optional(
                        CONF_CHANNEL_BOUQUET, default=options.get(CONF_CHANNEL_BOUQUET, "")
                    ): bouquet_selector(bouquets, options.get(CONF_CHANNEL_BOUQUET, "")),
                    vol.Required(
                        CONF_IMAGE_SOURCES,
                        default=options.get(CONF_IMAGE_SOURCES, DEFAULT_IMAGE_SOURCES),
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=list(IMAGE_SOURCES),
                            multiple=True,
                            translation_key="recording_image_sources",
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    ),
                    vol.Required(
                        CONF_SNAPSHOT_MINUTES, default=options.get(CONF_SNAPSHOT_MINUTES, 10)
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=0,
                            max=1440,
                            step=0.1,
                            unit_of_measurement="min",
                            mode=selector.NumberSelectorMode.BOX,
                        )
                    ),
                    vol.Optional(
                        CONF_TMDB_KEY, default=options.get(CONF_TMDB_KEY, "")
                    ): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.PASSWORD,
                        )
                    ),
                    vol.Optional(
                        CONF_OMDB_KEY, default=options.get(CONF_OMDB_KEY, "")
                    ): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.PASSWORD,
                        )
                    ),
                    vol.Optional(
                        CONF_IMAGE_URL, default=options.get(CONF_IMAGE_URL, "")
                    ): selector.TextSelector(),
                    vol.Optional("bouquet", default=options.get("bouquet", "")): bouquet_selector(
                        bouquets, options.get("bouquet", "")
                    ),
                    vol.Required(
                        "receiver_timezone",
                        default=options.get("receiver_timezone", self.hass.config.time_zone),
                    ): selector.TextSelector(),
                    vol.Required(
                        "artwork", default=options.get("artwork", "picon")
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=["picon", "screenshot", "none"],
                            translation_key="artwork",
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    ),
                    vol.Required(
                        "message_timeout", default=options.get("message_timeout", 10)
                    ): vol.All(int, vol.Range(min=1, max=120)),
                    vol.Required("message_type", default=options.get("message_type", 1)): vol.All(
                        int, vol.Range(min=0, max=3)
                    ),
                    vol.Required(
                        "off_mode", default=options.get("off_mode", "standby")
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=["standby", "deep_standby"],
                            translation_key="off_mode",
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    ),
                }
            ),
        )
