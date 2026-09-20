# SPDX-License-Identifier: Apache-2.0
"""Optional HA responses, refreshes and no replay of uncertain timer writes."""

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import aiohttp
import pytest
from aiohttp import web
from homeassistant.core import SupportsResponse
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from yarl import URL

from custom_components.enigma2_connect.api import (
    TIMER_COMMANDS,
    AuthenticationError,
    CommandRejectedError,
    CommandUnconfirmed,
    ConnectionError,
    OpenWebifClient,
    power_command_middleware,
)
from custom_components.enigma2_connect.const import DOMAIN

from .test_api import client_for
from .test_integration import setup

REFERENCE = "1:0:19:283D:3FB:1:C00000:0:0:0:"


@pytest.mark.parametrize("endpoint", sorted(TIMER_COMMANDS))
async def test_real_http_lost_timer_response_is_sent_once(aiohttp_server, socket_enabled, endpoint):
    """Warm a keep-alive connection: aiohttp would otherwise replay the GET."""
    writes = 0

    async def handler(request):
        nonlocal writes
        if request.path == f"/api/{endpoint}":
            writes += 1
            request.transport.abort()
            return web.Response()
        return web.json_response({"result": True})

    app = web.Application()
    app.router.add_get("/api/{endpoint}", handler)
    server = await aiohttp_server(app)
    async with aiohttp.ClientSession(middlewares=(power_command_middleware,)) as session:
        client = OpenWebifClient(session, server.host, server.port)
        await client.get("statusinfo")
        with pytest.raises(CommandUnconfirmed):
            await client.command_result(endpoint)
        assert writes == 1
        assert not client.command_lock.locked()
        assert await client.get("statusinfo") == {"result": True}


@pytest.mark.parametrize(
    "error",
    [
        aiohttp.ConnectionTimeoutError(),
        aiohttp.ClientConnectorError(SimpleNamespace(ssl=False, host="host", port=80), OSError()),
    ],
)
async def test_connect_failure_is_not_reported_as_sent(error):
    handler = AsyncMock(side_effect=error)
    with pytest.raises(ConnectionError) as caught:
        await power_command_middleware(
            SimpleNamespace(url=URL("http://host/api/timeradd")), handler
        )
    assert not isinstance(caught.value, CommandUnconfirmed)
    handler.assert_awaited_once()


@pytest.mark.parametrize(
    "data", [{}, {"result": "unknown"}, {"result": True, "state": None}, [], None]
)
async def test_unknown_command_reply_is_not_success(data):
    client, response = client_for()
    response.json.return_value = data
    with pytest.raises(CommandUnconfirmed):
        await client.command_result("timeradd")
    assert client.session.get.call_count == 1


@pytest.mark.parametrize(
    "data", [{"result": "1"}, {"state": True}, {"result": True, "state": "true"}]
)
async def test_known_command_acknowledgements(data):
    client, _ = client_for(data=data)
    assert await client.command_result("timeradd") == data


@pytest.mark.parametrize(
    "error",
    [
        ValueError("secret"),
        UnicodeError("secret"),
        aiohttp.ClientPayloadError("secret"),
        TimeoutError("secret"),
        aiohttp.ServerDisconnectedError(),
    ],
)
async def test_unreadable_command_reply_is_uncertain_and_private(error):
    client, response = client_for()
    response.json.side_effect = error
    with pytest.raises(CommandUnconfirmed) as caught:
        await client.command_result("timertogglestatus")
    assert "secret" not in str(caught.value)
    assert client.session.get.call_count == 1


