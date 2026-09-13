# SPDX-License-Identifier: Apache-2.0
"""Allowlist diagnostics: never export connection, channel or recording data."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any

    from homeassistant.core import HomeAssistant

    from .coordinator import EnigmaConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: EnigmaConfigEntry
) -> dict[str, Any]:
    coordinator = getattr(entry, "runtime_data", None)
    if coordinator is None:
        return {"loaded": False}
    data = coordinator.data
    return {
        "last_update_success": coordinator.last_update_success,
        "optional_endpoint_errors": sorted(coordinator.optional_errors),
        "poll_seconds": (
            coordinator.update_interval.total_seconds() if coordinator.update_interval else None
        ),
        "counts": {
            "bouquets": len(data.bouquets) if data else None,
            "channels": len(data.channels) if data else None,
            "timers": len(data.timers) if data and data.timers is not None else None,
            "recordings": len(data.movies) if data and data.movies is not None else None,
        },
    }
