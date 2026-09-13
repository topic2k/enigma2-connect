# SPDX-License-Identifier: Apache-2.0
"""Allowlist diagnostics: never export connection, channel or recording data."""


async def async_get_config_entry_diagnostics(hass, entry):
    coordinator = entry.runtime_data
    data = coordinator.data
    return {
        "last_update_success": coordinator.last_update_success,
        "optional_endpoint_errors": sorted(coordinator.optional_errors),
        "poll_seconds": coordinator.update_interval.total_seconds(),
        "counts": {
            "bouquets": len(data.bouquets),
            "channels": len(data.channels),
            "timers": len(data.timers) if data.timers is not None else None,
            "recordings": len(data.movies) if data.movies is not None else None,
        },
    }
