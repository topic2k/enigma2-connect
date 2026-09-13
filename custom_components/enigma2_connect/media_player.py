# SPDX-License-Identifier: Apache-2.0
"""Media controls and a shared bouquet source list."""

from asyncio import sleep
from time import monotonic
from uuid import uuid4

from homeassistant.components.media_player import MediaPlayerEntity, MediaPlayerState, MediaType
from homeassistant.components.media_player import MediaPlayerEntityFeature as Feature
from homeassistant.core import callback
from homeassistant.exceptions import ServiceValidationError

from .api import ReceiverError
from .const import KEYS
from .entity import EnigmaEntity
from .recordings import browse_recordings

PARALLEL_UPDATES = 0


async def async_setup_entry(hass, entry, async_add_entities):
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

    def __init__(self, coordinator):
        super().__init__(coordinator, "media_player")
        self._attr_translation_key = None
        self._screenshot_state = self._current_screenshot_state()
        self._screenshot_generation = uuid4().hex
        self._screenshot_ready_at = monotonic() + 1

    def _current_screenshot_state(self):
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
    def state(self):
        state = self.coordinator.data.state
        return (
            MediaPlayerState.OFF
            if state.standby
            else MediaPlayerState.PLAYING
            if state.reference
            else MediaPlayerState.IDLE
        )

    @property
    def assumed_state(self):
        # OpenWebif's status endpoints do not distinguish playback from pause.
        # HA must offer separate play/pause controls instead of a state toggle.
        return not self.coordinator.data.state.standby

    @property
    def media_title(self):
        return self.coordinator.data.state.title

    @property
    def media_channel(self):
        return self.coordinator.data.state.channel

    @property
    def media_content_id(self):
        return self.coordinator.data.state.reference

    @property
    def media_content_type(self):
        return (
            MediaType.VIDEO if self.coordinator.data.state.recording_playback else MediaType.TVSHOW
        )

    @property
    def extra_state_attributes(self):
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
    def volume_level(self):
        return self.coordinator.data.state.volume

    @property
    def is_volume_muted(self):
        return self.coordinator.data.state.muted

    @property
    def source_list(self):
        return list(self.coordinator.data.channels)

    @property
    def source(self):
        return next(
            (
                label
                for label, item in self.coordinator.data.channels.items()
                if item.reference == self.media_content_id
            ),
            None,
        )

    @property
    def media_image_url(self):
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

    async def async_get_media_image(self):
        if (
            not self.media_content_id
            or self.coordinator.data.state.standby
            or self.coordinator.entry.options.get("artwork") == "none"
        ):
            return None, None
        try:
            if self.coordinator.entry.options.get("artwork") == "screenshot":
                generation = self._screenshot_generation
                if (delay := self._screenshot_ready_at - monotonic()) > 0:
                    await sleep(delay)
                if not self._screenshot_request_current(generation):
                    return None, None
                image = await self.coordinator.client.screenshot()
                if not self._screenshot_request_current(generation):
                    return None, None
                return image, "image/jpeg"
            state = self.coordinator.data.state
            return await self.coordinator.client.picon(
                self.media_content_id, state.channel, state.picon_path
            ), "image/png"
        except ReceiverError:
            return None, None

    def _screenshot_request_current(self, generation):
        return (
            self.available
            and not self.coordinator.data.state.standby
            and self.coordinator.entry.options.get("artwork") == "screenshot"
            and self._screenshot_generation == generation
            and self._current_screenshot_state() == self._screenshot_state
        )

    async def command(self, endpoint, **params):
        await self.coordinator.perform(self.coordinator.client.command, endpoint, **params)

    async def key(self, name):
        await self.coordinator.perform(self.coordinator.client.keys, [KEYS[name]])

    async def async_turn_on(self):
        await self.command("powerstate", newstate=4)

    async def async_turn_off(self):
        deep = self.coordinator.entry.options.get("off_mode") == "deep_standby"
        await self.coordinator.perform(
            self.coordinator.client.command,
            "powerstate",
            newstate=1 if deep else 5,
            refresh=not deep,
        )

    async def async_set_volume_level(self, volume):
        await self.command("vol", set=f"set{round(max(0, min(1, volume)) * 100)}")

    async def async_mute_volume(self, mute):
        await self.coordinator.perform(self.coordinator.client.set_mute, mute)

    async def async_volume_up(self):
        await self.key("volume_up")

    async def async_volume_down(self):
        await self.key("volume_down")

    async def async_media_play(self):
        await self.key("play")

    async def async_media_pause(self):
        await self.key("pause")

    async def async_media_stop(self):
        await self.key("stop")

    async def async_media_next_track(self):
        await self.key("channel_up")

    async def async_media_previous_track(self):
        await self.key("channel_down")

    async def async_select_source(self, source):
        if source not in self.coordinator.data.channels:
            raise ServiceValidationError("Unknown channel")
        await self.command("zap", sRef=self.coordinator.data.channels[source].reference)

    async def async_play_media(self, media_type, media_id, **kwargs):
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
            raise ServiceValidationError("Use a channel number or an Enigma2 service reference")

    async def async_browse_media(self, media_content_type=None, media_content_id=None):
        return browse_recordings(
            self.coordinator.data,
            self.coordinator.entry.title,
            media_content_type,
            media_content_id,
        )
