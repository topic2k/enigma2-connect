# SPDX-License-Identifier: Apache-2.0
"""Exercise setup recovery and identity protection through the HA flow manager."""

from copy import deepcopy
from unittest.mock import AsyncMock, patch

import pytest
import voluptuous as vol
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.enigma2_connect.api import AuthenticationError, ConnectionError
from custom_components.enigma2_connect.config_flow import host
from custom_components.enigma2_connect.const import DOMAIN
from custom_components.enigma2_connect.recording_images import CONF_IMAGE_SOURCES, CONF_TMDB_KEY

from .conftest import DATA, RESPONSES


@pytest.fixture(autouse=True)
def mock_platform_lifecycle():
    """Flows create entries; platform loading is exercised by integration tests."""
    with (
        patch("custom_components.enigma2_connect.async_setup_entry", return_value=True),
        patch("custom_components.enigma2_connect.async_unload_entry", return_value=True),
    ):
        yield


@pytest.mark.parametrize("source", ["user", "reauth", "reconfigure"])
@pytest.mark.parametrize(
    ("failure", "error"),
    [
        (AuthenticationError(), "invalid_auth"),
        (ConnectionError(), "cannot_connect"),
        ({"info": {}}, "invalid_response"),
        ({"info": []}, "invalid_response"),
    ],
)
async def test_connection_error_recovers_in_same_flow(hass, receiver, source, failure, error):
    """A failed submission must leave the original flow usable, including reauth."""
    entry = None
    context = {"source": source}
    if source != "user":
        entry = MockConfigEntry(domain=DOMAIN, unique_id="aabbccddeeff", data=DATA)
        entry.add_to_hass(hass)
        context["entry_id"] = entry.entry_id
    receiver[0]["about"] = failure
    with (
        patch("custom_components.enigma2_connect.async_setup_entry", return_value=True),
        patch.object(hass.config_entries, "async_reload", new_callable=AsyncMock),
    ):
        form = await hass.config_entries.flow.async_init(DOMAIN, context=context)
        result = await hass.config_entries.flow.async_configure(form["flow_id"], DATA)
        assert result["type"] == "form"
        assert result["errors"] == {"base": error}
        if entry:
            assert dict(entry.data) == DATA
        else:
            assert not hass.config_entries.async_entries(DOMAIN)
        receiver[0]["about"] = deepcopy(RESPONSES["about"])
        result = await hass.config_entries.flow.async_configure(
            form["flow_id"], {**DATA, "password": "corrected"}
        )
        if source == "user":
            assert result["type"] == "create_entry"
            entry = result["result"]
        else:
            assert result["type"] == "abort"
            assert result["reason"] == f"{source}_successful"
        assert entry.data["password"] == "corrected"
        assert len(hass.config_entries.async_entries(DOMAIN)) == 1


@pytest.mark.parametrize("source", ["user", "reauth", "reconfigure"])
async def test_invalid_host_recovers_in_same_flow(hass, receiver, source):
    context = {"source": source}
    if source != "user":
        entry = MockConfigEntry(domain=DOMAIN, unique_id="aabbccddeeff", data=DATA)
        entry.add_to_hass(hass)
        context["entry_id"] = entry.entry_id
    with (
        patch("custom_components.enigma2_connect.async_setup_entry", return_value=True),
        patch.object(hass.config_entries, "async_reload", new_callable=AsyncMock),
    ):
        form = await hass.config_entries.flow.async_init(DOMAIN, context=context)
        result = await hass.config_entries.flow.async_configure(
            form["flow_id"], {**DATA, "host": "https://receiver.local/path"}
        )
        assert result["errors"] == {"host": "invalid_host"}
        receiver[1].assert_not_called()
        result = await hass.config_entries.flow.async_configure(form["flow_id"], DATA)
        assert result["type"] == ("create_entry" if source == "user" else "abort")
        if source != "user":
            assert result["reason"] == f"{source}_successful"


@pytest.mark.parametrize("value", [None, 42, "", "a" * 254, "bad..host", "-bad.local"])
def test_invalid_host_validation(value):
    with pytest.raises(vol.Invalid):
        host(value)


@pytest.mark.parametrize(
    ("value", "expected"),
    [(" RECEIVER.Local. ", "receiver.local"), ("[2001:db8::1]", "2001:db8::1")],
)
def test_host_normalization(value, expected):
    assert host(value) == expected


