# SPDX-License-Identifier: Apache-2.0
"""Device-scoped actions with mandatory, unambiguous receiver targeting."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant, ServiceCall

    from .coordinator import EnigmaConfigEntry, EnigmaCoordinator

import voluptuous as vol
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import ServiceResponse, SupportsResponse, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import device_registry as dr

from .action_choices import action_epoch, resolve_choices
from .const import DOMAIN
from .models import epoch, timer_range
from .recording_library import PROGRESS_FILTERS
from .timer_edit import WEEKDAYS, options
from .workflow_models import TimerIdentity


@callback
def register_services(hass: HomeAssistant) -> None:
    def resolve(device_id: str) -> EnigmaCoordinator:
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
        return cast("EnigmaConfigEntry", entries[0]).runtime_data

    async def handle(call: ServiceCall) -> ServiceResponse:
        coordinator = resolve(call.data["device_id"])
        params = dict(call.data)
        params.pop("device_id")
        service = call.service
        if service.startswith("timer_"):
            try:
                resolve_choices(
                    params,
                    coordinator.entry.entry_id,
                    "old_service_reference" if service == "timer_edit" else "service_reference",
                )
            except ValueError as err:
                raise ServiceValidationError(
                    translation_domain=DOMAIN, translation_key="invalid_action_choice"
                ) from err
            try:
                for key in ("begin", "end", "old_begin", "old_end"):
                    if key in params:
                        params[key] = action_epoch(params[key], hass.config.time_zone)
            except ValueError as err:
                raise ServiceValidationError(
                    translation_domain=DOMAIN, translation_key="invalid_time"
                ) from err
        if service == "timer_edit":
            try:
                old = TimerIdentity(
                    params.pop("old_service_reference"),
                    epoch(params.pop("old_begin")),
                    epoch(params.pop("old_end")),
                )
                if old.end < old.begin:
                    raise ValueError("Invalid old interval")
                for key in ("begin", "end"):
                    if key in params:
                        params[key] = epoch(params[key])
            except ValueError as err:
                raise ServiceValidationError(
                    translation_domain=DOMAIN, translation_key="invalid_time"
                ) from err
            scope = params.pop("scope")
            result = await coordinator.async_timer_edit(old, params, scope)
            return result if call.return_response else None
        if service in ("epg_search", "epg_similar", "record_event"):
            if service == "epg_search":
                return await coordinator.perform(coordinator.epg.search, refresh=False, **params)
            if service == "epg_similar":
                return await coordinator.perform(coordinator.epg.similar, params, refresh=False)
            result = await coordinator.async_record_event(params)
            return result if call.return_response else None
        if service == "recordings_list":
            return await coordinator.perform(
                coordinator.recording_library.list, refresh=False, **params
            )
        if service == "record_now":
            result = await coordinator.async_record_now()
            return result if call.return_response else None
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
                params = options(params)
                params.setdefault("disabled", 0)
                params["eit"] = 0
        is_timer = service.startswith("timer_")
        try:
            method = (
                coordinator.client.command_result
                if call.return_response
                else coordinator.client.command
            )
            await coordinator.perform(
                method,
                endpoint,
                refresh=False,
                timer_action=service if is_timer else None,
                **params,
            )
        except asyncio.CancelledError:
            if is_timer:
                coordinator.invalidate_lists()
            raise
        except HomeAssistantError:
            if is_timer:
                # Even a rejected edit may have changed receiver state on some images.
                coordinator.invalidate_lists()
                await coordinator.async_request_refresh()
            raise
        if is_timer:
            coordinator.invalidate_lists()
            await coordinator.async_request_refresh()
            if call.return_response:
                identity = TimerIdentity(params["sRef"], params["begin"], params["end"])
                return {"action": service, "timer": identity.response()}
        return None

    base: dict[Any, Any] = {vol.Required("device_id"): str}
    timer = {
        **base,
        vol.Optional("service_reference"): vol.All(str, vol.Strip, vol.Length(min=1)),
        vol.Optional("channel"): str,
        vol.Required("begin"): vol.Any(str, int),
        vol.Required("end"): vol.Any(str, int),
    }
    extra = {
        vol.Optional("directory_selection"): str,
        vol.Optional("weekdays"): [vol.In(WEEKDAYS)],
        vol.Optional("directory"): vol.All(str, vol.Match(r"^(?:/[^\x00\r\n]*|)\Z")),
        vol.Optional("tags"): [vol.All(str, vol.Match(r"^\S+\Z"))],
        vol.Optional("disabled"): bool,
        vol.Optional("recording_type"): vol.In(("normal", "descrambled", "scrambled")),
    }
    enum_number = vol.All(
        vol.Any(vol.All(int, vol.Range(min=0, max=3)), vol.In(("0", "1", "2", "3"))),
        vol.Coerce(int),
    )

    def exact_integer(value: Any) -> int:
        if type(value) is not int:
            raise vol.Invalid("Expected integer")
        return value

    event = {
        **base,
        vol.Required("service_reference"): vol.All(str, vol.Strip, vol.Length(min=1)),
        vol.Required("event_id"): vol.All(exact_integer, vol.Range(min=0)),
        vol.Required("begin"): vol.All(exact_integer, vol.Range(min=1)),
        vol.Required("end"): vol.All(exact_integer, vol.Range(min=1)),
    }
    schemas = {
        "recordings_list": {
            **base,
            vol.Optional("query"): vol.All(str, vol.Strip, vol.Length(max=200)),
            vol.Optional("tag"): str,
            vol.Optional("directory"): str,
            vol.Optional("progress", default="all"): vol.In(PROGRESS_FILTERS),
        },
        "epg_search": {
            **base,
            vol.Required("query"): vol.All(str, vol.Strip, vol.Length(min=1, max=200)),
        },
        "epg_similar": event,
        "record_event": event,
        "record_now": base,
        "reboot": base,
        "restart_gui": base,
        "deep_standby": base,
        "message": {
            **base,
            vol.Required("text"): str,
            vol.Optional("type", default=1): enum_number,
            vol.Optional("timeout", default=10): vol.All(int, vol.Range(min=1, max=120)),
        },
        "timer_add": {
            **timer,
            **extra,
            vol.Required("name"): str,
            vol.Optional("description", default=""): str,
            vol.Optional("justplay", default=False): bool,
            vol.Optional("afterevent", default=3): enum_number,
        },
        "timer_edit": {
            **base,
            **extra,
            vol.Optional("old_service_reference"): vol.All(str, vol.Strip, vol.Length(min=1)),
            vol.Optional("channel"): str,
            vol.Required("old_begin"): vol.Any(str, int),
            vol.Required("old_end"): vol.Any(str, int),
            vol.Required("scope"): vol.In(("single", "series")),
            vol.Optional("begin"): vol.Any(str, int),
            vol.Optional("end"): vol.Any(str, int),
            vol.Optional("name"): str,
            vol.Optional("description"): str,
            vol.Optional("justplay"): bool,
            vol.Optional("afterevent"): enum_number,
        },
        "timer_delete": timer,
        "timer_toggle": timer,
    }
    for name, schema in schemas.items():
        hass.services.async_register(
            DOMAIN,
            name,
            handle,
            schema=vol.Schema(schema),
            supports_response=SupportsResponse.ONLY
            if name.startswith("epg_") or name == "recordings_list"
            else SupportsResponse.OPTIONAL
            if name.startswith("timer_") or name in ("record_now", "record_event")
            else SupportsResponse.NONE,
        )
