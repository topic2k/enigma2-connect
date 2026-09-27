# SPDX-License-Identifier: Apache-2.0
"""Validate and select receiver audio tracks without optimistic state."""

from .api import (
    AuthenticationError,
    CommandUnconfirmed,
    OpenWebifClient,
    ReceiverError,
    command_response,
)
from .models import AudioTrack, JsonObject, ReceiverState, boolean


def parse_tracks(data: JsonObject | None) -> tuple[AudioTrack, ...] | None:
    if not data or boolean(data.get("result")) is not True:
        return None
    rows = data.get("tracklist")
    if not isinstance(rows, list):
        return None
    tracks = []
    indices: set[int] = set()
    for row in rows:
        if not isinstance(row, dict):
            return None
        index = row.get("index")
        description = row.get("description")
        active = boolean(row.get("active"))
        if (
            type(index) is not int
            or index < 0
            or index in indices
            or not isinstance(description, str)
            or not description.strip()
            or active is None
        ):
            return None
        indices.add(index)
        tracks.append(AudioTrack(index, description.strip(), active))
    if sum(track.active for track in tracks) > 1:
        return None
    return tuple(tracks)


class AudioTrackError(ReceiverError):
    """Selection became stale or could not be confirmed."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


async def read_state(client: OpenWebifClient, reason: str) -> ReceiverState:
    try:
        return ReceiverState.parse(await client.get("statusinfo"))
    except ValueError as err:
        raise AudioTrackError(reason) from err


async def select_track(client: OpenWebifClient, reference: str | None, track: AudioTrack) -> None:
    async with client.command_lock:
        state = await read_state(client, "audio_track_changed")
        tracks = parse_tracks(await client.get("getaudiotracks"))
        # Recheck after reading tracks; the receiver also accepts external controls.
        latest = await read_state(client, "audio_track_changed")
        if (
            not reference
            or state.standby
            or latest.standby
            or state.reference != reference
            or latest.reference != reference
            or tracks is None
            or not any(
                t.index == track.index and t.description == track.description for t in tracks
            )
        ):
            raise AudioTrackError("audio_track_changed")
        try:
            command_response(
                "selectaudiotrack", await client.get("selectaudiotrack", id=track.index)
            )
        except CommandUnconfirmed as err:
            raise AudioTrackError("audio_track_unconfirmed") from err
        try:
            tracks = parse_tracks(await client.get("getaudiotracks"))
            latest = await read_state(client, "audio_track_unconfirmed")
        except AuthenticationError:
            raise
        except ReceiverError as err:
            raise AudioTrackError("audio_track_unconfirmed") from err
        if (
            latest.standby
            or latest.reference != reference
            or tracks is None
            or not any(
                t.index == track.index and t.description == track.description and t.active
                for t in tracks
            )
        ):
            raise AudioTrackError("audio_track_unconfirmed")
