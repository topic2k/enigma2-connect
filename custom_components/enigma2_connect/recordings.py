# SPDX-License-Identifier: Apache-2.0
"""Recording titles and directory navigation for the HA media browser."""

from pathlib import PurePosixPath

from homeassistant.components.media_player import BrowseMedia, MediaClass
from homeassistant.components.media_player.errors import BrowseError
from homeassistant.helpers.translation import async_get_translations
from homeassistant.util import dt as dt_util

from .const import DOMAIN


async def async_recording_labels(hass):
    """Media browser titles follow the Home Assistant server language."""
    translations = await async_get_translations(hass, hass.config.language, "common", {DOMAIN})
    return {
        key: translations.get(f"component.{DOMAIN}.common.{key}", fallback)
        for key, fallback in {
            "recordings": "Enigma2 recordings",
            "recording": "Recording",
            "channels": "Channels",
        }.items()
    }


def recording_path(movie):
    """Keep receiver paths independent of the host OS and service IDs unchanged."""
    filename = movie.get("filename")
    if not filename:
        filename = movie["serviceref"].split(":", 10)[-1]
    return PurePosixPath(filename)


def recording_title(movie, fallback_title="Recording"):
    """HA has no subtitle field; include available details in the display title."""
    parts = [movie.get("eventname") or recording_path(movie).name or fallback_title]
    try:
        timestamp = float(movie.get("recordingtime"))
        if timestamp > 0:
            recorded = dt_util.as_local(dt_util.utc_from_timestamp(timestamp))
            parts.append(recorded.strftime("%d.%m.%Y %H:%M"))
    except TypeError, ValueError, OverflowError, OSError:
        pass
    if movie.get("servicename"):
        parts.append(movie["servicename"])
    # OpenWebif's length is minutes:seconds, including minutes greater than 59.
    length = str(movie.get("length", "")).split(":")
    if len(length) == 2 and all(part.isascii() and part.isdigit() for part in length):
        minutes, seconds = map(int, length)
        if seconds < 60 and (minutes or seconds):
            hours, minutes = divmod(minutes, 60)
            parts.append(f"{hours} h {minutes:02d} min" if hours else f"{minutes} min")
    return " · ".join(parts)


def browse_recordings(
    snapshot, title, media_type=None, media_id=None, *, fallback_title="Recording", thumbnails=None
):
    """Build one folder level from the shared recursive recording catalog."""
    movies = [movie for movie in snapshot.movies or [] if movie.get("serviceref")]
    # Older replies without directory metadata retain absolute folder structure.
    root = PurePosixPath(snapshot.movie_directory or "/")
    folders = {root}
    entries = []
    for movie in movies:
        path = recording_path(movie)
        parent = path.parent if path.is_absolute() else root / path.parent
        if not parent.is_relative_to(root):
            # Keep unexpected/missing paths playable at the library root.
            parent = root
        entries.append((parent, movie))
        folders.add(parent)
        folders.update(folder for folder in parent.parents if folder.is_relative_to(root))

    if media_type in (None, "enigma2_library") and media_id in (None, "", "root"):
        current = root
    elif media_type == "enigma2_directory" and media_id:
        current = PurePosixPath(media_id)
        if current not in folders:
            raise BrowseError(translation_domain=DOMAIN, translation_key="recording_folder_missing")
    else:
        raise BrowseError(translation_domain=DOMAIN, translation_key="unknown_recording_folder")

    children = [
        BrowseMedia(
            title=folder.name,
            media_class=MediaClass.DIRECTORY,
            media_content_type="enigma2_directory",
            media_content_id=str(folder),
            can_play=False,
            can_expand=True,
        )
        for folder in sorted(folders, key=lambda folder: str(folder).casefold())
        if folder != current and folder.parent == current
    ]
    children.extend(
        BrowseMedia(
            title=recording_title(movie, fallback_title),
            media_class=MediaClass.VIDEO,
            media_content_type="enigma2_recording",
            media_content_id=movie["serviceref"],
            thumbnail=(thumbnails or {}).get(movie["serviceref"]),
            can_play=True,
            can_expand=False,
        )
        for parent, movie in entries
        if parent == current
    )
    return BrowseMedia(
        title=title if current == root else current.name,
        media_class=MediaClass.DIRECTORY,
        media_content_type="enigma2_library" if current == root else "enigma2_directory",
        media_content_id="root" if current == root else str(current),
        can_play=False,
        can_expand=True,
        children=children,
    )