@pytest.mark.parametrize("source", ["reauth", "reconfigure"])
async def test_changed_hardware_is_rejected(hass, entry, receiver, source):
    receiver[0]["about"]["info"]["ifaces"] = [{"mac": "11:22:33:44:55:66"}]
    with patch.object(hass.config_entries, "async_reload", new_callable=AsyncMock) as reload:
        form = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": source, "entry_id": entry.entry_id}
        )
        result = await hass.config_entries.flow.async_configure(form["flow_id"], DATA)
        assert result["reason"] == "wrong_device"
        assert dict(entry.data) == DATA
        reload.assert_not_awaited()


@pytest.mark.parametrize("source", ["user", "reauth", "reconfigure"])
@pytest.mark.parametrize("same_host", [False, True])
async def test_duplicate_receiver_is_rejected(hass, entry, receiver, source, same_host):
    """Protect both host and hardware identity when another entry is present."""
    context = {"source": source}
    if source != "user":
        other = MockConfigEntry(
            domain=DOMAIN, unique_id="112233445566", data={**DATA, "host": "other.local"}
        )
        other.add_to_hass(hass)
        context["entry_id"] = other.entry_id
    form = await hass.config_entries.flow.async_init(DOMAIN, context=context)
    result = await hass.config_entries.flow.async_configure(
        form["flow_id"], {**DATA, "host": DATA["host"] if same_host else "new.local"}
    )
    assert result["reason"] == "already_configured"
    assert dict(entry.data) == DATA
    if source != "user":
        assert other.data["host"] == "other.local"


async def test_host_identity_can_be_reconfigured_without_mac(hass, receiver):
    receiver[0]["about"]["info"].pop("ifaces")
    with (
        patch("custom_components.enigma2_connect.async_setup_entry", return_value=True),
        patch.object(hass.config_entries, "async_reload", new_callable=AsyncMock),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}, data=DATA
        )
        entry = result["result"]
        assert entry.unique_id == "host:receiver.local"
        form = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "reconfigure", "entry_id": entry.entry_id}
        )
        result = await hass.config_entries.flow.async_configure(
            form["flow_id"], {**DATA, "host": "new.local"}
        )
        assert result["reason"] == "reconfigure_successful"
        assert entry.data["host"] == "new.local"
        assert entry.unique_id == "host:receiver.local"


async def test_distinct_receiver_can_be_added(hass, entry, receiver):
    """An existing receiver must not prevent adding another independent device."""
    receiver[0]["about"]["info"]["ifaces"] = [{"mac": "11:22:33:44:55:66"}]
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}, data={**DATA, "host": "other.local"}
    )
    assert result["type"] == "create_entry"
    assert result["result"].unique_id == "112233445566"
    assert len(hass.config_entries.async_entries(DOMAIN)) == 2
    assert dict(entry.data) == DATA


@pytest.mark.parametrize(
    ("bad", "error", "corrected"),
    [
        ({"receiver_timezone": "Invalid/Zone"}, "invalid_timezone", {"receiver_timezone": "UTC"}),
        (
            {CONF_IMAGE_SOURCES: ["tmdb"], CONF_TMDB_KEY: ""},
            "image_api_key_required",
            {CONF_TMDB_KEY: "test-key"},
        ),
    ],
)
async def test_options_error_recovers_without_losing_values(hass, entry, bad, error, corrected):
    with patch.object(hass.config_entries, "async_reload", new_callable=AsyncMock):
        menu = await hass.config_entries.options.async_init(entry.entry_id)
        form = await hass.config_entries.options.async_configure(
            menu["flow_id"], {"next_step_id": "settings"}
        )
        submitted = {**form["data_schema"]({}), "scan_interval": 43, **bad}
        result = await hass.config_entries.options.async_configure(form["flow_id"], submitted)
        assert result["type"] == "form"
        assert error in result["errors"].values()
        assert not entry.options
        assert result["data_schema"]({})["scan_interval"] == 43
        result = await hass.config_entries.options.async_configure(
            form["flow_id"], {**submitted, **corrected}
        )
        assert result["type"] == "create_entry"
        assert entry.options["scan_interval"] == 43
        for key, value in corrected.items():
            assert entry.options[key] == value