@pytest.mark.parametrize("action", ["timer_add", "timer_toggle", "timer_delete"])
async def test_optional_ha_response_contains_only_addressed_timer(hass, entry, receiver, action):
    await setup(hass, entry)
    device = dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id)[0]
    data = {
        "device_id": device.id,
        "service_reference": " " + REFERENCE + " ",
        "begin": "2026-09-20T12:00:00+02:00",
        "end": "2026-09-20T12:02:00+02:00",
    }
    if action == "timer_add":
        data["name"] = "Test"
    assert hass.services.supports_response(DOMAIN, action) is SupportsResponse.OPTIONAL
    with patch.object(
        entry.runtime_data.client,
        "command_result",
        return_value={"result": True, "message": "secret", "logentries": ["private"]},
    ) as command:
        result = await hass.services.async_call(
            DOMAIN, action, data, blocking=True, return_response=True
        )
    assert result == {
        "action": action,
        "timer": {"service_reference": REFERENCE, "begin": 1789898400, "end": 1789898520},
    }
    assert "secret" not in json.dumps(result)
    assert command.await_count == 1
    assert any(call.args == ("timerlist",) for call in receiver[1].call_args_list)
    assert await hass.services.async_call(DOMAIN, action, data, blocking=True) is None
    assert receiver[2].await_count == 1


@pytest.mark.parametrize(
    ("error", "key"),
    [
        (CommandUnconfirmed("secret"), "timer_unconfirmed"),
        (
            CommandRejectedError({"result": False, "message": "secret", "conflicts": []}),
            "request_failed",
        ),
        (AuthenticationError("secret"), "invalid_auth"),
    ],
)
@pytest.mark.parametrize("response", [False, True])
async def test_failure_refreshes_lists_but_never_returns_success(
    hass, entry, receiver, error, key, response
):
    await setup(hass, entry)
    coordinator = entry.runtime_data
    device = dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id)[0]
    command = "command_result" if response else "command"
    with (
        patch.object(coordinator.client, command, side_effect=error) as send,
        patch.object(coordinator, "async_request_refresh") as refresh,
        patch.object(entry, "async_start_reauth") as reauth,
    ):
        with pytest.raises(HomeAssistantError) as caught:
            await hass.services.async_call(
                DOMAIN,
                "timer_delete",
                {"device_id": device.id, "service_reference": REFERENCE, "begin": 100, "end": 200},
                blocking=True,
                return_response=response,
            )
        assert caught.value.translation_key == key
        assert "secret" not in str(caught.value)
        send.assert_awaited_once()
        refresh.assert_awaited_once()
        assert coordinator._slow_due == 0 and coordinator._catalog_due == 0
        assert reauth.call_count == int(key == "invalid_auth")


async def test_cancelled_ha_timer_marks_lists_dirty_without_retry(hass, entry, receiver):
    await setup(hass, entry)
    coordinator = entry.runtime_data
    device = dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id)[0]
    with (
        patch.object(coordinator.client, "command", side_effect=asyncio.CancelledError) as send,
        patch.object(coordinator, "async_request_refresh") as refresh,
    ):
        with pytest.raises(asyncio.CancelledError):
            await hass.services.async_call(
                DOMAIN,
                "timer_toggle",
                {"device_id": device.id, "service_reference": REFERENCE, "begin": 100, "end": 200},
                blocking=True,
            )
        assert coordinator._slow_due == 0
        send.assert_awaited_once()
        refresh.assert_not_awaited()


async def test_coordinator_preserves_result_and_timer_error_after_failed_refresh(
    hass, entry, receiver
):
    await setup(hass, entry)
    coordinator = entry.runtime_data
    expected = {"value": 42}
    method = AsyncMock(return_value=expected)
    assert await coordinator.perform(method, refresh=False) is expected
    receiver[0]["timerlist"] = ConnectionError()
    device = dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id)[0]
    receiver[2].side_effect = CommandUnconfirmed()
    with pytest.raises(HomeAssistantError) as caught:
        await hass.services.async_call(
            DOMAIN,
            "timer_delete",
            {
                "device_id": device.id,
                "service_reference": REFERENCE,
                "begin": 100,
                "end": 200,
            },
            blocking=True,
        )
    assert caught.value.translation_key == "timer_unconfirmed"
    assert coordinator.data.timers is None
    assert "timerlist" in coordinator.optional_errors
    receiver[2].assert_awaited_once()
