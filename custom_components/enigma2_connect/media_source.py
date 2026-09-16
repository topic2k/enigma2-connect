# SPDX-License-Identifier: Apache-2.0
"""A shared recordings tile, with receiver-owned playback identifiers."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from homeassistant.components.media_source import MediaSourceItem
    from homeassistant.core import HomeAssistant

    from .coordinator import EnigmaConfigEntry
    from .media_stream import CONF_EXTERNAL_PLAYBACK, CONF_STREAM_HTTPS, CONF_STREAM_PORT
from hashlib import sha256
from pathlib import PurePosixPath
from urllib.parse import quote, unquote

from homeassistant.components.media_player.const import MediaClass
from homeassistant.components.media_player.errors import BrowseError
from homeassistant.components.media_source import (
    BrowseMediaSource,
    MediaSource,
    PlayMedia,
    Unresolvable,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.helpers.translation import async_get_cached_translations

from .channel_media import (
    CONF_SHOW_CHANNELS,
    browse_channels,
    channel_entry,
    channel_folder,
    channel_from_identifier,
)
from .const import DOMAIN
from .media_stream import CONF_EXTERNAL_PLAYBACK, CONF_STREAM_HTTPS, CONF_STREAM_PORT
from .models import JsonObject, ReceiverState, Snapshot
from .recording_images import recording_thumbnail
from .recordings import async_recording_labels, browse_recordings, recording_path

CONF_RECORDINGS_LAYOUT = "recordings_layout"


def recordings_layout(hass: HomeAssistant) -> str:
    """The shared option is mirrored across receiver entries by the options flow."""
    return next(
        (
            entry.options[CONF_RECORDINGS_LAYOUT]
            for entry in hass.config_entries.async_entries(DOMAIN)
            if CONF_RECORDINGS_LAYOUT in entry.options
        ),
        "receivers",
    )


def recording_identifier(entry: EnigmaConfigEntry, movie: JsonObject) -> str:
    # Keep receiver file paths out of media IDs while retaining stable catalog lookup.
    digest = sha256(movie["serviceref"].encode()).hexdigest()
    return f"recording/{entry.entry_id}/{digest}"


def recording_from_identifier(
    hass: HomeAssistant, identifier: str | None
) -> tuple[EnigmaConfigEntry, JsonObject]:
    """Resolve only current catalog entries; never accept arbitrary receiver paths."""
    kind, separator, remainder = (identifier or "").partition("/")
    entry_id, _, digest = remainder.partition("/")
    entry: EnigmaConfigEntry | None = hass.config_entries.async_get_entry(entry_id)
    if (
        kind != "recording"
        or not separator
        or not entry
        or entry.domain != DOMAIN
        or entry.state is not ConfigEntryState.LOADED
        or not (coordinator := getattr(entry, "runtime_data", None))
        or not coordinator.last_update_success
    ):
        raise Unresolvable(translation_domain=DOMAIN, translation_key="recording_unavailable")
    for movie in coordinator.data.movies or []:
        if movie.get("serviceref") and sha256(movie["serviceref"].encode()).hexdigest() == digest:
            return entry, movie
    raise Unresolvable(translation_domain=DOMAIN, translation_key="recording_unavailable")


async def async_get_media_source(hass: HomeAssistant) -> EnigmaRecordingSource:
    await async_recording_labels(hass)
    return EnigmaRecordingSource(hass)


class EnigmaRecordingSource(MediaSource):
    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self._name_override: str | None = None
        super().__init__(DOMAIN)

    @property
    def name(self) -> str:
        return self._name_override or async_get_cached_translations(
            self.hass, self.hass.config.language, "common", DOMAIN
        ).get(f"component.{DOMAIN}.common.recordings", "Enigma2 Connect")

    @name.setter
    def name(self, value: str | None) -> None:
        """Honor MediaSource's writable name while retaining dynamic translations."""
        self._name_override = value

    def _entries(self) -> list[EnigmaConfigEntry]:
        return sorted(
            (
                entry
                for entry in self.hass.config_entries.async_entries(DOMAIN)
                if entry.state is ConfigEntryState.LOADED and getattr(entry, "runtime_data", None)
            ),
            key=lambda entry: (entry.title.casefold(), entry.entry_id),
        )

    @staticmethod
    def _folder(
        identifier: str | None, title: str, children: list[BrowseMediaSource] | None = None
    ) -> BrowseMediaSource:
        return BrowseMediaSource(
            domain=DOMAIN,
            identifier=identifier,
            title=title,
            media_class=MediaClass.DIRECTORY,
            media_content_type="enigma2_directory",
            can_play=False,
            can_expand=True,
            children=children,
        )

    async def async_browse_media(self, item: MediaSourceItem) -> BrowseMediaSource:
        labels = await async_recording_labels(self.hass)
        identifier = item.identifier or ""
        entries = self._entries()
        if identifier == "channels":
            return self._folder(
                "channels",
                labels["channels"],
                [
                    channel_folder(entry, entry.title)
                    for entry in entries
                    if entry.options.get(CONF_SHOW_CHANNELS, False)
                ],
            )
        if identifier.startswith("channels/"):
            try:
                entry = channel_entry(self.hass, identifier.partition("/")[2])
            except Unresolvable:
                raise BrowseError(
                    translation_domain=DOMAIN, translation_key="channel_unavailable"
                ) from None
            return browse_channels(entry, f"{entry.title} · {labels['channels']}")
        if not identifier and recordings_layout(self.hass) == "receivers":
            return self._folder(
                None,
                self.name,
                [self._folder(f"receiver/{entry.entry_id}", entry.title) for entry in entries],
            )

        kind, _, remainder = identifier.partition("/")
        merged = kind == "merged" or not identifier
        if merged:
            prefix = "merged"
            directory = unquote(remainder) if remainder else "/"
            title = self.name
        elif kind == "receiver":
            entry_id, _, folder_path = remainder.partition("/")
            entries = [entry for entry in entries if entry.entry_id == entry_id]
            if not entries:
                raise BrowseError(
                    translation_domain=DOMAIN, translation_key="recording_unavailable"
                )
            prefix = f"receiver/{entry_id}"
            directory = unquote(folder_path) if folder_path else "/"
            title = entries[0].title
        else:
            raise BrowseError(translation_domain=DOMAIN, translation_key="unknown_recording_folder")

        movies = []
        thumbnails = {}
        for entry in entries:
            snapshot = entry.runtime_data.data
            root = PurePosixPath(snapshot.movie_directory or "/")
            for movie in snapshot.movies or []:
                if not movie.get("serviceref"):
                    continue
                thumbnails[recording_identifier(entry, movie)] = recording_thumbnail(entry, movie)
                path = recording_path(movie)
                # Map each receiver's recording root to the shared virtual root so
                # differing mount paths do not become extra folders in the browser.
                relative = (
                    path.relative_to(root)
                    if path.is_relative_to(root)
                    else path
                    if not path.is_absolute()
                    else PurePosixPath(path.name)
                )
                name = movie.get("eventname") or path.name or labels["recording"]
                movies.append(
                    {
                        **movie,
                        "filename": str(PurePosixPath("/") / relative),
                        "eventname": f"{name} [{entry.title}]" if merged else name,
                        "serviceref": recording_identifier(entry, movie),
                    }
                )

        catalog = browse_recordings(
            Snapshot(ReceiverState(False), movies=movies, movie_directory="/"),
            title,
            "enigma2_directory",
            directory,
            fallback_title=labels["recording"],
        )
        children = []
        for child in catalog.children or ():
            if child.can_expand:
                children.append(
                    self._folder(
                        f"{prefix}/{quote(child.media_content_id, safe='')}",
                        child.title,
                    )
                )
            else:
                children.append(
                    BrowseMediaSource(
                        domain=DOMAIN,
                        identifier=child.media_content_id,
                        title=child.title,
                        media_class=MediaClass.VIDEO,
                        media_content_type="video/mpeg",
                        thumbnail=thumbnails.get(child.media_content_id),
                        can_play=True,
                        can_expand=False,
                    )
                )
        if directory == "/":
            if merged and any(entry.options.get(CONF_SHOW_CHANNELS, False) for entry in entries):
                children.insert(0, self._folder("channels", labels["channels"]))
            elif not merged and entries[0].options.get(CONF_SHOW_CHANNELS, False):
                children.insert(0, channel_folder(entries[0], labels["channels"]))
        return self._folder(identifier or None, catalog.title, children)

    async def async_resolve_media(self, item: MediaSourceItem) -> PlayMedia:
        if (item.identifier or "").startswith("channel/"):
            entry, channel = channel_from_identifier(self.hass, item.identifier)
            if entry.options.get(CONF_EXTERNAL_PLAYBACK, False):
                client = entry.runtime_data.client
                source = (
                    client.base_url.with_scheme(
                        "https" if entry.options.get(CONF_STREAM_HTTPS, False) else "http"
                    )
                    .with_port(entry.options.get(CONF_STREAM_PORT, 8001))
                    .with_path("/" + channel.reference)
                )
                return await entry.runtime_data.media_stream.async_play(source, recording=False)
            raise Unresolvable(
                translation_domain=DOMAIN,
                translation_key="channel_receiver_only",
                translation_placeholders={"receiver": entry.title},
            )
        entry, movie = recording_from_identifier(self.hass, item.identifier)
        if entry.options.get(CONF_EXTERNAL_PLAYBACK, False):
            path = recording_path(movie)
            if not path.is_absolute() or ".." in path.parts or path.suffix.lower() != ".ts":
                raise Unresolvable(
                    translation_domain=DOMAIN, translation_key="stream_recording_format"
                )
            source = entry.runtime_data.client.base_url.with_path("/file").with_query(
                action="download", file=str(path)
            )
            return await entry.runtime_data.media_stream.async_play(source, recording=True)
        # External playback is opt-in; receiver playback keeps its existing routing.
        raise Unresolvable(
            translation_domain=DOMAIN,
            translation_key="recording_receiver_only",
            translation_placeholders={"receiver": entry.title},
        )
