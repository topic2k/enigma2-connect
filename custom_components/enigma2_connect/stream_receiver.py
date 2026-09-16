# SPDX-License-Identifier: Apache-2.0
"""Receiver stream discovery and a bounded relay for plain MPEG-TS HLS."""

from __future__ import annotations

from hashlib import sha256
from typing import TYPE_CHECKING

import aiohttp
from yarl import URL

if TYPE_CHECKING:
    from .api import OpenWebifClient

PLAYLIST_LIMIT = 256 * 1024
SEGMENT_LIMIT = 32 * 1024 * 1024


def receiver_url(client: OpenWebifClient, value: str) -> URL:
    """Never follow playlists to other hosts, protocols or embedded credentials."""
    url = URL(value)
    if url.scheme not in ("http", "https") or url.host != client.base_url.host or url.fragment:
        raise ValueError("Invalid receiver stream address")
    # Authenticate using the saved receiver credentials, never playlist credentials.
    return url.with_user(None)


async def fetch(client: OpenWebifClient, url: URL, limit: int, timeout: int = 8) -> bytes:
    async with client.session.get(
        url,
        headers={**client.headers, "Accept-Encoding": "identity"},
        ssl=client.verify_ssl,
        timeout=aiohttp.ClientTimeout(total=timeout),
        allow_redirects=False,
    ) as response:
        response.raise_for_status()
        if response.status != 200:
            raise ValueError("Unexpected receiver response")
        content = bytearray()
        async for chunk in response.content.iter_chunked(64 * 1024):
            content.extend(chunk)
            if len(content) > limit:
                raise ValueError("Receiver response exceeds limit")
        return bytes(content)


async def discover_hls(client: OpenWebifClient, reference: str) -> URL:
    # Unlike stream.m3u/streamnew.m3u, this endpoint zaps only with explicit zap=.
    url = client.base_url.with_path("/web/streamhls.m3u").with_query(
        ref=reference, vcodec="h264", acodec="aac"
    )
    async with client.session.get(
        url,
        headers=client.headers,
        ssl=client.verify_ssl,
        timeout=aiohttp.ClientTimeout(total=3),
        allow_redirects=False,
    ) as response:
        if response.status != 307:
            raise ValueError("Receiver HLS unavailable")
        return receiver_url(client, response.headers.get("Location", ""))


async def discover_transcoded(client: OpenWebifClient, source: URL) -> URL:
    # video.m3u calls getStream without the zapstream side effect of stream.m3u.
    url = client.base_url.with_path("/web/video.m3u").with_query(
        ref=source.path.lstrip("/"), device="phone", vcodec="h264", acodec="aac"
    )
    text = (await fetch(client, url, PLAYLIST_LIMIT, 3)).decode("utf-8-sig")
    if not text.startswith("#EXTM3U"):
        raise ValueError("Receiver playlist unavailable")
    addresses = [
        line.strip() for line in text.splitlines() if line.strip() and not line.startswith("#")
    ]
    if len(addresses) != 1:
        raise ValueError("Unexpected receiver playlist")
    result = receiver_url(client, addresses[0])
    if result.path != source.path or result == source:
        raise ValueError("No separate transcoded source")
    return result


class ReceiverHLS:
    """Relay a limited media playlist; complex HLS falls back to local packaging."""

    def __init__(self, client: OpenWebifClient, url: URL) -> None:
        self.client = client
        self.url = url
        self.segments: dict[str, URL] = {}
        self.first_segment: URL | None = None

    async def playlist(self) -> bytes:
        text = (await fetch(self.client, self.url, PLAYLIST_LIMIT)).decode("utf-8-sig")
        lines = text.splitlines()
        if not lines or lines[0].strip() != "#EXTM3U":
            raise ValueError("Not an HLS playlist")
        target = False
        output = []
        current: dict[str, URL] = {}
        # No external URI attributes, keys, maps, variants or byte ranges. Passing
        # unrecognised tags through could leak addresses or bypass the relay.
        allowed = {
            "#EXTM3U",
            "#EXTINF",
            "#EXT-X-VERSION",
            "#EXT-X-TARGETDURATION",
            "#EXT-X-MEDIA-SEQUENCE",
            "#EXT-X-DISCONTINUITY-SEQUENCE",
            "#EXT-X-DISCONTINUITY",
            "#EXT-X-ENDLIST",
            "#EXT-X-PROGRAM-DATE-TIME",
            "#EXT-X-INDEPENDENT-SEGMENTS",
            "#EXT-X-PLAYLIST-TYPE",
        }
        for raw in lines:
            line = raw.strip()
            if not line:
                continue
            if line.startswith("#"):
                tag = line.partition(":")[0]
                if tag not in allowed or "URI=" in line:
                    raise ValueError("Unsupported HLS tag")
                if tag == "#EXT-X-TARGETDURATION":
                    target = 0 < int(line.partition(":")[2]) <= 30
                # Strip optional human-readable titles supplied by the receiver.
                output.append(line.partition(",")[0] + "," if tag == "#EXTINF" else line)
                continue
            url = receiver_url(self.client, str(self.url.join(URL(line))))
            if url.origin() != self.url.origin() or not url.path.endswith(".ts"):
                raise ValueError("Unsupported HLS segment")
            filename = "remote" + sha256(str(url).encode()).hexdigest() + ".ts"
            current[filename] = url
            output.append(filename)
        if not target or not current or len(current) > 64:
            raise ValueError("Unsupported HLS window")
        self.first_segment = next(iter(current.values()))
        self.segments.update(current)
        # Retain a small previous window for in-flight browser requests.
        self.segments = dict(list(self.segments.items())[-128:])
        return ("\n".join(output) + "\n").encode()

    async def read(self, filename: str) -> bytes:
        if filename == "index.m3u8":
            return await self.playlist()
        if filename not in self.segments:
            raise FileNotFoundError()
        return await fetch(self.client, self.segments[filename], SEGMENT_LIMIT)
