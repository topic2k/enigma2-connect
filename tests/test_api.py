# SPDX-License-Identifier: Apache-2.0
"""Transport status handling, command rejection and mute idempotence."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import aiohttp
import pytest
from yarl import URL

from custom_components.enigma2_connect.api import (
    AuthenticationError,
    CommandRejectedError,
    ConnectionError,
    OpenWebifClient,
    PowerCommandUnconfirmed,
    ProtocolError,
    UnsupportedError,
    power_command_middleware,
)


def client_for(status=200, data=None):
    response = MagicMock(status=status)
    response.json = AsyncMock(return_value=data if data is not None else {"result": True})
    response.read = AsyncMock(return_value=b"\xff\xd8\xffimage")
    session = MagicMock()
    session.get.return_value.__aenter__ = AsyncMock(return_value=response)
    return OpenWebifClient(session, "::1", username="root", password="secret"), response


def test_client_without_username_sends_no_authorization_header():
    client = OpenWebifClient(MagicMock(), "::1")
    assert client.headers == {}


@pytest.mark.parametrize(
    ("status", "error"),
    [
        (401, AuthenticationError),
        (403, AuthenticationError),
        (404, UnsupportedError),
        (302, ProtocolError),
    ],
)
async def test_http_errors(status, error):
    client, _ = client_for(status)
    with pytest.raises(error):
        await client.get("about")


@pytest.mark.parametrize("data", [[1], {"result": False}, {"result": "false"}])
async def test_invalid_json_structure(data):
    client, _ = client_for(data=data)
    with pytest.raises(ProtocolError):
        await client.get("about")


async def test_rejected_command():
    client, _ = client_for(data={"state": False})
    with pytest.raises(ProtocolError):
        await client.command("remotecontrol", command=1)


async def test_timeout_and_json_error():
    client, response = client_for()
    response.json.side_effect = ValueError()
    with pytest.raises(ProtocolError):
        await client.get("about")
    response.json.side_effect = asyncio.TimeoutError()
    with pytest.raises(ConnectionError):
        await client.get("about")
    response.json.side_effect = aiohttp.ClientConnectionError()
    with pytest.raises(ConnectionError):
        await client.get("about")


async def test_credentials_not_in_url_and_message_encoding():
    client, _ = client_for()
    await client.command("message", text="A & B? # Grüße")
    args, kwargs = client.session.get.call_args
    assert str(args[0]) == "http://[::1]/api/message"
    assert kwargs["params"]["text"] == "A & B? # Grüße"
    assert kwargs["headers"]["Authorization"] == "Basic cm9vdDpzZWNyZXQ="
    assert kwargs["allow_redirects"] is False


@pytest.mark.parametrize(
    ("actual", "desired", "calls"),
    [(True, True, 1), (False, False, 1), (True, False, 2), (False, True, 2)],
)
async def test_mute_idempotence(actual, desired, calls):
    client, _ = client_for(data={"ismuted": actual})
    await client.set_mute(desired)
    assert client.session.get.call_count == calls


async def test_image_response_validation():
    client, response = client_for()
    assert await client.screenshot() == b"\xff\xd8\xffimage"
    response.read.return_value = b"<html>Login</html>"
    with pytest.raises(ProtocolError):
        await client.screenshot()
    with pytest.raises(UnsupportedError):
        await client.picon("4097:0:0:0:0:0:0:0:0:0:http%3a//example.test")


async def test_sequences_do_not_interleave():
    client, response = client_for()
    await asyncio.gather(client.keys([1, 2], 0.001), client.keys([3, 4], 0.001))
    assert [call.kwargs["params"]["command"] for call in client.session.get.call_args_list] == [
        1,
        2,
        3,
        4,
    ]


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (aiohttp.ConnectionTimeoutError(), ConnectionError),
        (aiohttp.ServerDisconnectedError(), PowerCommandUnconfirmed),
        (TimeoutError(), PowerCommandUnconfirmed),
    ],
)
async def test_power_middleware_does_not_replay_commands(error, expected):
    handler = AsyncMock(side_effect=error)
    request = SimpleNamespace(url=URL("http://receiver.local/api/powerstate?newstate=2"))
    with pytest.raises(expected):
        await power_command_middleware(request, handler)
    handler.assert_awaited_once_with(request)


async def test_power_middleware_passes_reads_and_successes():
    response = object()
    handler = AsyncMock(return_value=response)
    for path in ("/api/statusinfo", "/api/powerstate?newstate=4", "/api/powerstate?newstate=3"):
        assert (
            await power_command_middleware(
                SimpleNamespace(url=URL("http://receiver.local" + path)), handler
            )
            is response
        )


async def test_lost_power_response_is_unconfirmed():
    client, response = client_for()
    response.json.side_effect = aiohttp.ClientPayloadError()
    with pytest.raises(PowerCommandUnconfirmed):
        await client.command("powerstate", newstate=1)
    assert client.session.get.call_count == 1


@pytest.mark.parametrize(("codes", "delay"), [([], 0), ([768], 0), ([1] * 501, 0), ([1], 6)])
async def test_invalid_key_sequence_never_sends(codes, delay):
    client, _ = client_for()
    with pytest.raises(ValueError):
        await client.keys(codes, delay)
    client.session.get.assert_not_called()


async def test_rejected_key_stops_sequence_and_releases_lock():
    client, response = client_for(data={"state": False})
    with pytest.raises(ProtocolError):
        await client.keys([1, 2], 0)
    assert client.session.get.call_count == 1
    response.json.return_value = {"state": True}
    await client.keys([3], 0, hold=True)
    assert client.session.get.call_args.kwargs["params"] == {"command": 3, "type": "long"}


async def test_missing_mute_state_does_not_toggle():
    client, _ = client_for(data={})
    with pytest.raises(ProtocolError):
        await client.set_mute(True)
    assert client.session.get.call_count == 1


@pytest.mark.parametrize(
    "data",
    [
        {"result": True, "timer": {"eit": 42}},
        {"state": "true", "data": [1, 2]},
        {},
    ],
)
async def test_command_result_retains_success_and_legacy_return_contract(data):
    client, _ = client_for(data=data)
    assert await client.command_result("message", text="Test") == data
    assert await client.command("message", text="Test") is None
    assert client.session.get.call_count == 2
    assert client.session.get.call_args.kwargs["params"] == {"text": "Test"}


@pytest.mark.parametrize("flag", ["result", "state"])
@pytest.mark.parametrize("value", [False, "false", 0, "0"])
async def test_rejected_command_retains_details_without_exposing_them(flag, value):
    conflicts = [{"name": "Private programme", "begin": 100, "end": 200}]
    data = {flag: value, "message": "http://root:secret@receiver/", "conflicts": conflicts}
    client, response = client_for(data=data)
    with pytest.raises(CommandRejectedError) as caught:
        await client.command_result("timerchange")
    assert isinstance(caught.value, ProtocolError)
    assert caught.value.response == data
    assert caught.value.response["conflicts"] == conflicts
    assert "secret" not in str(caught.value)
    assert "Private programme" not in repr(caught.value)
    assert client.session.get.call_count == 1
    assert not client.command_lock.locked()
    response.json.return_value = {"result": True}
    assert await client.command_result("timerchange") == {"result": True}


async def test_rejected_read_remains_a_protocol_error_with_details():
    client, _ = client_for(data={"result": False, "conflicts": []})
    with pytest.raises(ProtocolError) as caught:
        await client.get("timeradd")
    assert isinstance(caught.value, CommandRejectedError)
    assert caught.value.response == {"result": False, "conflicts": []}


async def test_command_results_share_lock_with_existing_commands():
    client, response = client_for()
    entered = asyncio.Event()
    release = asyncio.Event()

    async def reply(**_kwargs):
        entered.set()
        await release.wait()
        return {"result": True}

    response.json.side_effect = reply
    first = asyncio.create_task(client.command_result("timeradd"))
    await asyncio.wait_for(entered.wait(), timeout=5)
    second = asyncio.create_task(client.command("timerdelete"))
    try:
        await asyncio.sleep(0)
        assert client.session.get.call_count == 1
        release.set()
        assert await asyncio.gather(first, second) == [{"result": True}, None]
        assert [call.args[0].path for call in client.session.get.call_args_list] == [
            "/api/timeradd",
            "/api/timerdelete",
        ]
    finally:
        release.set()
        await asyncio.gather(first, second, return_exceptions=True)


async def test_cancelled_command_result_releases_lock():
    client, response = client_for()
    entered = asyncio.Event()

    async def reply(**_kwargs):
        entered.set()
        await asyncio.Event().wait()

    response.json.side_effect = reply
    task = asyncio.create_task(client.command_result("recordnow"))
    await asyncio.wait_for(entered.wait(), timeout=5)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert not client.command_lock.locked()
    response.json.side_effect = None
    assert await client.command_result("timerdelete") == {"result": True}


@pytest.mark.parametrize("error", [TimeoutError(), aiohttp.ClientPayloadError()])
async def test_command_result_transport_failure_releases_lock(error):
    client, response = client_for()
    response.json.side_effect = error
    with pytest.raises(ConnectionError):
        await client.command_result("timerchange")
    assert not client.command_lock.locked()
    assert client.session.get.call_count == 1
    response.json.side_effect = None
    assert await client.command_result("timerdelete") == {"result": True}
