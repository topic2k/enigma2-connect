# SPDX-License-Identifier: Apache-2.0
"""Shared polling, catalog ownership and action error handling."""

from __future__ import annotations

import logging
from dataclasses import replace
from datetime import timedelta
from time import monotonic

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import AuthenticationError, OpenWebifClient, PowerCommandUnconfirmed, ReceiverError
from .const import CATALOG_INTERVAL, DOMAIN, SLOW_INTERVAL
from .models import ReceiverState, Snapshot, services

_LOGGER = logging.getLogger(__name__)


class EnigmaCoordinator(DataUpdateCoordinator[Snapshot]):
    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, client: OpenWebifClient, interval: int
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
        self.info: dict = {}
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
            raise ConfigEntryAuthFailed("Receiver authentication failed") from err
        except (ReceiverError, KeyError, ValueError) as err:
            raise UpdateFailed("Cannot identify OpenWebif receiver") from err

    async def optional(self, endpoint: str, field: str | None = None, **params):
        error_key = (
            f"{endpoint}_{params['stype']}"
            if endpoint == "bouquets" and "stype" in params
            else endpoint
        )
        try:
            result = await self.client.get(endpoint, **params)
            value = result[field] if field else result
            if field and not isinstance(value, list):
                raise ValueError("Expected list")
        except AuthenticationError:
            raise
        except ReceiverError, KeyError, ValueError:
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
                timers, movies = previous.timers, previous.movies
                movie_directory = previous.movie_directory
                if monotonic() >= self._slow_due:
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
                if monotonic() >= self._catalog_due:
                    tv = await self.optional("bouquets", "bouquets", stype="tv")
                    radio = await self.optional("bouquets", "bouquets", stype="radio")
                    bouquets = services([*(tv or []), *(radio or [])])
                    refs = {item.reference for item in bouquets.values()}
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
                    self._catalog_due = monotonic() + CATALOG_INTERVAL
                return Snapshot(
                    state,
                    signal,
                    self.info,
                    timers,
                    movies,
                    bouquets,
                    channels,
                    self._bouquet,
                    movie_directory,
                )
            except AuthenticationError as err:
                raise ConfigEntryAuthFailed("Receiver authentication failed") from err
            except (ReceiverError, ValueError, TypeError) as err:
                raise UpdateFailed("Cannot update receiver") from err

    async def perform(self, method, *args, refresh: bool = True, **kwargs) -> None:
        try:
            await method(*args, **kwargs)
        except AuthenticationError as err:
            self.entry.async_start_reauth(self.hass)
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="invalid_auth"
            ) from err
        except PowerCommandUnconfirmed as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="power_unconfirmed"
            ) from err
        except ReceiverError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="request_failed"
            ) from err
        if refresh:
            await self.async_request_refresh()

    async def select_bouquet(self, reference: str) -> None:
        async def change():
            async with self.data_lock:
                result = await self.client.get("getservices", sRef=reference)
                channels = services(result.get("services", []), channels=True)
                self._bouquet = reference
                self.async_set_updated_data(
                    replace(self.data, bouquet=reference, channels=channels)
                )

        await self.perform(change, refresh=False)

    def invalidate_lists(self) -> None:
        self._slow_due = self._catalog_due = 0


type EnigmaConfigEntry = ConfigEntry[EnigmaCoordinator]
