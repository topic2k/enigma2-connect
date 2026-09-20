# SPDX-License-Identifier: Apache-2.0
"""Shared polling, catalog ownership and action error handling."""

from __future__ import annotations

from typing import TYPE_CHECKING, overload

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable
    from typing import Any

import logging
from dataclasses import replace
from datetime import timedelta
from time import monotonic

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    AuthenticationError,
    CommandUnconfirmed,
    OpenWebifClient,
    PowerCommandUnconfirmed,
    ReceiverError,
)
from .channel_media import CONF_CHANNEL_BOUQUET, CONF_SHOW_CHANNELS
from .const import CATALOG_INTERVAL, DOMAIN, SLOW_INTERVAL
from .media_stream import MediaStream
from .models import JsonObject, ReceiverState, Snapshot, services
from .recording_images import RecordingImages

_LOGGER = logging.getLogger(__name__)


class EnigmaCoordinator(DataUpdateCoordinator[Snapshot]):
    def __init__(
        self, hass: HomeAssistant, entry: EnigmaConfigEntry, client: OpenWebifClient, interval: int
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            config_entry=entry,
            update_interval=timedelta(seconds=interval),
            always_update=False,
        )
        self.client = client
        self.entry = entry
        self.recording_images = RecordingImages(hass, self)
        self.media_stream = MediaStream(hass, self)
        self.info: dict[str, Any] = {}
        self._slow_due = 0.0
        self._catalog_due = 0.0
        self._bouquet = entry.options.get("bouquet")
        self.optional_errors: set[str] = set()
        # Serialize catalog selection with polls so an old poll cannot overwrite it.
        import asyncio

        self.data_lock = asyncio.Lock()

    async def _async_setup(self) -> None:
        try:
            data = await self.client.get("about")
            self.info = data["info"]
            if not isinstance(self.info, dict) or not self.info.get("model"):
                raise ValueError("Missing receiver model")
        except AuthenticationError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN, translation_key="invalid_auth"
            ) from err
        except (ReceiverError, KeyError, ValueError) as err:
            raise UpdateFailed(
                translation_domain=DOMAIN, translation_key="cannot_identify"
            ) from err

    @overload
    async def optional(
        self, endpoint: str, field: None = None, **params: Any
    ) -> JsonObject | None: ...

    @overload
    async def optional(self, endpoint: str, field: str, **params: Any) -> list[Any] | None: ...

    async def optional(
        self, endpoint: str, field: str | None = None, **params: Any
    ) -> JsonObject | list[Any] | None:
        error_key = (
            f"{endpoint}_{params['stype']}"
            if endpoint == "bouquets" and "stype" in params
            else endpoint
        )
        try:
            result = await self.client.get(endpoint, **params)
            value: JsonObject | list[Any] = result[field] if field else result
            if field and not isinstance(value, list):
                raise ValueError("Expected list")
        except AuthenticationError:
            # Authentication failures require reauth, even on optional endpoints.
            raise
        except ReceiverError, KeyError, ValueError:
            # Missing optional data must not make the entire receiver unavailable.
            self.optional_errors.add(error_key)
            return None
        self.optional_errors.discard(error_key)
        return value

    async def _async_update_data(self) -> Snapshot:
        async with self.data_lock:
            try:
                raw = await self.client.get("statusinfo")
                state = ReceiverState.parse(raw)
                signal = current = None
                if not state.standby:
                    signal = await self.optional("signal")
                    current = await self.optional("getcurrent")
                state = ReceiverState.parse(raw, current)
                previous = self.data if self.data else Snapshot(state)
                # Reuse slow-changing lists between their own refresh deadlines.
                # A failed list refresh replaces old data with None, not an empty list.
                timers, movies = previous.timers, previous.movies
                movie_directory = previous.movie_directory
                catalog_refreshed = monotonic() >= self._slow_due
                if catalog_refreshed:
                    timers = await self.optional("timerlist", "timers")
                    catalog = await self.optional("movielist", recursive=1)
                    movies = catalog.get("movies") if isinstance(catalog, dict) else None
                    movie_directory = (
                        catalog.get("directory") if isinstance(catalog, dict) else None
                    )
                    if not isinstance(movies, list):
                        movies = None
                        self.optional_errors.add("movielist")
                    if not isinstance(movie_directory, str):
                        movie_directory = None
                    self._slow_due = monotonic() + SLOW_INTERVAL
                bouquets, channels = previous.bouquets, previous.channels
                media_channels = previous.media_channels
                if monotonic() >= self._catalog_due:
                    tv = await self.optional("bouquets", "bouquets", stype="tv")
                    radio = await self.optional("bouquets", "bouquets", stype="radio")
                    bouquets = services([*(tv or []), *(radio or [])])
                    refs = {item.reference for item in bouquets.values()}
                    # A configured reference may be absent from the bouquet listing;
                    # retain it so manually entered bouquets can still be queried.
                    if not self._bouquet or (
                        self._bouquet not in refs
                        and self._bouquet != self.entry.options.get("bouquet")
                    ):
                        self._bouquet = (
                            next(iter(refs))
                            if len(refs) == 1
                            else next((s.reference for s in bouquets.values()), None)
                        )
                    rows = (
                        await self.optional("getservices", "services", sRef=self._bouquet)
                        if self._bouquet
                        else []
                    )
                    channels = services(rows or [], channels=True)
                    media_channels = None
                    if self.entry.options.get(CONF_SHOW_CHANNELS, False):
                        media_bouquet = (
                            self.entry.options.get(CONF_CHANNEL_BOUQUET) or self._bouquet
                        )
                        if media_bouquet == self._bouquet:
                            media_channels = channels
                        elif media_bouquet:
                            media_rows = await self.optional(
                                "getservices", "services", sRef=media_bouquet
                            )
                            media_channels = (
                                services(media_rows, channels=True)
                                if media_rows is not None
                                else None
                            )
                    self._catalog_due = monotonic() + CATALOG_INTERVAL
                snapshot = Snapshot(
                    state,
                    signal,
                    self.info,
                    timers,
                    movies,
                    bouquets,
                    channels,
                    self._bouquet,
                    movie_directory,
                    media_channels,
                )
                if catalog_refreshed:
                    self.recording_images.async_catalog_updated(snapshot)
                return snapshot
            except AuthenticationError as err:
                raise ConfigEntryAuthFailed(
                    translation_domain=DOMAIN, translation_key="invalid_auth"
                ) from err
            except (ReceiverError, ValueError, TypeError) as err:
                raise UpdateFailed(
                    translation_domain=DOMAIN, translation_key="cannot_update"
                ) from err

    async def perform[T](
        self, method: Callable[..., Awaitable[T]], *args: Any, refresh: bool = True, **kwargs: Any
    ) -> T:
        try:
            result = await method(*args, **kwargs)
        except AuthenticationError as err:
            self.entry.async_start_reauth(self.hass)
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="invalid_auth"
            ) from err
        except PowerCommandUnconfirmed as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="power_unconfirmed"
            ) from err
        except CommandUnconfirmed as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="timer_unconfirmed"
            ) from err
        except ReceiverError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="request_failed"
            ) from err
        if refresh:
            await self.async_request_refresh()
        return result

    async def select_bouquet(self, reference: str) -> None:
        async def change() -> None:
            async with self.data_lock:
                result = await self.client.get("getservices", sRef=reference)
                channels = services(result.get("services", []), channels=True)
                # Publish selection and channels together only after a successful fetch.
                self._bouquet = reference
                self.async_set_updated_data(
                    replace(
                        self.data,
                        bouquet=reference,
                        channels=channels,
                        media_channels=channels
                        if self.entry.options.get(CONF_SHOW_CHANNELS, False)
                        and not self.entry.options.get(CONF_CHANNEL_BOUQUET)
                        else self.data.media_channels,
                    )
                )

        await self.perform(change, refresh=False)

    def invalidate_lists(self) -> None:
        self._slow_due = self._catalog_due = 0


type EnigmaConfigEntry = ConfigEntry[EnigmaCoordinator]
