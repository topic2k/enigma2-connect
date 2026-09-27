# SPDX-License-Identifier: Apache-2.0
"""Optional preservation of receiver timeshift save warnings."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import aiohttp
import pytest
from aiohttp import web

from custom_components.enigma2_connect.api import (
    AuthenticationError,
    CommandRejectedError,
    CommandUnconfirmed,
    OpenWebifClient,
    UnsupportedError,
    power_command_middleware,
)
from custom_components.enigma2_connect.timeshift import (
    CONF_RESTORE_TIMESHIFT_WARNING,
    TimeshiftError,
    parse_warning,
    set_timeshift,
)

KEY = "config.timeshift.check"


def config(value, key=KEY):
    return {"configs": [{"path": key, "data": {"result": True, "current": value}}]}


@pytest.mark.parametrize(
    "data",
    [
        {},
        {"configs": {}},
        {"configs": []},
        {"configs": [None, {"path": []}]},
        {"configs": [{"path": KEY}]},
        config(None),
        {"configs": [{"path": KEY, "data": {"result": False, "current": True}}]},
        {"configs": config(True)["configs"] * 2},
        {
            "configs": config(True)["configs"]
            + config(True, "config.usage.check_timeshift")["configs"]
        },
    ],
)
def test_bad_config(data):
    with pytest.raises(TimeshiftError) as error:
        parse_warning(data)
    assert error.value.reason == "timeshift_warning_unavailable"


@pytest.mark.parametrize("key", [KEY, "config.usage.check_timeshift"])
@pytest.mark.parametrize("value", [True, False])
def test_config(key, value):
    assert parse_warning(config(value, key)) == (key, value)


def simulated(enabled=True, warning=True, failure=None):
    state = {"enabled": enabled, "warning": warning, "written": False}
    client = SimpleNamespace(command_lock=asyncio.Lock())

    async def get(endpoint):
        assert client.command_lock.locked()
        if endpoint == "statusinfo":
            return {"inStandby": False}
        if endpoint == "tsstate":
            return {"state": True, "timeshiftEnabled": state["enabled"]}
        if endpoint == "config/Timeshift":
            if failure == "pre_auth" or (state["written"] and failure == "post_auth"):
                raise AuthenticationError()
            if failure == "pre_read" or (state["written"] and failure == "post_read"):
                raise UnsupportedError()
            return config(
                state["warning"],
                "config.usage.check_timeshift"
                if state["written"] and failure == "key_change"
                else KEY,
            )
        assert endpoint in ("tsstart", "tsstop")
        state["written"] = True
        state["enabled"] = endpoint == "tsstart"
        if endpoint == "tsstop" or failure == "start_mutation":
            state["warning"] = False
        if failure == "write_lost":
            raise CommandUnconfirmed()
        if failure == "write_rejected":
            raise CommandRejectedError({"state": False})
        if failure == "cancel":
            raise asyncio.CancelledError()
        return {"state": True}

    async def post(endpoint, **params):
        assert client.command_lock.locked()
        assert endpoint == "saveconfig" and params == {"key": KEY, "value": "true"}
        if failure == "restore_auth":
            raise AuthenticationError()
        if failure == "restore_rejected":
            raise CommandRejectedError({"result": False})
        if failure != "not_restored":
            state["warning"] = True
        if failure == "restore_lost":
            raise CommandUnconfirmed()
        return {"result": True}

    client.get = AsyncMock(side_effect=get)
    client.post = AsyncMock(side_effect=post)
    return client, state


@pytest.mark.parametrize("desired", [True, False])
@pytest.mark.parametrize("before", [True, False])
async def test_restore_only_previous_true(desired, before):
    client, state = simulated(enabled=not desired, warning=before)
    await set_timeshift(client, desired, restore_save_warning=True)
    assert state["enabled"] is desired
    assert state["warning"] is before
    assert client.post.await_count == int(before and not desired)
    assert not client.command_lock.locked()


async def test_disabled_option_does_not_access_config():
    client, state = simulated()
    await set_timeshift(client, False)
    assert state["warning"] is False
    assert not any(c.args[0] == "config/Timeshift" for c in client.get.call_args_list)
    client.post.assert_not_awaited()


async def test_noop_does_not_access_config():
    client, _ = simulated()
    await set_timeshift(client, True, restore_save_warning=True)
    client.post.assert_not_awaited()
    assert not any(c.args[0] == "config/Timeshift" for c in client.get.call_args_list)


@pytest.mark.parametrize("failure", ["pre_read", "pre_auth"])
async def test_preflight_failure_never_writes(failure):
    client, state = simulated(failure=failure)
    with pytest.raises(AuthenticationError if failure == "pre_auth" else TimeshiftError):
        await set_timeshift(client, False, restore_save_warning=True)
    assert not state["written"]
    client.post.assert_not_awaited()


@pytest.mark.parametrize(
    ("failure", "expected"),
    [
        ("write_lost", TimeshiftError),
        ("write_rejected", CommandRejectedError),
        ("cancel", asyncio.CancelledError),
    ],
)
async def test_command_failure_still_restores(failure, expected):
    client, state = simulated(failure=failure)
    with pytest.raises(expected):
        await set_timeshift(client, False, restore_save_warning=True)
    assert state["warning"] is True
    client.post.assert_awaited_once()
    assert not client.command_lock.locked()


@pytest.mark.parametrize(
    "failure",
    ["post_read", "key_change", "restore_rejected", "not_restored", "post_auth", "restore_auth"],
)
async def test_restore_failure_is_visible(failure):
    client, state = simulated(failure=failure)
    with pytest.raises(
        AuthenticationError if failure.endswith("auth") else TimeshiftError
    ) as error:
        await set_timeshift(client, False, restore_save_warning=True)
    if isinstance(error.value, TimeshiftError):
        assert error.value.reason == "timeshift_warning_restore_failed"
    assert state["written"]
    assert client.post.await_count <= 1
    assert not client.command_lock.locked()


@pytest.mark.parametrize("failure", ["restore_lost", "start_mutation"])
async def test_confirm_actual_restore_without_replay(failure):
    client, state = simulated(enabled=failure != "start_mutation", failure=failure)
    await set_timeshift(client, failure == "start_mutation", restore_save_warning=True)
    assert state["warning"] is True
    client.post.assert_awaited_once()


async def test_option_defaults_and_saved_value(hass, entry):
    with patch.object(hass.config_entries, "async_reload", new_callable=AsyncMock):
        menu = await hass.config_entries.options.async_init(entry.entry_id)
        form = await hass.config_entries.options.async_configure(
            menu["flow_id"], {"next_step_id": "settings"}
        )
        values = form["data_schema"]({})
        assert values[CONF_RESTORE_TIMESHIFT_WARNING] is False
        result = await hass.config_entries.options.async_configure(
            form["flow_id"], {**values, CONF_RESTORE_TIMESHIFT_WARNING: True}
        )
        assert result["type"] == "create_entry"
        assert entry.options[CONF_RESTORE_TIMESHIFT_WARNING] is True
        menu = await hass.config_entries.options.async_init(entry.entry_id)
        form = await hass.config_entries.options.async_configure(
            menu["flow_id"], {"next_step_id": "settings"}
        )
        assert form["data_schema"]({})[CONF_RESTORE_TIMESHIFT_WARNING] is True


async def test_coordinator_passes_receiver_option(hass, entry, receiver):
    from .test_integration import setup

    await setup(hass, entry)
    hass.config_entries.async_update_entry(entry, options={CONF_RESTORE_TIMESHIFT_WARNING: True})
    with patch(
        "custom_components.enigma2_connect.coordinator.set_timeshift", new_callable=AsyncMock
    ) as call:
        await entry.runtime_data.async_set_timeshift(False)
        call.assert_awaited_once_with(entry.runtime_data.client, False, restore_save_warning=True)


@pytest.mark.parametrize("lost", [False, True])
async def test_real_post_form_and_no_replay(aiohttp_server, socket_enabled, lost):
    requests = []

    async def handler(request):
        requests.append(dict(await request.post()))
        assert request.headers.get("Authorization", "").startswith("Basic ")
        if lost:
            request.transport.abort()
        return web.json_response({"result": True})

    app = web.Application()
    app.router.add_post("/api/saveconfig", handler)
    server = await aiohttp_server(app)
    async with aiohttp.ClientSession(middlewares=(power_command_middleware,)) as session:
        client = OpenWebifClient(
            session, server.host, server.port, username="test", password="test"
        )
        if lost:
            with pytest.raises(CommandUnconfirmed):
                await client.post("saveconfig", key=KEY, value="true")
        else:
            assert await client.post("saveconfig", key=KEY, value="true") == {"result": True}
    assert requests == [{"key": KEY, "value": "true"}]
