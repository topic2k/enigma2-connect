# SPDX-License-Identifier: Apache-2.0
"""Literal text input through simulated transport and real HA actions."""

import asyncio
from unittest.mock import patch
from urllib.parse import quote, unquote

import pytest
import voluptuous as vol
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.service import async_get_all_descriptions

from custom_components.enigma2_connect.api import (
    AuthenticationError,
    CommandRejectedError,
    OpenWebifClient,
    TextCommandUnconfirmed,
    power_command_middleware,
)
from custom_components.enigma2_connect.const import DOMAIN

from .test_api import client_for
from .test_integration import setup


@pytest.mark.parametrize("value", ["", "x" * 501, "a\nb", "\x00", "\x7f", "\x85", 1, None])
async def test_invalid_text_never_sends(value):
    client, _ = client_for()
    with pytest.raises(ValueError):
        await client.send_text(value)
    client.session.get.assert_not_called()


@pytest.mark.parametrize(
    "data", [{}, {"state": None}, {"state": "unknown"}, {"state": True, "result": None}]
)
async def test_missing_acknowledgement(data):
    client, _ = client_for(data=data)
    with pytest.raises(TextCommandUnconfirmed):
        await client.send_text("hello")
    assert client.session.get.call_count == 1


@pytest.mark.parametrize("data", [{"state": False}, {"result": False}])
async def test_rejection(data):
    client, _ = client_for(data=data)
    with pytest.raises(CommandRejectedError):
        await client.send_text("hello")


async def test_shared_lock_preserves_spaces_and_unicode():
    client, _ = client_for(data={"result": True})
    await client.command_lock.acquire()
    task = asyncio.create_task(client.send_text("  Grüße & + %20? # 日本語  "))
    await asyncio.sleep(0)
    client.session.get.assert_not_called()
    client.command_lock.release()
    await task
    assert client.session.get.call_args.kwargs["params"] == {
        "text": quote("  Grüße & + %20? # 日本語  ", safe="")
    }
    assert not client.command_lock.locked()


@pytest.mark.parametrize("disconnect", [False, True])
async def test_http_encoding_and_no_replay(aiohttp_server, socket_enabled, disconnect):
    import aiohttp
    from aiohttp import web

    calls = []

    async def serve(request):
        calls.append({"text": unquote(request.query["text"])})
        if disconnect:
            request.transport.close()
        return web.json_response({"result": True})

    app = web.Application()
    app.router.add_get("/api/remotecontrol", serve)
    server = await aiohttp_server(app)
    async with aiohttp.ClientSession(middlewares=(power_command_middleware,)) as session:
        client = OpenWebifClient(session, server.host, server.port)
        text = "  Grüße & + %20? # 日本語  "
        if disconnect:
            with pytest.raises(TextCommandUnconfirmed):
                await client.send_text(text)
        else:
            await client.send_text(text)
        assert calls == [{"text": text}]


async def test_ha_action_validation_and_descriptions(hass, entry, receiver):
    await setup(hass, entry)
    device = dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id)[0]
    receiver[0]["remotecontrol"] = {"result": True}
    receiver[1].reset_mock()
    await hass.services.async_call(
        DOMAIN, "send_text", {"device_id": device.id, "text": " A & B "}, blocking=True
    )
    receiver[1].assert_awaited_once_with("remotecontrol", text=quote(" A & B ", safe=""))
    for value in ("", "x" * 501, "\n", "\x00", 42):
        with pytest.raises(vol.Invalid):
            await hass.services.async_call(
                DOMAIN, "send_text", {"device_id": device.id, "text": value}, blocking=True
            )
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN, "send_text", {"device_id": "missing", "text": "hello"}, blocking=True
        )
    fields = (await async_get_all_descriptions(hass))[DOMAIN]["send_text"]["fields"]
    assert fields["text"]["selector"]["text"] == {"multiline": False, "multiple": False}
    assert fields["device_id"]["selector"]["device"]["integration"] == DOMAIN


@pytest.mark.parametrize(
    "error,key",
    [
        (TextCommandUnconfirmed(), "text_unconfirmed"),
        (AuthenticationError(), "invalid_auth"),
        (CommandRejectedError({"result": False}), "request_failed"),
    ],
)
async def test_ha_errors(hass, entry, receiver, error, key):
    await setup(hass, entry)
    device = dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id)[0]
    receiver[0]["remotecontrol"] = error
    with patch.object(entry, "async_start_reauth") as reauth:
        with pytest.raises(HomeAssistantError) as caught:
            await hass.services.async_call(
                DOMAIN, "send_text", {"device_id": device.id, "text": "hello"}, blocking=True
            )
        assert caught.value.translation_key == key
        assert reauth.called == isinstance(error, AuthenticationError)


@pytest.mark.parametrize("error", [ValueError(), asyncio.TimeoutError()])
async def test_unreadable_reply_is_uncertain(error):
    client, response = client_for()
    response.json.side_effect = error
    with pytest.raises(TextCommandUnconfirmed):
        await client.send_text("hello")
    assert client.session.get.call_count == 1
    assert not client.command_lock.locked()


async def test_cancelled_write_releases_lock_without_replay():
    client, response = client_for()
    response.json.side_effect = asyncio.CancelledError()
    with pytest.raises(asyncio.CancelledError):
        await client.send_text("hello")
    assert client.session.get.call_count == 1
    assert not client.command_lock.locked()


async def test_maximum_length_and_space_are_preserved():
    client, _ = client_for()
    for text in (" ", "x" * 500):
        await client.send_text(text)
        assert client.session.get.call_args.kwargs["params"] == {"text": quote(text, safe="")}
