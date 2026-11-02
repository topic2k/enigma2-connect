# SPDX-License-Identifier: Apache-2.0
"""Device identity behavior for old and future Home Assistant DeviceInfo types."""

from dataclasses import dataclass, field
from unittest.mock import patch

import pytest
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC

from custom_components.enigma2_connect import entity as entity_module
from custom_components.enigma2_connect.entity import EnigmaEntity

from .test_integration import setup


@dataclass
class DataclassDeviceInfo:
    identifiers: set[tuple[str, str]]
    name: str
    manufacturer: str | None = None
    model: str | None = None
    sw_version: str | None = None
    configuration_url: str | None = None
    connections: set[tuple[str, str]] = field(default_factory=set)


@pytest.mark.parametrize(
    ("ifaces", "expected_connections"),
    [
        (
            [{"mac": "AA:BB:CC:DD:EE:FF"}],
            {(CONNECTION_NETWORK_MAC, "aa:bb:cc:dd:ee:ff")},
        ),
        ([], set()),
        ([{"mac": "00:00:00:00:00:00"}], set()),
    ],
)
async def test_device_info_dataclass_receives_connections(
    hass, entry, receiver, ifaces, expected_connections
):
    if ifaces:
        receiver[0]["about"]["info"]["ifaces"] = ifaces
    else:
        receiver[0]["about"]["info"].pop("ifaces")
    await setup(hass, entry)

    with patch.object(entity_module, "DeviceInfo", DataclassDeviceInfo):
        device_info = EnigmaEntity(entry.runtime_data, "test")._attr_device_info

    assert isinstance(device_info, DataclassDeviceInfo)
    assert device_info.identifiers == {("enigma2_connect", entry.unique_id)}
    assert device_info.name == entry.title
    assert device_info.manufacturer == "Example"
    assert device_info.model == "Test Receiver"
    assert device_info.sw_version == "1.5.2"
    assert device_info.configuration_url == str(entry.runtime_data.client.base_url)
    assert device_info.connections == expected_connections
