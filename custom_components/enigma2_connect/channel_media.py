# SPDX-License-Identifier: Apache-2.0
"""Optional receiver-owned channel browsing and authenticated picons."""

import asyncio
from collections import OrderedDict
from hashlib import sha256
from time import monotonic

from aiohttp import web
from homeassistant.components.http import HomeAssistantView
from homeassistant.components.media_player import MediaClass
from homeassistant.components.media_source import BrowseMediaSource, Unresolvable
from homeassistant.config_entries import ConfigEntryState

from .api import ReceiverError
from .const import DOMAIN

CONF_SHOW_CHANNELS = "media_show_channels"
CONF_CHANNEL_BOUQUET = "media_channel_bouquet"
PICON_FALLBACK = b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 160 90"><rect x="20" y="10" width="120" height="65" rx="5" fill="#263238"/><path d="M60 82h40" stroke="#b0bec5" stroke-width="5"/></svg>'


def channel_identifier(entry, channel):
    return f"channel/{entry.entry_id}/{sha256(channel.reference.encode()).hexdigest()}"


def channel_entry(hass, entry_id):
    entry = hass.config_entries.async_get_entry(entry_id)
    if (
        not entry
        or entry.domain != DOMAIN
        or entry.state is not ConfigEntryState.LOADED
        or not entry.options.get(CONF_SHOW_CHANNELS, False)
        or not entry.runtime_data.last_update_success
        or entry.runtime_data.data.media_channels is None
    ):
        raise Unresolvable(translation_domain=DOMAIN, translation_key="channel_unavailable")
    return entry


def channel_from_identifier(hass, identifier):
    kind, _, remainder = (identifier or "").partition("/")
    entry_id, _, digest = remainder.partition("/")
    if kind != "channel":
        raise Unresolvable(translation_domain=DOMAIN, translation_key="channel_unavailable")
    entry = channel_entry(hass, entry_id)
    for channel in (entry.runtime_data.data.media_channels or {}).values():
        if sha256(channel.reference.encode()).hexdigest() == digest:
            return entry, channel
    raise Unresolvable(translation_domain=DOMAIN, translation_key="channel_unavailable")


def channel_folder(entry, title, children=None):
    return BrowseMediaSource(
        domain=DOMAIN,
        identifier=f"channels/{entry.entry_id}",
        title=title,
        media_class=MediaClass.DIRECTORY,
        media_content_type="enigma2_directory",
        can_play=False,
        can_expand=True,
        children=children,
    )


def browse_channels(entry, title):
    children = [
        BrowseMediaSource(
            domain=DOMAIN,
            identifier=channel_identifier(entry, channel),
            title=label,
            media_class=MediaClass.CHANNEL,
            media_content_type="video/mpeg",
            thumbnail=f"/api/{DOMAIN}/channel_picon/{entry.entry_id}/{sha256(channel.reference.encode()).hexdigest()}",
            can_play=True,
            can_expand=False,
        )
        for label, channel in (entry.runtime_data.data.media_channels or {}).items()
    ]
    return channel_folder(entry, title, children)


class ChannelPiconView(HomeAssistantView):
    url = f"/api/{DOMAIN}/channel_picon/{{entry_id}}/{{digest}}"
    name = f"api:{DOMAIN}:channel_picon"
    requires_auth = True

    def __init__(self, hass):
        self.hass = hass
        self._cache = OrderedDict()
        self._slots = asyncio.Semaphore(4)

    async def get(self, request, entry_id, digest):
        identifier = f"channel/{entry_id}/{digest}"
        try:
            entry, channel = channel_from_identifier(self.hass, identifier)
        except Unresolvable:
            raise web.HTTPNotFound() from None
        # Include the name because name-based picon lookup can change on rename.
        key = identifier, channel.name
        async with self._slots:
            cached = self._cache.get(key)
            if cached and cached[0] > monotonic():
                _, content, mime, ttl = cached
                self._cache.move_to_end(key)
            else:
                try:
                    content = await entry.runtime_data.client.picon(channel.reference, channel.name)
                    mime = "image/png" if content.startswith(b"\x89PNG") else "image/jpeg"
                    ttl = 900
                except ReceiverError:
                    content, mime, ttl = PICON_FALLBACK, "image/svg+xml", 120
                self._cache[key] = (monotonic() + ttl, content, mime, ttl)
                while len(self._cache) > 256:
                    self._cache.popitem(last=False)
        return web.Response(
            body=content, content_type=mime, headers={"Cache-Control": f"private, max-age={ttl}"}
        )
