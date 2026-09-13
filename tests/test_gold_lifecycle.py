# SPDX-License-Identifier: Apache-2.0
"""Privacy, repair recovery and one-receiver-per-entry lifecycle in real HA."""

from types import SimpleNamespace
from unittest.mock import patch

import pytest
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.enigma2_connect.api import ConnectionError
from custom_components.enigma2_connect.const import DOMAIN
from custom_components.enigma2_connect.diagnostics import async_get_config_entry_diagnostics
from custom_components.enigma2_connect.recording_images import async_check_snapshot_support
from custom_components.enigma2_connect.sensor import DESCRIPTIONS, EnigmaSensor

from .conftest import DATA
from .test_integration import setup


async def test_diagnostics_without_runtime(hass, entry):
    assert await async_get_config_entry_diagnostics(hass, entry) == {"loaded": False}


async def test_diagnostics_partial_offline_and_no_data(hass, entry, receiver):
    await setup(hass, entry)
    coordinator = entry.runtime_data
    receiver[0]["timerlist"] = ConnectionError()
    receiver[0]["movielist"] = ConnectionError()
    coordinator.invalidate_lists()
    await coordinator.async_refresh()
    receiver[0]["statusinfo"] = ConnectionError()
    await coordinator.async_refresh()
    report = await async_get_config_entry_diagnostics(hass, entry)
    assert report["last_update_success"] is False
    assert report["counts"]["timers"] is None
    assert report["counts"]["recordings"] is None
    assert report["optional_endpoint_errors"] == ["movielist", "timerlist"]
    assert not any(
        value in str(report) for value in ("secret", "root", "receiver.local", "Channel", "AA:BB")
    )
    coordinator.data = None
    coordinator.update_interval = None
    report = await async_get_config_entry_diagnostics(hass, entry)
    assert report["poll_seconds"] is None
    assert set(report["counts"].values()) == {None}


@pytest.mark.parametrize("resolution", ["installed", "disabled", "removed"])
async def test_snapshot_repair_lifecycle(hass, entry, receiver, resolution):
    registry = ir.async_get(hass)
    issue_id = f"{entry.entry_id}_snapshot_binary"
    with patch("custom_components.enigma2_connect.recording_images.which", return_value=None):
        await setup(hass, entry)
        issue = registry.async_get_issue(DOMAIN, issue_id)
        assert issue.translation_key == "snapshot_binary"
        assert issue.translation_placeholders == {"receiver": "Test Receiver"}
        assert hass.states.get("media_player.test_receiver").state == "playing"
        if resolution == "removed":
            await hass.config_entries.async_remove(entry.entry_id)
        elif resolution == "disabled":
            hass.config_entries.async_update_entry(entry, options={"recording_image_sources": []})
            await async_check_snapshot_support(hass, entry)
        else:
            hass.data["ffmpeg"] = SimpleNamespace(binary="/custom/ffmpeg")
            with patch(
                "custom_components.enigma2_connect.recording_images.which",
                return_value="/custom/ffmpeg",
            ) as which:
                await async_check_snapshot_support(hass, entry)
                which.assert_called_once_with("/custom/ffmpeg")
    assert registry.async_get_issue(DOMAIN, issue_id) is None


async def test_add_offline_remove_preserves_other_receiver(hass, entry, receiver):
    await setup(hass, entry)
    devices, entities = dr.async_get(hass), er.async_get(hass)
    original = dr.async_entries_for_config_entry(devices, entry.entry_id)[0]
    receiver[0]["about"]["info"]["ifaces"][0]["mac"] = "11:22:33:44:55:66"
    second = MockConfigEntry(
        domain=DOMAIN,
        title="Second Receiver",
        unique_id="112233445566",
        data={**DATA, "host": "other.local"},
    )
    second.add_to_hass(hass)
    assert await hass.config_entries.async_setup(second.entry_id)
    await hass.async_block_till_done()
    added = dr.async_entries_for_config_entry(devices, second.entry_id)[0]
    assert added.id != original.id
    assert hass.states.get("media_player.second_receiver").state == "playing"
    receiver[0]["statusinfo"] = ConnectionError()
    await second.runtime_data.async_refresh()
    assert devices.async_get(added.id) is not None
    assert hass.states.get("media_player.second_receiver").state == "unavailable"
    await hass.config_entries.async_remove(second.entry_id)
    await hass.async_block_till_done()
    assert not dr.async_entries_for_config_entry(devices, second.entry_id)
    assert not er.async_entries_for_config_entry(entities, second.entry_id)
    assert devices.async_get(original.id) is not None
    assert hass.states.get("media_player.test_receiver").state == "playing"


async def test_diagnostics_are_optional_and_connectivity_uses_device_class(hass, entry, receiver):
    await setup(hass, entry)
    entities = er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)
    for item in entities:
        if item.unique_id.rsplit("_", 1)[-1] in ("signal", "snr", "ber"):
            assert item.disabled_by is er.RegistryEntryDisabler.INTEGRATION
            assert item.entity_category.value == "diagnostic"
    assert (
        hass.states.get("binary_sensor.test_receiver_connection").attributes["device_class"]
        == "connectivity"
    )
    for description in DESCRIPTIONS:
        if description.key in ("signal", "snr", "ber"):
            sensor = EnigmaSensor(entry.runtime_data, description)
            assert sensor.native_value == {"signal": 80, "snr": 12.5, "ber": 0}[description.key]
