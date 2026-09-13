# SPDX-License-Identifier: Apache-2.0
"""Media controls and a shared bouquet source list."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any

    from homeassistant.components.media_player.browse_media import BrowseMedia
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

    from .coordinator import EnigmaConfigEntry, EnigmaCoordinator

from asyncio import sleep
from time import monotonic
from uuid import uuid4

from homeassistant.components import media_source
from homeassistant.components.media_player import MediaPlayerEntity
from homeassistant.components.media_player.const import MediaPlayerEntityFeature as Feature
from homeassistant.components.media_player.const import MediaPlayerState, MediaType
from homeassistant.components.media_player.errors import BrowseError
from homeassistant.core import callback
from homeassistant.exceptions import ServiceValidationError

from .api import ReceiverError
from .channel_media import (
    CONF_SHOW_CHANNELS,
    browse_channels,
    channel_entry,
    channel_folder,
    channel_from_identifier,
)
from .const import DOMAIN, KEYS
from .entity import EnigmaEntity
from .media_source import recording_from_identifier
from .recording_images import recording_thumbnail
from .recordings import async_recording_labels, browse_recordings

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EnigmaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities([EnigmaMediaPlayer(entry.runtime_data)])


class EnigmaMediaPlayer(EnigmaEntity, MediaPlayerEntity):
    _attr_name = None
    _attr_supported_features = (
        Feature.TURN_ON
        | Feature.TURN_OFF
        | Feature.VOLUME_SET
        | Feature.VOLUME_STEP
        | Feature.VOLUME_MUTE
        | Feature.PLAY
        | Feature.PAUSE
        | Feature.STOP
        | Feature.NEXT_TRACK
        | Feature.PREVIOUS_TRACK
        | Feature.PLAY_MEDIA
        | Feature.SELECT_SOURCE
        | Feature.BROWSE_MEDIA
    )

    def __init__(self, coordinator: EnigmaCoordinator) -> None:
        super().__init__(coordinator, "media_player")
        self._attr_translation_key = None
        self._screenshot_state = self._current_screenshot_state()
        self._screenshot_generation = uuid4().hex
        self._screenshot_ready_at = monotonic() + 1

    def _current_screenshot_state(self) -> tuple[str | None, bool]:
        state = self.coordinator.data.state
        return state.reference, state.standby

    @callback
    def _handle_coordinator_update(self) -> None:
        if (state := self._current_screenshot_state()) != self._screenshot_state:
            self._screenshot_state = state
            self._screenshot_generation = uuid4().hex
            self._screenshot_ready_at = monotonic() + 1
        super()._handle_coordinator_update()

    @property
    def state(self) -> MediaPlayerState:
        state = self.coordinator.data.state
        return (
            MediaPlayerState.OFF
            if state.standby
            else MediaPlayerState.PLAYING
            if state.reference
            else MediaPlayerState.IDLE
        )

    @property
    def assumed_state(self) -> bool:
        # OpenWebif's status endpoints do not distinguish playback from pause.
        # HA must offer separate play/pause controls instead of a state toggle.
        return not self.coordinator.data.state.standby

    @property
    def media_title(self) -> str | None:
        return self.coordinator.data.state.title

    @property
    def media_channel(self) -> str | None:
        return self.coordinator.data.state.channel

    @property
    def media_content_id(self) -> str | None:
        return self.coordinator.data.state.reference

    @property
    def media_content_type(self) -> MediaType:
        return (
            MediaType.VIDEO if self.coordinator.data.state.recording_playback else MediaType.TVSHOW
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        state = self.coordinator.data.state
        if state.standby:
            return {}
        return {
            "programme_description": state.description,
            "programme_start": state.programme_start,
            "programme_end": state.programme_end,
            "recording_active": state.recording,
            "recording_playback": state.recording_playback,
        }

    @property
    def volume_level(self) -> float | None:
        return self.coordinator.data.state.volume

    @property
    def is_volume_muted(self) -> bool | None:
        return self.coordinator.data.state.muted

    @property
    def source_list(self) -> list[str]:
        return list(self.coordinator.data.channels)

    @property
    def source(self) -> str | None:
        return next(
            (
                label
                for label, item in self.coordinator.data.channels.items()
                if item.reference == self.media_content_id
            ),
            None,
        )

    @property
    def media_image_url(self) -> str | None:
        # A credential-free cache key; bytes are fetched through the authenticated API.
        if not self.media_content_id or self.coordinator.entry.options.get("artwork") == "none":
            return None
        screenshot = self.coordinator.entry.options.get("artwork") == "screenshot"
        query = {"ref": self.media_content_id}
        if screenshot:
            # Revisiting a channel must not reuse a frame captured during an earlier zap.
            query["generation"] = self._screenshot_generation
        return str(
            self.coordinator.client.base_url.with_path(
                "/grab" if screenshot else "/picon"
            ).with_query(query)
        )

    async def async_get_media_image(self) -> tuple[bytes | None, str | None]:
        if (
            not self.media_content_id
            or self.coordinator.data.state.standby
            or self.coordinator.entry.options.get("artwork") == "none"
        ):
            return None, None
        try:
            if self.coordinator.entry.options.get("artwork") == "screenshot":
                generation = self._screenshot_generation
                # Allow the receiver to render the new channel after a zap.
                if (delay := self._screenshot_ready_at - monotonic()) > 0:
                    await sleep(delay)
                if not self._screenshot_request_current(generation):
                    return None, None
                image = await self.coordinator.client.screenshot()
                # A channel change during the fetch makes this frame obsolete too.
                if not self._screenshot_request_current(generation):
                    return None, None
                return image, "image/jpeg"
            state = self.coordinator.data.state
            return await self.coordinator.client.picon(
                self.media_content_id, state.channel, state.picon_path
            ), "image/png"
        except ReceiverError:
            return None, None

    def _screenshot_request_current(self, generation: str) -> bool:
        return (
            self.available
            and not self.coordinator.data.state.standby
            and self.coordinator.entry.options.get("artwork") == "screenshot"
            and self._screenshot_generation == generation
            and self._current_screenshot_state() == self._screenshot_state
        )

    async def command(self, endpoint: str, **params: Any) -> None:
        await self.coordinator.perform(self.coordinator.client.command, endpoint, **params)

    async def key(self, name: str) -> None:
        await self.coordinator.perform(self.coordinator.client.keys, [KEYS[name]])

    async def async_turn_on(self) -> None:
        await self.command("powerstate", newstate=4)

    async def async_turn_off(self) -> None:
        deep = self.coordinator.entry.options.get("off_mode") == "deep_standby"
        # Deep standby takes the API offline, so an immediate refresh would fail.
        await self.coordinator.perform(
            self.coordinator.client.command,
            "powerstate",
            newstate=1 if deep else 5,
            refresh=not deep,
        )

    async def async_set_volume_level(self, volume: float) -> None:
        await self.command("vol", set=f"set{round(max(0, min(1, volume)) * 100)}")

    async def async_mute_volume(self, mute: bool) -> None:
        await self.coordinator.perform(self.coordinator.client.set_mute, mute)

    async def async_volume_up(self) -> None:
        await self.key("volume_up")

    async def async_volume_down(self) -> None:
        await self.key("volume_down")

    async def async_media_play(self) -> None:
        await self.key("play")

    async def async_media_pause(self) -> None:
        await self.key("pause")

    async def async_media_stop(self) -> None:
        await self.key("stop")

    async def async_media_next_track(self) -> None:
        await self.key("channel_up")

    async def async_media_previous_track(self) -> None:
        await self.key("channel_down")

    async def async_select_source(self, source: str) -> None:
        if source not in self.coordinator.data.channels:
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="unknown_channel"
            )
        await self.command("zap", sRef=self.coordinator.data.channels[source].reference)

    async def async_play_media(self, media_type: str, media_id: str, **kwargs: Any) -> None:
        if media_source.is_media_source_id(media_id):
            item = media_source.MediaSourceItem.from_uri(self.hass, media_id, self.entity_id)
            if item.domain != DOMAIN:
                raise ServiceValidationError(
                    translation_domain=DOMAIN, translation_key="select_recording"
                )
            is_channel = (item.identifier or "").startswith("channel/")
            if is_channel:
                entry, channel = channel_from_identifier(self.hass, item.identifier)
                reference = channel.reference
            else:
                entry, movie = recording_from_identifier(self.hass, item.identifier)
                reference = movie["serviceref"]
            # Service references identify files on the owning receiver's filesystem.
            if entry.entry_id != self.coordinator.entry.entry_id:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="channel_receiver_only"
                    if is_channel
                    else "recording_receiver_only",
                    translation_placeholders={"receiver": entry.title},
                )
            await self.command("zap", sRef=reference)
            return
        if (
            media_type == MediaType.CHANNEL
            and media_id.isascii()
            and media_id.isdigit()
            and 0 < int(media_id)
            and len(media_id) <= 5
        ):
            await self.coordinator.perform(
                self.coordinator.client.keys, [KEYS[digit] for digit in media_id] + [KEYS["ok"]]
            )
        elif (
            media_type in (MediaType.CHANNEL, "enigma2_reference", "enigma2_recording")
            and ":" in media_id
        ):
            await self.command("zap", sRef=media_id)
        else:
            raise ServiceValidationError(translation_domain=DOMAIN, translation_key="invalid_media")

    async def async_browse_media(
        self, media_content_type: str | None = None, media_content_id: str | None = None
    ) -> BrowseMedia:
        if media_content_id and media_source.is_media_source_id(media_content_id):
            item = media_source.MediaSourceItem.from_uri(
                self.hass, media_content_id, self.entity_id
            )
            if item.domain == DOMAIN and (item.identifier or "").startswith("channels/"):
                try:
                    entry = channel_entry(self.hass, item.identifier.partition("/")[2])
                except media_source.Unresolvable:
                    raise BrowseError(
                        translation_domain=DOMAIN, translation_key="channel_unavailable"
                    ) from None
                labels = await async_recording_labels(self.hass)
                return browse_channels(entry, f"{entry.title} · {labels['channels']}")
            return await media_source.async_browse_media(self.hass, media_content_id)
        labels = await async_recording_labels(self.hass)
        result = browse_recordings(
            self.coordinator.data,
            self.coordinator.entry.title,
            media_content_type,
            media_content_id,
            fallback_title=labels["recording"],
            thumbnails={
                movie["serviceref"]: recording_thumbnail(self.coordinator.entry, movie)
                for movie in self.coordinator.data.movies or []
                if movie.get("serviceref")
            },
        )
        if result.media_content_id == "root" and self.coordinator.entry.options.get(
            CONF_SHOW_CHANNELS, False
        ):
            result.children = [
                channel_folder(self.coordinator.entry, labels["channels"]),
                *(result.children or ()),
            ]
        return result
