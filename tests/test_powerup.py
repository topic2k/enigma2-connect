# SPDX-License-Identifier: Apache-2.0
"""Quiet power-up against simulated images and the real HA action registry."""

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
    OpenWebifClient,
    PowerCommandUnconfirmed,
    ProtocolError,
    UnsupportedError,
    power_command_middleware,
)
from custom_components.enigma2_connect.const import DOMAIN
from custom_components.enigma2_connect.powerup import QuietPowerupError, powerup_without_tv

from .test_api import client_for
from .test_integration import setup


@pytest.mark.parametrize(
    "endpoint", ["supports_powerup_without_waking_tv", "set_powerup_without_waking_tv"]
)
@pytest.mark.parametrize("value", [True, False, "true", 1, [], {}])
async def test_boolean_transport(endpoint, value):
    client, _ = client_for(data=value)
    if value is True:
        assert await client.get(endpoint) == {"result": True}
    elif value == {}:
        assert await client.get(endpoint) == {}
    else:
        with pytest.raises((ProtocolError, CommandUnconfirmed)):
            await client.get(endpoint)


async def test_boolean_does_not_relax_other_endpoints():
    client, _ = client_for(data=True)
    with pytest.raises(ProtocolError):
        await client.get("statusinfo")


@pytest.mark.parametrize(
    "endpoint,error",
    [
        ("set_powerup_without_waking_tv", CommandUnconfirmed),
        ("powerstate?newstate=4", PowerCommandUnconfirmed),
    ],
)
async def test_no_automatic_replay(endpoint, error):
    handler = AsyncMock(side_effect=aiohttp.ServerDisconnectedError())
    with pytest.raises(error):
        await power_command_middleware(
            SimpleNamespace(url=URL("http://box/api/" + endpoint)), handler
        )
    assert handler.await_count == 1


@pytest.mark.parametrize(
    "mode",
    [
        "success",
        "awake",
        "unknown",
        "unsupported",
        "missing_support",
        "support_error",
        "arm_false",
        "arm_missing",
        "arm_lost",
        "wake_lost",
        "still_standby",
        "after_unknown",
        "after_lost",
        "auth",
        "arm_auth",
        "cancelled",
    ],
)
async def test_workflow(mode):
    calls = []

    async def get(endpoint, **params):
        assert client.command_lock.locked()
        calls.append((endpoint, params))
        if endpoint == "supports_powerup_without_waking_tv":
            if mode == "support_error":
                raise UnsupportedError()
            if mode == "auth":
                raise AuthenticationError()
            return {} if mode == "missing_support" else {"result": mode != "unsupported"}
        if endpoint == "set_powerup_without_waking_tv":
            if mode == "arm_auth":
                raise AuthenticationError()
            if mode == "arm_lost":
                raise ConnectionError()
            if mode == "cancelled":
                raise asyncio.CancelledError()
            return {} if mode == "arm_missing" else {"result": mode != "arm_false"}
        if params:
            assert params == {"newstate": 4}
            if mode == "wake_lost":
                raise PowerCommandUnconfirmed()
            return {"instandby": False}
        if len(calls) == 1:
            return {} if mode == "unknown" else {"instandby": mode != "awake"}
        if mode == "after_lost":
            raise ConnectionError()
        return {} if mode == "after_unknown" else {"instandby": mode == "still_standby"}

    client = SimpleNamespace(command_lock=asyncio.Lock(), get=get)
    if mode in ("success", "awake"):
        await powerup_without_tv(client)
    else:
        error = (
            AuthenticationError
            if mode in ("auth", "arm_auth")
            else (asyncio.CancelledError if mode == "cancelled" else QuietPowerupError)
        )
        with pytest.raises(error):
            await powerup_without_tv(client)
    assert not client.command_lock.locked()
    assert sum(endpoint == "set_powerup_without_waking_tv" for endpoint, _ in calls) <= 1
    wakes = sum(bool(params) for _, params in calls)
    assert wakes == (
        1 if mode in ("success", "wake_lost", "still_standby", "after_unknown", "after_lost") else 0
    )
    if mode == "awake":
        assert len(calls) == 1


@pytest.mark.parametrize("failure", [False, True])
async def test_ha_action(hass, entry, receiver, failure):
    await setup(hass, entry)
    device = dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id)[0]
    original = receiver[1].side_effect
    wakes = []

    async def get(endpoint, **params):
        if endpoint == "powerstate":
            if params:
                wakes.append(params)
            return {"instandby": not wakes}
        if endpoint in ("supports_powerup_without_waking_tv", "set_powerup_without_waking_tv"):
            return {"result": not failure}
        return await original(endpoint, **params)

    receiver[1].side_effect = get
    call = hass.services.async_call(
        DOMAIN, "powerup_without_tv", {"device_id": device.id}, blocking=True
    )
    if failure:
        with pytest.raises(HomeAssistantError) as caught:
            await call
        assert caught.value.translation_key == "quiet_powerup_unavailable"
        assert not wakes
    else:
        await call
        assert wakes == [{"newstate": 4}]
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN, "powerup_without_tv", {"device_id": "missing"}, blocking=True
        )


async def test_concurrent_wakes_arm_once():
    armed = asyncio.Event()
    release = asyncio.Event()
    awake = False
    arms = 0

    async def get(endpoint, **params):
        nonlocal awake, arms
        if endpoint == "set_powerup_without_waking_tv":
            arms += 1
            armed.set()
            await release.wait()
            return {"result": True}
        if endpoint == "supports_powerup_without_waking_tv":
            return {"result": True}
        if params:
            awake = True
        return {"instandby": not awake}

    client = SimpleNamespace(command_lock=asyncio.Lock(), get=get)
    first = asyncio.create_task(powerup_without_tv(client))
    await armed.wait()
    second = asyncio.create_task(powerup_without_tv(client))
    release.set()
    await asyncio.gather(first, second)
    assert arms == 1 and awake


@pytest.mark.parametrize("disconnect", [None, "arm", "wake"])
async def test_http_sequence(aiohttp_server, socket_enabled, disconnect):
    from aiohttp import web

    writes = []
    awake = False

    async def serve(request):
        nonlocal awake
        if request.path.endswith("/supports_powerup_without_waking_tv"):
            return web.json_response(True)
        action = (
            "arm"
            if request.path.endswith("/set_powerup_without_waking_tv")
            else ("wake" if request.query else None)
        )
        if action:
            writes.append(action)
            if action == "wake":
                awake = True
            if disconnect == action:
                request.transport.close()
            return web.json_response(True if action == "arm" else {"result": True})
        return web.json_response({"result": True, "instandby": not awake})

    app = web.Application()
    app.router.add_get("/api/{endpoint}", serve)
    server = await aiohttp_server(app)
    async with aiohttp.ClientSession(middlewares=(power_command_middleware,)) as session:
        client = OpenWebifClient(session, server.host, port=server.port)
        if disconnect:
            with pytest.raises(QuietPowerupError, match="quiet_powerup_unconfirmed"):
                await powerup_without_tv(client)
        else:
            await powerup_without_tv(client)
    assert writes == (["arm"] if disconnect == "arm" else ["arm", "wake"])
