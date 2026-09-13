# SPDX-License-Identifier: Apache-2.0
"""Async OpenWebif JSON transport, independent of Home Assistant."""

from __future__ import annotations

import asyncio
from base64 import b64encode
from typing import Any, Literal, overload

import aiohttp
from yarl import URL

from .models import JsonObject, boolean, picon_candidates


class ReceiverError(Exception):
    """Receiver request failed."""


class AuthenticationError(ReceiverError):
    """Credentials rejected."""


class ConnectionError(ReceiverError):
    """Receiver unavailable."""


class UnsupportedError(ReceiverError):
    """Endpoint unavailable on this image."""


class ProtocolError(ReceiverError):
    """Malformed reply or rejected command."""


class PowerCommandUnconfirmed(ReceiverError):
    """Power transition may have started before its response was received."""


async def power_command_middleware(
    request: aiohttp.ClientRequest, handler: aiohttp.ClientHandlerType
) -> aiohttp.ClientResponse:
    """Do not replay a disruptive GET after losing its response.

    Install on the session so Home Assistant's own middleware remains active.
    Raising our own exception inside the handler prevents aiohttp's GET retry.
    """
    if request.url.path != "/api/powerstate" or request.url.query.get("newstate") not in (
        "1",
        "2",
        "3",
    ):
        return await handler(request)
    try:
        return await handler(request)
    except (aiohttp.ClientConnectorError, aiohttp.ConnectionTimeoutError) as err:
        raise ConnectionError("Cannot connect to receiver") from err
    except (aiohttp.ClientConnectionError, TimeoutError) as err:
        raise PowerCommandUnconfirmed("Power command response was not received") from err


class OpenWebifClient:
    def __init__(
        self,
        session: aiohttp.ClientSession,
        host: str,
        port: int = 80,
        username: str = "",
        password: str = "",
        use_https: bool = False,
        verify_ssl: bool = True,
        timeout: int = 10,
    ) -> None:
        self.session = session
        self.base_url = URL.build(scheme="https" if use_https else "http", host=host, port=port)
        self.headers = (
            {"Authorization": "Basic " + b64encode(f"{username}:{password}".encode()).decode()}
            if username
            else {}
        )
        self.verify_ssl = verify_ssl
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        # All entities share this lock so state-changing requests stay ordered.
        self.command_lock = asyncio.Lock()

    @overload
    async def request(
        self, path: str, params: dict[str, Any] | None = None, *, image: Literal[False] = False
    ) -> JsonObject: ...

    @overload
    async def request(
        self, path: str, params: dict[str, Any] | None = None, *, image: Literal[True]
    ) -> bytes: ...

    async def request(
        self, path: str, params: dict[str, Any] | None = None, *, image: bool = False
    ) -> JsonObject | bytes:
        disruptive_power = path == "/api/powerstate" and str((params or {}).get("newstate")) in (
            "1",
            "2",
            "3",
        )
        try:
            async with self.session.get(
                self.base_url.with_path(path),
                params=params,
                headers=self.headers,
                ssl=self.verify_ssl,
                timeout=self.timeout,
                allow_redirects=False,
            ) as response:
                if response.status in (401, 403):
                    raise AuthenticationError("Receiver authentication failed")
                if response.status in (404, 405, 501):
                    raise UnsupportedError("Endpoint is not supported")
                if 300 <= response.status < 400:
                    raise ProtocolError("Configure the receiver's final HTTP/HTTPS address")
                response.raise_for_status()
                if image:
                    content = await response.read()
                    if not content.startswith((b"\xff\xd8\xff", b"\x89PNG\r\n\x1a\n")):
                        raise ProtocolError("Receiver did not return an image")
                    return content
                # Accept JSON even when the receiver reports a different MIME type.
                data = await response.json(content_type=None)
                if not isinstance(data, dict):
                    raise ProtocolError("Expected a JSON object")
                if "result" in data and boolean(data["result"]) is False:
                    raise ProtocolError("Receiver rejected the request")
                return data
        except (TimeoutError, aiohttp.ClientError) as err:
            # URLs and receiver response text may contain secrets: do not expose them.
            if (
                disruptive_power
                and isinstance(
                    err, (TimeoutError, aiohttp.ClientConnectionError, aiohttp.ClientPayloadError)
                )
                and not isinstance(
                    err, (aiohttp.ClientConnectorError, aiohttp.ConnectionTimeoutError)
                )
            ):
                raise PowerCommandUnconfirmed("Power command response was not received") from err
            raise ConnectionError("Cannot communicate with receiver") from err
        except (ValueError, UnicodeError) as err:
            raise ProtocolError("Invalid JSON response") from err

    async def get(self, endpoint: str, **params: Any) -> JsonObject:
        return await self.request(f"/api/{endpoint}", params or None)

    async def command(self, endpoint: str, **params: Any) -> None:
        async with self.command_lock:
            data = await self.get(endpoint, **params)
            if "state" in data and boolean(data["state"]) is False:
                raise ProtocolError("Receiver rejected the command")

    async def keys(self, codes: list[int], delay: float = 0.3, hold: bool = False) -> None:
        if not codes or len(codes) > 500 or any(not 0 <= code <= 0x2FF for code in codes):
            raise ValueError("Invalid key sequence")
        if not 0 <= delay <= 5:
            raise ValueError("Delay must be between 0 and 5 seconds")
        # Hold the lock across delays to keep other commands out of a key sequence.
        async with self.command_lock:
            for index, code in enumerate(codes):
                data = await self.get(
                    "remotecontrol", command=code, type="long" if hold else "short"
                )
                if "state" in data and boolean(data["state"]) is False:
                    raise ProtocolError("Receiver rejected the key")
                if index < len(codes) - 1 and delay:
                    await asyncio.sleep(delay)

    async def set_mute(self, desired: bool) -> None:
        """OpenWebif provides a toggle: read live state inside the command lock."""
        async with self.command_lock:
            state = await self.get("vol")
            muted = boolean(state.get("ismute", state.get("ismuted", state.get("muted"))))
            if muted is None:
                raise ProtocolError("Receiver did not report mute state")
            if muted != desired:
                await self.get("vol", set="mute")

    async def screenshot(self) -> bytes:
        return await self.request("/grab", {"format": "jpg", "r": 720}, image=True)

    async def picon(
        self, reference: str, channel: str | None = None, hint: str | None = None
    ) -> bytes:
        for path in picon_candidates(reference, channel, hint):
            try:
                return await self.request(path, image=True)
            except UnsupportedError:
                continue
        raise UnsupportedError("No picon found for this service")
