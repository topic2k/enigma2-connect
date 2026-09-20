# SPDX-License-Identifier: Apache-2.0
"""Receiver-labelled action choices and explicit handling of local UI times."""

from __future__ import annotations

import json
from copy import deepcopy
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from homeassistant.helpers.service import async_set_service_schema

from .const import DOMAIN
from .models import JsonObject, epoch

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.core import HomeAssistant

    from .coordinator import EnigmaCoordinator

CHOICES_KEY = f"{DOMAIN}_action_choices"
TIMER_ACTIONS = ("timer_add", "timer_edit", "timer_delete", "timer_toggle")


def action_epoch(value: str | int, timezone: str) -> int:
    """The native selector supplies a wall-clock string in HA's configured zone."""
    if isinstance(value, str):
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            zone = ZoneInfo(timezone)
            candidates = set()
            for fold in (0, 1):
                local = parsed.replace(tzinfo=zone, fold=fold)
                if local.astimezone(UTC).astimezone(zone).replace(tzinfo=None) == parsed:
                    candidates.add(int(local.timestamp()))
            if len(candidates) != 1:
                raise ValueError("Ambiguous or nonexistent local time")
            return candidates.pop()
    return epoch(value)


def choice(entry_id: str, kind: str, value: str) -> str:
    return json.dumps([entry_id, kind, value], ensure_ascii=False, separators=(",", ":"))


def selected(value: str, entry_id: str, kind: str) -> str:
    try:
        decoded = json.loads(value)
    except ValueError as err:
        raise ValueError("Invalid receiver choice") from err
    if (
        not isinstance(decoded, list)
        or len(decoded) != 3
        or decoded[:2] != [entry_id, kind]
        or not isinstance(decoded[2], str)
        or not decoded[2].strip()
    ):
        raise ValueError("Choice does not match this receiver and field")
    result = decoded[2].strip() if kind == "channel" else decoded[2]
    if kind == "directory" and not valid_directory(result):
        raise ValueError("Invalid recording directory")
    return result


def resolve_choices(params: JsonObject, entry_id: str, reference_key: str) -> None:
    """Keep explicit YAML references/paths as alternatives, never guess precedence."""
    if ("channel" in params) == (reference_key in params):
        raise ValueError("Choose exactly one channel input")
    if "channel" in params:
        params[reference_key] = selected(params.pop("channel"), entry_id, "channel")
    if "directory_selection" in params:
        if "directory" in params:
            raise ValueError("Choose one recording directory input")
        params["directory"] = selected(params.pop("directory_selection"), entry_id, "directory")


def valid_directory(value: object) -> bool:
    return (
        isinstance(value, str) and value.startswith("/") and not any(c in value for c in "\x00\r\n")
    )


def recording_directories(
    timers: JsonObject | None, movie_directory: str | None
) -> tuple[str, ...]:
    """Bookmarks, default and known timer/movie paths, not a filesystem explorer."""
    data = timers or {}
    locations = data.get("locations")
    values = list(locations) if isinstance(locations, list) else []
    values.extend((data.get("default"), movie_directory))
    rows = data.get("timers")
    if isinstance(rows, list):
        values.extend(row.get("dirname") for row in rows if isinstance(row, dict))
    return tuple(sorted({value for value in values if valid_directory(value)}))


class ActionChoices:
    """Publish shared HA action descriptions without mixing receiver identities."""

    def __init__(self, hass: HomeAssistant, descriptions: JsonObject) -> None:
        self.hass = hass
        self.descriptions = deepcopy(descriptions)
        self.receivers: dict[str, tuple[list[JsonObject], list[JsonObject]]] = {}

    def bind(self, coordinator: EnigmaCoordinator) -> Callable[[], None]:
        entry = coordinator.entry

        def update() -> None:
            # A failed poll must not advertise cached data as a current catalog.
            channels: list[JsonObject] = []
            directories: list[JsonObject] = []
            if coordinator.last_update_success:
                channels = [
                    {
                        "label": f"{entry.title} · {name}",
                        "value": choice(entry.entry_id, "channel", item.reference),
                    }
                    for name, item in coordinator.data.channels.items()
                ]
                directories = [
                    {
                        "label": f"{entry.title} · {path}",
                        "value": choice(entry.entry_id, "directory", path),
                    }
                    for path in coordinator.data.recording_directories
                ]
            current = (channels, directories)
            if self.receivers.get(entry.entry_id) != current:
                self.receivers[entry.entry_id] = current
                self.publish()

        remove_listener = coordinator.async_add_listener(update)
        update()

        def remove() -> None:
            remove_listener()
            self.receivers.pop(entry.entry_id, None)
            self.publish()

        return remove

    def publish(self) -> None:
        channels = [item for values in self.receivers.values() for item in values[0]]
        directories = [item for values in self.receivers.values() for item in values[1]]
        for action in TIMER_ACTIONS:
            schema = deepcopy(self.descriptions[action])
            fields = schema["fields"]
            fields["channel"]["selector"]["select"]["options"] = channels
            if "directory_selection" in fields:
                fields["directory_selection"]["selector"]["select"]["options"] = directories
            async_set_service_schema(self.hass, DOMAIN, action, schema)
