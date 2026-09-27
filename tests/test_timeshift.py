# SPDX-License-Identifier: Apache-2.0
"""Timeshift actions and status in real HA with simulated receiver data."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import device_registry as dr

from custom_components.enigma2_connect.api import (
    AuthenticationError,
    CommandUnconfirmed,
    UnsupportedError,
)
from custom_components.enigma2_connect.binary_sensor import EnigmaBinarySensor
from custom_components.enigma2_connect.const import DOMAIN
from custom_components.enigma2_connect.timeshift import (
    TimeshiftError,
    parse_timeshift,
    set_timeshift,
)

from .test_integration import setup


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        (None, None),
        ({}, None),
        ({"state": False, "timeshiftEnabled": True}, None),
        ({"state": True}, None),
        ({"state": True, "timeshiftEnabled": "bad"}, None),
        ({"state": True, "timeshiftEnabled": False}, False),
        ({"state": "true", "timeshiftEnabled": "true"}, True),
    ],
)
def test_parse(data, expected):
    assert parse_timeshift(data) is expected


async def test_poll_sensor_and_recovery(hass, entry, receiver):
    await setup(hass, entry)
    entity = EnigmaBinarySensor(entry.runtime_data, "timeshift")
    assert entity.available and entity.is_on is False
    assert hass.states.get("binary_sensor.test_receiver_timeshift_active").state == "off"
    receiver[0]["tsstate"]["timeshiftEnabled"] = True
    await entry.runtime_data.async_refresh()
    assert entity.is_on is True
    assert hass.states.get("media_player.test_receiver").state == "playing"
    for failure in (UnsupportedError(), {}, {"state": False}):
        receiver[0]["tsstate"] = failure
        await entry.runtime_data.async_refresh()
        assert entry.runtime_data.last_update_success
        assert not entity.available and entity.is_on is None
        assert "tsstate" in entry.runtime_data.optional_errors
    receiver[0]["tsstate"] = {"state": True, "timeshiftEnabled": False}
    await entry.runtime_data.async_refresh()
    assert entity.available and entity.is_on is False
    assert "tsstate" not in entry.runtime_data.optional_errors
    receiver[0]["statusinfo"]["inStandby"] = True
    receiver[1].reset_mock()
    await entry.runtime_data.async_refresh()
    assert not entity.available
    assert not any(c.args[0] == "tsstate" for c in receiver[1].call_args_list)


@pytest.mark.parametrize("enabled", [True, False])
async def test_actions_confirm_refresh_and_noop(hass, entry, receiver, enabled):
    receiver[0]["tsstate"]["timeshiftEnabled"] = not enabled
    await setup(hass, entry)
    device = dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id)[0]
    endpoint = "tsstart" if enabled else "tsstop"
    action = "timeshift_start" if enabled else "timeshift_stop"
    original = receiver[1].side_effect

    async def get(name, **params):
        if name == endpoint:
            assert entry.runtime_data.client.command_lock.locked()
            assert not params
            receiver[0]["tsstate"]["timeshiftEnabled"] = enabled
            return {"state": True, "timeshiftEnabled": enabled}
        return await original(name, **params)

    receiver[1].side_effect = get
    for _ in range(2):
        await hass.services.async_call(DOMAIN, action, {"device_id": device.id}, blocking=True)
        assert entry.runtime_data.data.timeshift is enabled
    assert sum(c.args[0] == endpoint for c in receiver[1].call_args_list) == 1


@pytest.mark.parametrize("action", ["timeshift_start", "timeshift_stop"])
async def test_invalid_target(hass, entry, receiver, action):
    await setup(hass, entry)
    receiver[1].reset_mock()
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(DOMAIN, action, {"device_id": "missing"}, blocking=True)
    receiver[1].assert_not_awaited()


@pytest.mark.parametrize(
    ("reply", "key"),
    [
        ({"state": False}, "request_failed"),
        ({}, "timeshift_unconfirmed"),
        ({"state": True}, "timeshift_unconfirmed"),
        (CommandUnconfirmed(), "timeshift_unconfirmed"),
        (AuthenticationError(), "invalid_auth"),
    ],
)
async def test_action_errors(hass, entry, receiver, reply, key):
    await setup(hass, entry)
    receiver[0]["tsstart"] = reply
    with pytest.raises(HomeAssistantError) as error:
        await entry.runtime_data.async_set_timeshift(True)
    assert error.value.translation_key == key
    assert sum(c.args[0] == "tsstart" for c in receiver[1].call_args_list) == 1
    assert entry.runtime_data.data.timeshift is False


@pytest.mark.parametrize(
    "change",
    ["standby", "invalid_state", "invalid_timeshift", "read_failure", "read_auth", "cancel"],
)
async def test_boundaries(change):
    written = False

    async def get(endpoint):
        nonlocal written
        if endpoint == "statusinfo":
            return {} if change == "invalid_state" else {"inStandby": change == "standby"}
        if endpoint == "tsstart":
            written = True
            if change == "cancel":
                raise asyncio.CancelledError
            return {"state": True}
        if written:
            raise AuthenticationError() if change == "read_auth" else UnsupportedError()
        return {} if change == "invalid_timeshift" else {"state": True, "timeshiftEnabled": False}

    client = SimpleNamespace(command_lock=asyncio.Lock(), get=AsyncMock(side_effect=get))
    expected = (
        AuthenticationError
        if change == "read_auth"
        else asyncio.CancelledError
        if change == "cancel"
        else TimeshiftError
    )
    with pytest.raises(expected):
        await set_timeshift(client, True)
    assert written == (change in ("read_failure", "read_auth", "cancel"))
    assert not client.command_lock.locked()


async def test_poll_auth(hass, entry, receiver):
    await setup(hass, entry)
    receiver[0]["tsstate"] = AuthenticationError()
    await entry.runtime_data.async_refresh()
    assert not entry.runtime_data.last_update_success


async def test_lost_reply_refreshes_actual_changed_state(hass, entry, receiver):
    await setup(hass, entry)
    original = receiver[1].side_effect

    async def get(endpoint, **params):
        if endpoint == "tsstart":
            receiver[0]["tsstate"]["timeshiftEnabled"] = True
            raise CommandUnconfirmed()
        return await original(endpoint, **params)

    receiver[1].side_effect = get
    with pytest.raises(HomeAssistantError) as error:
        await entry.runtime_data.async_set_timeshift(True)
    assert error.value.translation_key == "timeshift_unconfirmed"
    assert entry.runtime_data.data.timeshift is True
    assert sum(c.args[0] == "tsstart" for c in receiver[1].call_args_list) == 1
    assert not entry.runtime_data.client.command_lock.locked()
