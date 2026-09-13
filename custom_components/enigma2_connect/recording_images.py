# SPDX-License-Identifier: Apache-2.0
"""Recording artwork with throttled preparation and a bounded private cache."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal, overload

if TYPE_CHECKING:
    from collections.abc import Mapping
    from typing import Any

    from homeassistant.core import HomeAssistant

    from .coordinator import EnigmaConfigEntry, EnigmaCoordinator
    from .models import JsonObject, Snapshot

import asyncio
import json
from collections import OrderedDict
from contextlib import suppress
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from shutil import which
from string import Formatter
from time import time
from urllib.parse import quote

import aiohttp
from aiohttp import web
from homeassistant.config_entries import ConfigEntryState
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.http import HomeAssistantView
from PIL import Image, UnidentifiedImageError
from yarl import URL

from .const import DOMAIN
from .models import boolean, number
from .recording_snapshot import extract_snapshot, recording_duration, snapshot_position
from .recordings import recording_path

CONF_IMAGE_SOURCES = "recording_image_sources"
CONF_SNAPSHOT_MINUTES = "recording_snapshot_minutes"
CONF_TMDB_KEY = "recording_tmdb_key"
CONF_OMDB_KEY = "recording_omdb_key"
CONF_IMAGE_URL = "recording_image_url"
CONF_IMAGE_GENERATION = "recording_image_generation"
IMAGE_SOURCES = ("custom", "tmdb", "omdb", "snapshot")
DEFAULT_IMAGE_SOURCES = ["snapshot"]
MAX_IMAGE_BYTES = 5 * 1024 * 1024
CACHE_LIMIT = 128
CACHE_TTL = 7 * 86400
BACKGROUND_DELAY = 5
FALLBACK = b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 160 90"><rect width="160" height="90" fill="#263238"/><path d="M62 25v40l38-20z" fill="#b0bec5"/></svg>'


async def async_check_snapshot_support(hass: HomeAssistant, entry: EnigmaConfigEntry) -> None:
    """Report a missing decoder with concrete recovery steps, without blocking I/O."""
    issue_id = f"{entry.entry_id}_snapshot_binary"
    manager = hass.data.get("ffmpeg")
    binary = manager.binary if manager else "ffmpeg"
    if "snapshot" in entry.options.get(CONF_IMAGE_SOURCES, DEFAULT_IMAGE_SOURCES) and not (
        await hass.async_add_executor_job(which, binary)
    ):
        ir.async_create_issue(
            hass,
            DOMAIN,
            issue_id,
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key="snapshot_binary",
            translation_placeholders={"receiver": entry.title},
        )
    else:
        ir.async_delete_issue(hass, DOMAIN, issue_id)


def custom_image_url(template: str, movie: JsonObject) -> URL:
    """Expand encoded values, never interpret a URL as code or expose receiver paths."""
    values = {
        "title": movie.get("eventname") or recording_path(movie).stem,
        "filename": recording_path(movie).name,
        "channel": movie.get("servicename") or "",
    }
    for _, field, spec, conversion in Formatter().parse(template):
        if field is not None and (field not in values or spec or conversion):
            raise ValueError("Unsupported URL placeholder")
    result = URL(
        template.format(**{key: quote(str(value), safe="") for key, value in values.items()})
    )
    if result.scheme not in ("http", "https") or not result.host or result.user is not None:
        raise ValueError("Expected an HTTP(S) URL without user credentials")
    return result


def image_version(entry: EnigmaConfigEntry, movie: JsonObject) -> str:
    settings = {
        key: entry.options.get(key, default)
        for key, default in (
            (CONF_IMAGE_SOURCES, DEFAULT_IMAGE_SOURCES),
            (CONF_SNAPSHOT_MINUTES, 10),
            (CONF_TMDB_KEY, ""),
            (CONF_OMDB_KEY, ""),
            (CONF_IMAGE_URL, ""),
        )
    }
    if generation := entry.options.get(CONF_IMAGE_GENERATION):
        settings[CONF_IMAGE_GENERATION] = generation
    # HA's number selector returns floats, including an unchanged default of 10.
    minutes = float(settings[CONF_SNAPSHOT_MINUTES])
    settings[CONF_SNAPSHOT_MINUTES] = int(minutes) if minutes.is_integer() else minutes
    metadata = [movie.get(key) for key in ("eventname", "servicename", "recordingtime")]
    if "snapshot" in settings[CONF_IMAGE_SOURCES]:
        # A growing recording must get a new frame once the requested position exists.
        metadata.append(snapshot_position(movie, settings[CONF_SNAPSHOT_MINUTES]))
    return sha256(json.dumps([settings, metadata], sort_keys=True).encode()).hexdigest()[:24]


def recording_thumbnail(entry: EnigmaConfigEntry, movie: JsonObject) -> str | None:
    if not entry.options.get(CONF_IMAGE_SOURCES, DEFAULT_IMAGE_SOURCES):
        return None
    digest = sha256(movie["serviceref"].encode()).hexdigest()
    return (
        f"/api/{DOMAIN}/recording_thumbnail/{entry.entry_id}/{digest}/{image_version(entry, movie)}"
    )


def validate_image_options(options: Mapping[str, Any]) -> dict[str, str]:
    errors = {}
    selected = options.get(CONF_IMAGE_SOURCES, DEFAULT_IMAGE_SOURCES)
    for source, field in (("tmdb", CONF_TMDB_KEY), ("omdb", CONF_OMDB_KEY)):
        if source in selected and not options.get(field, "").strip():
            errors[field] = "image_api_key_required"
    if "custom" in selected:
        try:
            custom_image_url(
                options.get(CONF_IMAGE_URL, ""),
                {
                    "filename": "recording.ts",
                    "eventname": "Recording",
                },
            )
        except ValueError, KeyError:
            errors[CONF_IMAGE_URL] = "invalid_image_url"
    return errors


def normalize_image(content: bytes) -> bytes:
    """Bound decoded dimensions and store only small JPEGs, never remote active content."""
    with Image.open(BytesIO(content)) as image:
        if image.format not in ("JPEG", "PNG", "WEBP") or image.width * image.height > 20_000_000:
            raise ValueError("Unsupported or oversized image")
        image.thumbnail((640, 640))
        output = BytesIO()
        image.convert("RGB").save(output, "JPEG", quality=85)
        return output.getvalue()


class RecordingImages:
    def __init__(self, hass: HomeAssistant, coordinator: EnigmaCoordinator) -> None:
        self.hass = hass
        self.coordinator = coordinator
        self.cache = Path(
            hass.config.path(".storage", f"{DOMAIN}_thumbnails", coordinator.entry.entry_id)
        )
        self._pending: dict[str, asyncio.Task[bytes | None]] = {}
        self._failed: OrderedDict[str, float] = OrderedDict()
        self._lock = asyncio.Lock()
        self._queue: OrderedDict[str, JsonObject] = OrderedDict()
        self._prepared: dict[str, float] = {}
        self._worker: asyncio.Task[None] | None = None
        self._started = False
        self._closed = False
        self._snapshot: Snapshot | None = None

    def _image_key(self, movie: JsonObject) -> str:
        digest = sha256(movie["serviceref"].encode()).hexdigest()
        return f"{digest}-{image_version(self.coordinator.entry, movie)}"

    def _snapshot_ready(self, movie: JsonObject) -> bool:
        """Do not repeatedly extract midpoint frames from a still-growing recording."""
        snapshot = self._snapshot
        if snapshot is None:
            return True
        position = float(self.coordinator.entry.options.get(CONF_SNAPSHOT_MINUTES, 10)) * 60
        length = recording_duration(movie)
        path = str(recording_path(movie))
        running = any(
            number(timer.get("state")) == 2
            and boolean(timer.get("justplay")) is not True
            and timer.get("filename")
            and path in (timer["filename"], f"{timer['filename']}.ts")
            for timer in snapshot.timers or []
            if isinstance(timer, dict)
        )
        start = number(movie.get("recordingtime")) or 0
        age = time() - start if start > 0 else None
        # Some images omit timer filenames. Conservatively defer recent short files
        # while the receiver is recording or its recording state is unknown.
        if snapshot.state.recording is not False and age is not None:
            running |= age < max(position, length or 0) + 120
        # A newly created file may report its planned duration before data exists.
        if age is not None and age <= position + 5 and (length is None or length > age + 5):
            return False
        if running:
            return (
                length > position if length is not None else age is not None and age > position + 5
            )
        return True

    def async_start(self) -> None:
        """Start after platform setup; never hold integration startup for artwork."""
        self._started = True
        self.async_catalog_updated(self.coordinator.data)

    def async_catalog_updated(self, snapshot: Snapshot) -> None:
        """Reconcile on existing catalog polls, including unchanged lists and expiry."""
        self._snapshot = snapshot
        options = self.coordinator.entry.options
        sources = options.get(CONF_IMAGE_SOURCES, DEFAULT_IMAGE_SOURCES)
        if self._closed or not self._started:
            return
        if not sources or snapshot.movies is None:
            self._queue.clear()
            return
        # Warm only what fits in the cache: otherwise large catalogs would evict
        # and regenerate each other forever. Older items remain available on demand.
        movies = sorted(
            (
                movie
                for movie in snapshot.movies
                if isinstance(movie, dict)
                and isinstance(movie.get("serviceref"), str)
                and movie["serviceref"]
                and (not movie.get("filename") or isinstance(movie["filename"], str))
            ),
            key=lambda movie: (number(movie.get("recordingtime")) or 0, movie["serviceref"]),
            reverse=True,
        )[:CACHE_LIMIT]
        candidates = {self._image_key(movie): movie for movie in movies}
        self._prepared = {
            key: until
            for key, until in self._prepared.items()
            if key in candidates and until > time()
        }
        self._queue = OrderedDict(
            (key, movie)
            for key, movie in candidates.items()
            if key not in self._prepared
            and (sources != ["snapshot"] or self._snapshot_ready(movie))
        )
        if self._queue and self._worker is None:
            self._worker = self.hass.async_create_background_task(
                self._prepare_catalog(), f"{DOMAIN} prepare recording artwork", eager_start=False
            )

    def _cache_index(self) -> dict[str, float]:
        try:
            return {
                file.stem: file.stat().st_mtime + CACHE_TTL for file in self.cache.glob("*.jpg")
            }
        except OSError:
            return {}

    async def _prepare_catalog(self) -> None:
        try:
            cached = await self.hass.async_add_executor_job(self._cache_index)
            self._prepared.update(
                {
                    key: until
                    for key, until in cached.items()
                    if key in self._queue and until > time()
                }
            )
            while self._queue and not self._closed:
                self._queue = OrderedDict(
                    (key, movie)
                    for key, movie in self._queue.items()
                    if self._prepared.get(key, 0) <= time()
                )
                if not self._queue:
                    break
                await asyncio.sleep(BACKGROUND_DELAY)
                if not self.coordinator.last_update_success:
                    return
                if self._pending:
                    continue  # Let foreground requests finish before starting another image.
                if not self._queue:
                    continue
                key, movie = self._queue.popitem(last=False)
                if await self.async_image(movie):
                    self._prepared[key] = time() + CACHE_TTL
                else:
                    self._prepared[key] = time() + 120
        finally:
            self._worker = None

    def _read_cache(self, key: str) -> bytes | None:
        path = self.cache / f"{key}.jpg"
        try:
            if time() - path.stat().st_mtime < CACHE_TTL:
                return path.read_bytes()
        except OSError:
            pass
        return None

    def _write_cache(self, key: str, content: bytes) -> None:
        self.cache.mkdir(parents=True, exist_ok=True)
        path = self.cache / f"{key}.jpg"
        temporary = path.with_suffix(".tmp")
        temporary.write_bytes(content)
        temporary.replace(path)
        files = sorted(
            self.cache.glob("*.jpg"), key=lambda file: file.stat().st_mtime, reverse=True
        )
        for file in files[CACHE_LIMIT:]:
            file.unlink(missing_ok=True)

    async def async_close(self) -> None:
        self._closed = True
        self._queue.clear()
        worker = self._worker
        if worker:
            worker.cancel()
        for task in self._pending.values():
            task.cancel()
        await asyncio.gather(
            *([worker] if worker else []), *list(self._pending.values()), return_exceptions=True
        )

    async def async_image(self, movie: JsonObject) -> bytes | None:
        entry = self.coordinator.entry
        if self._closed or not entry.options.get(CONF_IMAGE_SOURCES, DEFAULT_IMAGE_SOURCES):
            return None
        key = self._image_key(movie)
        if self._failed.get(key, 0) > time():
            return None
        if key not in self._pending:
            if len(self._pending) >= 32:
                return None
            self._pending[key] = self.hass.async_create_background_task(
                self._generate(key, movie), f"{DOMAIN} recording artwork"
            )
            self._pending[key].add_done_callback(lambda task: self._pending.pop(key, None))
        task = self._pending[key]
        return await asyncio.shield(task)

    async def _generate(self, key: str, movie: JsonObject) -> bytes | None:
        if cached := await self.hass.async_add_executor_job(self._read_cache, key):
            return cached
        async with self._lock:
            options = self.coordinator.entry.options
            enabled = options.get(CONF_IMAGE_SOURCES, DEFAULT_IMAGE_SOURCES)
            for source in IMAGE_SOURCES:
                if source not in enabled:
                    continue
                try:
                    content = await self._from_source(source, movie, options)
                    if content:
                        image = await self.hass.async_add_executor_job(normalize_image, content)
                        with suppress(OSError):
                            await self.hass.async_add_executor_job(self._write_cache, key, image)
                        return image
                except (
                    aiohttp.ClientError,
                    OSError,
                    TimeoutError,
                    ValueError,
                    UnidentifiedImageError,
                    Image.DecompressionBombError,
                ):
                    # Remote errors can contain URLs or API keys; never log them.
                    continue
            self._failed[key] = time() + 120
            while len(self._failed) > CACHE_LIMIT:
                self._failed.popitem(last=False)
        return None

    @overload
    async def _fetch(
        self,
        url: str | URL,
        *,
        params: dict[str, Any] | None = None,
        json_response: Literal[False] = False,
    ) -> bytes: ...

    @overload
    async def _fetch(
        self,
        url: str | URL,
        *,
        params: dict[str, Any] | None = None,
        json_response: Literal[True],
    ) -> Any: ...

    async def _fetch(
        self, url: str | URL, *, params: dict[str, Any] | None = None, json_response: bool = False
    ) -> Any:
        url = URL(url)
        if url.scheme not in ("https", "http") or not url.host or url.user is not None:
            raise ValueError("Unsupported image URL")
        # This session never receives the receiver's Authorization header.
        session = async_get_clientsession(self.hass)
        async with session.get(
            url, params=params, timeout=aiohttp.ClientTimeout(total=15), allow_redirects=False
        ) as response:
            response.raise_for_status()
            if response.status != 200:
                raise ValueError("Image source did not return data")
            content = bytearray()
            async for chunk in response.content.iter_chunked(64 * 1024):
                content.extend(chunk)
                if len(content) > MAX_IMAGE_BYTES:
                    raise ValueError("Image response too large")
            return json.loads(content) if json_response else bytes(content)

    async def _from_source(
        self, source: str, movie: JsonObject, options: Mapping[str, Any]
    ) -> bytes | None:
        title = movie.get("eventname") or recording_path(movie).stem
        if source == "custom":
            return await self._fetch(custom_image_url(options.get(CONF_IMAGE_URL, ""), movie))
        if source == "tmdb" and options.get(CONF_TMDB_KEY):
            result = await self._fetch(
                "https://api.themoviedb.org/3/search/multi",
                params={
                    "api_key": options[CONF_TMDB_KEY],
                    "query": title,
                    "language": self.hass.config.language,
                    "include_adult": "false",
                },
                json_response=True,
            )
            if isinstance(result, dict):
                matches = result.get("results")
                for match in matches if isinstance(matches, list) else []:
                    if not isinstance(match, dict) or match.get("media_type") not in (
                        "movie",
                        "tv",
                    ):
                        continue
                    poster = match.get("poster_path")
                    if isinstance(poster, str) and poster.startswith("/") and ".." not in poster:
                        return await self._fetch(f"https://image.tmdb.org/t/p/w500{poster}")
        if source == "omdb" and options.get(CONF_OMDB_KEY):
            result = await self._fetch(
                "https://www.omdbapi.com/",
                params={
                    "apikey": options[CONF_OMDB_KEY],
                    "t": title,
                },
                json_response=True,
            )
            if isinstance(result, dict) and result.get("Response") == "True":
                poster = result.get("Poster")
                if (
                    isinstance(poster, str)
                    and URL(poster).scheme == "https"
                    and URL(poster).host
                    in ("m.media-amazon.com", "ia.media-imdb.com", "img.omdbapi.com")
                ):
                    return await self._fetch(poster)
        if (
            source == "snapshot"
            and self.coordinator.last_update_success
            and self._snapshot_ready(movie)
        ):
            manager = self.hass.data.get("ffmpeg")
            return await extract_snapshot(
                self.coordinator.client,
                movie,
                options.get(CONF_SNAPSHOT_MINUTES, 10),
                manager.binary if manager else "ffmpeg",
            )
        return None


class RecordingThumbnailView(HomeAssistantView):
    url = f"/api/{DOMAIN}/recording_thumbnail/{{entry_id}}/{{digest}}/{{version}}"
    name = f"api:{DOMAIN}:recording_thumbnail"
    requires_auth = True

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    async def get(
        self, request: web.Request, entry_id: str, digest: str, version: str
    ) -> web.Response:
        entry: EnigmaConfigEntry | None = self.hass.config_entries.async_get_entry(entry_id)
        if not entry or entry.domain != DOMAIN or entry.state is not ConfigEntryState.LOADED:
            raise web.HTTPNotFound()
        coordinator = entry.runtime_data
        for movie in coordinator.data.movies or []:
            if (
                movie.get("serviceref")
                and sha256(movie["serviceref"].encode()).hexdigest() == digest
            ):
                if version != image_version(entry, movie):
                    raise web.HTTPNotFound()
                if content := await coordinator.recording_images.async_image(movie):
                    return web.Response(
                        body=content,
                        content_type="image/jpeg",
                        headers={"Cache-Control": "private, max-age=86400"},
                    )
                return web.Response(
                    body=FALLBACK,
                    content_type="image/svg+xml",
                    headers={"Cache-Control": "no-store"},
                )
        raise web.HTTPNotFound()
