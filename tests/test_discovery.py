# SPDX-License-Identifier: Apache-2.0
"""Discovery must never pair silently or move a receiver to different hardware."""

from copy import deepcopy
from ipaddress import ip_address
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.enigma2_connect.api import AuthenticationError, ConnectionError
from custom_components.enigma2_connect.const import DOMAIN

from .conftest import DATA, RESPONSES


@pytest.fixture(autouse=True)
def mock_lifecycle():
    with (
        patch("custom_components.enigma2_connect.async_setup_entry", return_value=True),
        patch("custom_components.enigma2_connect.async_unload_entry", return_value=True),
    ):
        yield


@pytest.mark.parametrize("secure", [False, True])
async def test_advertisement_needs_validated_confirmation(hass, receiver, secure):
    protocol = "_https._tcp.local." if secure else "_http._tcp.local."
    info = ZeroconfServiceInfo(
        ip_address=ip_address("192.0.2.42"),
        ip_addresses=[ip_address("192.0.2.42")],
        port=8443 if secure else 8080,
        hostname="receiver.local.",
        type=protocol,
        name=f"OpenWebif.{protocol}",
        properties={},
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "zeroconf"}, data=info
    )
    assert result["type"] == "form"
    assert result["step_id"] == "user"
    receiver[1].assert_not_called()
    assert not hass.config_entries.async_entries(DOMAIN)
    defaults = {
        key.schema: key.default()
        for key in result["data_schema"].schema
        if key.default is not None and key.schema in ("host", "port", "use_https")
    }
    assert defaults == {"host": "192.0.2.42", "port": info.port, "use_https": secure}
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {**DATA, **defaults})
    assert result["type"] == "create_entry"
    assert result["result"].unique_id == "aabbccddeeff"
    assert result["data"]["use_https"] is secure
    # A repeated advertisement at the paired address must not create a second flow.
    duplicate = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "zeroconf"}, data=info
    )
    assert duplicate["reason"] == "already_configured"


async def dhcp(hass, mac="aabbccddeeff", address="192.0.2.43"):
    return await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "dhcp"},
        data=DhcpServiceInfo(ip=address, hostname="receiver", macaddress=mac),
    )


async def test_dhcp_preserves_credentials_tls_options_and_ids(hass, entry, receiver):
    before = {**DATA, "port": 8443, "use_https": True, "verify_ssl": True}
    hass.config_entries.async_update_entry(entry, data=before, options={"scan_interval": 30})
    with patch.object(hass.config_entries, "async_reload", new_callable=AsyncMock) as reload:
        result = await dhcp(hass)
        assert result["reason"] == "already_configured"
        assert dict(entry.data) == {**before, "host": "192.0.2.43"}
        assert dict(entry.options) == {"scan_interval": 30}
        assert entry.unique_id == "aabbccddeeff"
        reload.assert_awaited_once_with(entry.entry_id)
        receiver[1].reset_mock()
        assert (await dhcp(hass))["reason"] == "already_configured"
        receiver[1].assert_not_called()


@pytest.mark.parametrize(
    "reply, reason",
    [
        (AuthenticationError(), "discovery_failed"),
        (ConnectionError(), "discovery_failed"),
        ({"info": None}, "discovery_failed"),
        ({"info": {}}, "wrong_device"),
        ({"info": {"ifaces": [{"mac": "11:22:33:44:55:66"}]}}, "wrong_device"),
    ],
)
async def test_unverified_address_cannot_replace_saved_connection(
    hass, entry, receiver, reply, reason
):
    receiver[0]["about"] = reply
    with patch.object(hass.config_entries, "async_reload", new_callable=AsyncMock) as reload:
        result = await dhcp(hass)
        assert result["reason"] == reason
        assert dict(entry.data) == DATA
        reload.assert_not_awaited()
    receiver[0]["about"] = deepcopy(RESPONSES["about"])


async def test_dhcp_ignores_unpaired_and_host_identity_receivers(hass, receiver):
    MockConfigEntry(domain=DOMAIN, unique_id="host:receiver.local", data=DATA).add_to_hass(hass)
    assert (await dhcp(hass))["reason"] == "not_registered"
    receiver[1].assert_not_called()


async def test_dhcp_does_not_take_over_another_entry_address(hass, entry, receiver):
    other = MockConfigEntry(
        domain=DOMAIN, unique_id="host:192.0.2.43", data={**DATA, "host": "192.0.2.43"}
    )
    other.add_to_hass(hass)
    assert (await dhcp(hass))["reason"] == "already_configured"
    assert dict(entry.data) == DATA
    receiver[1].assert_not_called()
