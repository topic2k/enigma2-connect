# SPDX-License-Identifier: Apache-2.0
"""System measurements and dynamic sensors using simulated receiver responses."""

from unittest.mock import patch

import pytest
from homeassistant.helpers import entity_registry as er

from custom_components.enigma2_connect.api import AuthenticationError, ConnectionError
from custom_components.enigma2_connect.sensor import DESCRIPTIONS, EnigmaSensor
from custom_components.enigma2_connect.system_diagnostics import (
    SystemDiagnostics,
    memory_bytes,
    uptime_seconds,
)

from .test_integration import setup


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("0 MB", 0),
        ("1024 kB", 1024**2),
        ("1.5 GB", 1.5 * 1024**3),
        ("1,5 GiB", 1.5 * 1024**3),
        (" 2 TB ", 2 * 1024**4),
        ("12 B", 12),
        ("1024 MiB", 1024**3),
        (None, None),
        (True, None),
        (12, None),
        ("-1 MB", None),
        ("?", None),
        ("NaN GB", None),
        ("1 PB", None),
        ("9" * 400 + " GB", None),
        ("", None),
        ("1.2.3 MB", None),
    ],
)
def test_memory_units(value, expected):
    assert memory_bytes(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("0:00", 0),
        ("24:00", 86400),
        ("1d 02:03", 93780),
        (" 12:59 ", 46740),
        (None, None),
        (13, None),
        ("?", None),
        ("1d 24:00", None),
        ("12:60", None),
        ("-1:00", None),
        ("9" * 5000 + ":00", None),
    ],
)
def test_uptime(value, expected):
    assert uptime_seconds(value) == expected


def test_about_validation_and_order():
    assert SystemDiagnostics.parse(None) == SystemDiagnostics()
    assert SystemDiagnostics.parse({"hdd": {}}) == SystemDiagnostics()
    parsed = SystemDiagnostics.parse(
        {
            "hdd": [
                None,
                {},
                {"mount": False},
                {"mount": "relative", "free": "5 GB"},
                {"mount": "/media/z/", "free": "0 MB"},
                {"mount": "/media/a", "free": "1 GB"},
                {"mount": "/media/a/", "free": "2 GB"},
            ]
        }
    )
    assert [(d.mount, d.free_bytes) for d in parsed.disks] == [
        ("/media/a", None),
        ("/media/z", 0),
    ]


def diagnostic_entries(hass, entry):
    return {
        item.unique_id.removeprefix(entry.unique_id + "_"): item
        for item in er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)
        if item.domain == "sensor"
    }


async def test_measurements_registry_refresh_and_disks(hass, entry, receiver):
    info = receiver[0]["about"]["info"]
    info.update(
        mem1="1024 kB",
        mem2="512 kB",
        uptime="1d 02:03",
        hdd=[
            {"mount": "/media/hdd", "free": "2 GB"},
            {"mount": "/media/usb", "free": "0 MB"},
        ],
    )
    await setup(hass, entry)
    coordinator = entry.runtime_data
    entities = diagnostic_entries(hass, entry)
    for key in ("ram_free", "ram_total", "uptime"):
        assert entities[key].disabled_by is er.RegistryEntryDisabler.INTEGRATION
    expected = {"ram_free": 512 * 1024, "ram_total": 1024**2, "uptime": 93780}
    for desc in DESCRIPTIONS:
        if desc.key in expected:
            assert EnigmaSensor(coordinator, desc).native_value == expected[desc.key]
    disk = entities["disk_free_/media/hdd"]
    assert disk.disabled_by is None
    assert "/media/hdd" in hass.states.get(disk.entity_id).name
    assert hass.states.get(disk.entity_id).state == "2.0"
    assert hass.states.get(disk.entity_id).attributes["unit_of_measurement"] == "GiB"
    assert hass.states.get(entities["disk_free_/media/usb"].entity_id).state == "0.0"

    def about_calls():
        return sum(c.args == ("about",) for c in receiver[1].call_args_list)

    assert about_calls() == 1
    due = coordinator._diagnostics_due
    with patch("custom_components.enigma2_connect.coordinator.monotonic", return_value=due - 1):
        await coordinator.async_refresh()
    assert about_calls() == 1
    info["hdd"].reverse()
    info["hdd"][1]["free"] = "1 GB"
    info["hdd"].append({"mount": "/media/new", "free": "3 GB"})
    info["uptime"] = "00:01"  # Receiver reboot: the duration may decrease.
    with patch("custom_components.enigma2_connect.coordinator.monotonic", return_value=due):
        await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert about_calls() == 2
    assert coordinator.data.system.uptime_seconds == 60
    assert hass.states.get(disk.entity_id).state == "1.0"
    assert len([k for k in diagnostic_entries(hass, entry) if k.startswith("disk_free_")]) == 3
    info["hdd"] = []
    coordinator._diagnostics_due = 0
    await coordinator.async_refresh()
    assert hass.states.get(disk.entity_id).state == "unavailable"
    info["hdd"] = [{"mount": "/media/hdd", "free": "4 GB"}]
    coordinator._diagnostics_due = 0
    await coordinator.async_refresh()
    assert hass.states.get(disk.entity_id).state == "4.0"
    assert diagnostic_entries(hass, entry)["disk_free_/media/hdd"].entity_id == disk.entity_id
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert not coordinator._listeners


@pytest.mark.parametrize("bad", [ConnectionError(), {"info": []}, {}])
async def test_optional_diagnostics_failure_and_recovery(hass, entry, receiver, bad):
    info = receiver[0]["about"]["info"]
    info.update(mem2="1 MB", uptime="00:10")
    await setup(hass, entry)
    coordinator = entry.runtime_data
    receiver[0]["about"] = bad
    coordinator._diagnostics_due = 0
    await coordinator.async_refresh()
    assert coordinator.last_update_success
    assert coordinator.data.system == SystemDiagnostics()
    assert "about" in coordinator.optional_errors
    assert coordinator.info["model"] == "Test Receiver"
    receiver[0]["about"] = {"info": info}
    coordinator._diagnostics_due = 0
    await coordinator.async_refresh()
    assert coordinator.data.system.ram_free_bytes == 1024**2
    assert "about" not in coordinator.optional_errors


async def test_diagnostics_authentication_starts_reauth(hass, entry, receiver):
    await setup(hass, entry)
    receiver[0]["about"] = AuthenticationError()
    entry.runtime_data._diagnostics_due = 0
    await entry.runtime_data.async_refresh()
    assert not entry.runtime_data.last_update_success
    await hass.async_block_till_done()
    assert any(
        flow["context"]["source"] == "reauth" for flow in hass.config_entries.flow.async_progress()
    )
