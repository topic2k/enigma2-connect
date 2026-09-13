# SPDX-License-Identifier: Apache-2.0
"""Device-scoped actions with mandatory, unambiguous receiver targeting."""

import voluptuous as vol
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN
from .models import timer_range


@callback
def register_services(hass):
    def resolve(device_id):
        device = dr.async_get(hass).async_get(device_id)
        entries = [
            entry
            for entry in hass.config_entries.async_entries(DOMAIN)
            if device
            and entry.entry_id in device.config_entries
            and entry.state is ConfigEntryState.LOADED
        ]
        if len(entries) != 1:
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="invalid_target"
            )
        return entries[0].runtime_data

    async def handle(call):
        coordinator = resolve(call.data["device_id"])
        params = dict(call.data)
        params.pop("device_id")
        service = call.service
        if service in ("reboot", "restart_gui", "deep_standby"):
            endpoint = "powerstate"
            params = {"newstate": {"reboot": 2, "restart_gui": 3, "deep_standby": 1}[service]}
        elif service == "message":
            endpoint = "message"
        else:
            endpoint = {
                "timer_add": "timeradd",
                "timer_delete": "timerdelete",
                "timer_toggle": "timertogglestatus",
            }[service]
            try:
                params["begin"], params["end"] = timer_range(params["begin"], params["end"])
            except ValueError as err:
                raise ServiceValidationError(
                    translation_domain=DOMAIN, translation_key="invalid_time"
                ) from err
            params["sRef"] = params.pop("service_reference")
            if service == "timer_add":
                params.update(justplay=int(params["justplay"]), disabled=0, eit=0)
        await coordinator.perform(coordinator.client.command, endpoint, refresh=False, **params)
        if service.startswith("timer_"):
            # Bypass the slow list deadline so calendar and counts reflect the action.
            coordinator.invalidate_lists()
            await coordinator.async_request_refresh()

    base = {vol.Required("device_id"): str}
    timer = {
        **base,
        vol.Required("service_reference"): str,
        vol.Required("begin"): vol.Any(str, int),
        vol.Required("end"): vol.Any(str, int),
    }
    schemas = {
        "reboot": base,
        "restart_gui": base,
        "deep_standby": base,
        "message": {
            **base,
            vol.Required("text"): str,
            vol.Optional("type", default=1): vol.All(int, vol.Range(min=0, max=3)),
            vol.Optional("timeout", default=10): vol.All(int, vol.Range(min=1, max=120)),
        },
        "timer_add": {
            **timer,
            vol.Required("name"): str,
            vol.Optional("description", default=""): str,
            vol.Optional("justplay", default=False): bool,
            vol.Optional("afterevent", default=3): vol.All(int, vol.Range(min=0, max=3)),
        },
        "timer_delete": timer,
        "timer_toggle": timer,
    }
    for name, schema in schemas.items():
        hass.services.async_register(DOMAIN, name, handle, schema=vol.Schema(schema))
