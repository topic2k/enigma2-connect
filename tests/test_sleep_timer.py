# SPDX-License-Identifier: Apache-2.0
"""Sleep timer tests with real HA and simulated receiver responses."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import aiohttp
import pytest
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import device_registry as dr
from yarl import URL

from custom_components.enigma2_connect.api import (
    AuthenticationError,
    CommandUnconfirmed,
    ConnectionError,
    UnsupportedError,
    power_command_middleware,
)
from custom_components.enigma2_connect.binary_sensor import EnigmaBinarySensor
from custom_components.enigma2_connect.const import DOMAIN
from custom_components.enigma2_connect.sleep_timer import (
    SleepTimerError,
    parse_sleep_timer,
    set_sleep_timer,
)

from .test_api import client_for
from .test_integration import setup


@pytest.mark.parametrize("data", [None, {}, {"result": False, "enabled": True}, {"enabled": "bad"}])
def test_invalid_status(data):
    assert parse_sleep_timer(data) is None


@pytest.mark.parametrize(
    "raw,expected",
    [
        (30, 30),
        ("30", 30),
        (None, None),
        ("9" * 5000, None),
        ("", None),
        (-1, None),
        (True, None),
        (1.2, None),
        ("²", None),
    ],
)
def test_optional_minutes(raw, expected):
    result = parse_sleep_timer({"enabled": "true", "minutes": raw, "action": "unexpected"})
    assert result.enabled and result.minutes == expected and result.action is None


async def test_poll_and_status(hass, entry, receiver):
    await setup(hass, entry)
    entity = EnigmaBinarySensor(entry.runtime_data, "sleep_timer")
    assert entity.available and entity.is_on is False
    assert hass.states.get("binary_sensor.test_receiver_sleep_timer_active").state == "off"
    receiver[0]["sleeptimer"] = {"enabled": True, "minutes": "30", "action": "shutdown"}
    await entry.runtime_data.async_refresh()
    assert entity.is_on is True
    assert entity.extra_state_attributes == {"reported_minutes": 30, "action": "shutdown"}
    for failure in (UnsupportedError(), {}):
        receiver[0]["sleeptimer"] = failure
        await entry.runtime_data.async_refresh()
        assert entry.runtime_data.last_update_success
        assert not entity.available and entity.is_on is None
        assert entity.extra_state_attributes is None
        assert "sleeptimer" in entry.runtime_data.optional_errors
    receiver[0]["sleeptimer"] = {"enabled": False}
    receiver[0]["statusinfo"]["inStandby"] = True
    await entry.runtime_data.async_refresh()
    assert entity.available and entity.is_on is False
    assert "sleeptimer" not in entry.runtime_data.optional_errors
    assert EnigmaBinarySensor(entry.runtime_data, "standby").extra_state_attributes is None


@pytest.mark.parametrize("minutes", [30, None])
async def test_actions(hass, entry, receiver, minutes):
    receiver[0]["sleeptimer"] = {"enabled": True, "minutes": 60, "action": "shutdown"}
    await setup(hass, entry)
    device = dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id)[0]
    original = receiver[1].side_effect
    writes = []

    async def get(endpoint, **params):
        if params.get("cmd") == "set":
            assert entry.runtime_data.client.command_lock.locked()
            writes.append(params)
            receiver[0]["sleeptimer"] = {
                "enabled": minutes is not None,
                "minutes": minutes,
                "action": params["action"],
            }
            return {}  # Some images omit result; only a fresh status confirms success.
        return await original(endpoint, **params)

    receiver[1].side_effect = get
    for _ in range(2):
        await hass.services.async_call(
            DOMAIN,
            "sleep_timer_set" if minutes else "sleep_timer_cancel",
            {"device_id": device.id, **({"minutes": minutes} if minutes else {})},
            blocking=True,
        )
        assert entry.runtime_data.data.sleep_timer.enabled is (minutes is not None)
    assert len(writes) == (2 if minutes else 1)
    assert writes[0] == {
        "cmd": "set",
        "enabled": "True" if minutes else "False",
        "time": minutes or 0,
        "action": "standby" if minutes else "shutdown",
    }


@pytest.mark.parametrize("minutes", [0, 1000, True, 1.5, "30"])
async def test_invalid_duration(minutes):
    client = SimpleNamespace(get=AsyncMock())
    with pytest.raises(SleepTimerError, match="sleep_timer_invalid"):
        await set_sleep_timer(client, minutes)
    client.get.assert_not_awaited()


@pytest.mark.parametrize(
    "mode",
    [
        "standby",
        "bad_state",
        "missing",
        "unknown_action",
        "write_lost",
        "read_lost",
        "auth",
        "bad_reply",
        "missing_after",
        "wrong_enabled",
        "wrong_action",
        "rounded",
        "cancelled",
    ],
)
async def test_boundaries(mode):
    writes = []

    async def get(endpoint, **params):
        if endpoint == "statusinfo":
            return {} if mode == "bad_state" else {"inStandby": mode == "standby"}
        if params:
            writes.append(params)
            if mode == "write_lost":
                raise CommandUnconfirmed()
            if mode == "cancelled":
                raise asyncio.CancelledError()
            return {"result": False} if mode == "bad_reply" else {}
        if not writes:
            return (
                {}
                if mode == "missing"
                else {
                    "enabled": True,
                    "minutes": 60,
                    "action": None if mode == "unknown_action" else "standby",
                }
            )
        if mode in ("read_lost", "auth"):
            raise AuthenticationError() if mode == "auth" else UnsupportedError()
        if mode == "missing_after":
            return {}
        return {
            "enabled": mode != "wrong_enabled",
            "minutes": 45 if mode == "rounded" else 30,
            "action": "shutdown" if mode == "wrong_action" else "standby",
        }

    client = SimpleNamespace(command_lock=asyncio.Lock(), get=get)
    expected = (
        AuthenticationError
        if mode == "auth"
        else asyncio.CancelledError
        if mode == "cancelled"
        else SleepTimerError
    )
    with pytest.raises(expected):
        await set_sleep_timer(client, None if mode == "unknown_action" else 30)
    assert len(writes) == (
        0 if mode in ("standby", "bad_state", "missing", "unknown_action") else 1
    )
    assert not client.command_lock.locked()


@pytest.mark.parametrize(
    "error,key",
    [(CommandUnconfirmed(), "sleep_timer_unconfirmed"), (AuthenticationError(), "invalid_auth")],
)
async def test_action_error_refresh(hass, entry, receiver, error, key):
    await setup(hass, entry)
    original = receiver[1].side_effect

    async def get(endpoint, **params):
        if params:
            receiver[0]["sleeptimer"]["enabled"] = True
            raise error
        return await original(endpoint, **params)

    receiver[1].side_effect = get
    with pytest.raises(HomeAssistantError) as caught:
        await entry.runtime_data.async_set_sleep_timer(30)
    assert caught.value.translation_key == key
    assert entry.runtime_data.data.sleep_timer.enabled


@pytest.mark.parametrize("service", ["sleep_timer_set", "sleep_timer_cancel"])
async def test_wrong_device(hass, entry, receiver, service):
    await setup(hass, entry)
    receiver[1].reset_mock()
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            service,
            {"device_id": "missing", **({"minutes": 30} if service.endswith("set") else {})},
            blocking=True,
        )
    receiver[1].assert_not_awaited()


@pytest.mark.parametrize("write", [False, True])
async def test_transport_does_not_replay_writes(write):
    handler = AsyncMock(side_effect=aiohttp.ServerDisconnectedError())
    request = SimpleNamespace(
        url=URL("http://receiver/api/sleeptimer" + ("?cmd=set" if write else ""))
    )
    with pytest.raises(CommandUnconfirmed if write else aiohttp.ServerDisconnectedError):
        await power_command_middleware(request, handler)
    handler.assert_awaited_once()
    client, response = client_for()
    response.json.side_effect = TimeoutError()
    with pytest.raises(CommandUnconfirmed if write else ConnectionError) as caught:
        await client.get("sleeptimer", **({"cmd": "set"} if write else {}))
    assert isinstance(caught.value, CommandUnconfirmed) is write
    assert client.session.get.call_count == 1


async def test_actions_have_valid_ha_selectors(hass, entry, receiver):
    from homeassistant.helpers.selector import NumberSelector
    from homeassistant.helpers.service import async_get_all_descriptions

    await setup(hass, entry)
    descriptions = (await async_get_all_descriptions(hass))[DOMAIN]
    fields = descriptions["sleep_timer_set"]["fields"]
    assert fields["device_id"]["required"]
    selector = NumberSelector(fields["minutes"]["selector"]["number"])
    assert selector(30) == 30
    assert descriptions["sleep_timer_cancel"]["fields"]["device_id"]["required"]


async def test_commands_serialize():
    entered = asyncio.Event()
    release = asyncio.Event()
    written = False

    async def get(endpoint, **params):
        nonlocal written
        if endpoint == "statusinfo":
            entered.set()
            await release.wait()
            return {"inStandby": False}
        if params:
            written = True
        return {"enabled": written, "minutes": 30, "action": "standby"}

    client = SimpleNamespace(command_lock=asyncio.Lock(), get=AsyncMock(side_effect=get))
    first = asyncio.create_task(set_sleep_timer(client, 30))
    await entered.wait()
    second = asyncio.create_task(set_sleep_timer(client, 30))
    await asyncio.sleep(0)
    assert client.get.await_count == 1
    release.set()
    await asyncio.gather(first, second)
    assert client.get.await_count == 8
