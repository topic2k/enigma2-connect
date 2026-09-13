# SPDX-License-Identifier: Apache-2.0
"""Recording metadata formatting and stable directory navigation."""

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest
from homeassistant.components.media_player.errors import BrowseError
from homeassistant.util import dt as dt_util

from custom_components.enigma2_connect.models import ReceiverState, Snapshot
from custom_components.enigma2_connect.recordings import browse_recordings, recording_title


@pytest.mark.parametrize(("month", "local_hour"), [(1, "19:15"), (9, "20:15")])
def test_recording_details_in_local_time(monkeypatch, month, local_hour):
    movie = {
        "eventname": "Tatort",
        "recordingtime": str(datetime(2026, month, 13, 18, 15, tzinfo=UTC).timestamp()),
        "servicename": "Das Erste HD",
        "length": "90:32",
    }
    with monkeypatch.context() as timezone_patch:
        timezone_patch.setattr(dt_util, "DEFAULT_TIME_ZONE", ZoneInfo("Europe/Berlin"))
        assert recording_title(movie) == (
            f"Tatort · 13.{month:02d}.2026 {local_hour} · Das Erste HD · 1 h 30 min"
        )


@pytest.mark.parametrize(
    ("length", "suffix"),
    [
        ("45:59", " · 45 min"),
        ("60:00", " · 1 h 00 min"),
        ("125:12", " · 2 h 05 min"),
        ("?:??", ""),
        (None, ""),
        ("0:00", ""),
        ("90:99", ""),
        ("invalid", ""),
    ],
)
def test_duration_minutes_and_seconds(length, suffix):
    assert recording_title({"eventname": "Film", "length": length}) == "Film" + suffix


@pytest.mark.parametrize("timestamp", [None, "invalid", "nan", "inf", -1, 0, 1e100])
def test_missing_or_invalid_details(timestamp):
    assert (
        recording_title(
            {
                "filename": "/media/hdd/movie/Film.ts",
                "recordingtime": timestamp,
            }
        )
        == "Film.ts"
    )


def test_nested_only_recordings_preserve_root_and_reference():
    reference = "1:0:0:0:0:0:0:0:0:0:/recordings/Serien & Filme/Staffel 1/100%: Film.ts"
    snapshot = Snapshot(
        ReceiverState(False),
        movie_directory="/recordings/",
        movies=[{"serviceref": reference}],
    )
    root = browse_recordings(snapshot, "Receiver")
    assert [child.title for child in root.children] == ["Serien & Filme"]
    first = root.children[0]
    series = browse_recordings(
        snapshot, "Receiver", first.media_content_type, first.media_content_id
    )
    assert [child.title for child in series.children] == ["Staffel 1"]
    second = series.children[0]
    season = browse_recordings(
        snapshot, "Receiver", second.media_content_type, second.media_content_id
    )
    assert season.children[0].title == "100%: Film.ts"
    assert season.children[0].media_content_id == reference
    assert (
        browse_recordings(snapshot, "Receiver", "enigma2_library", "root").as_dict()
        == root.as_dict()
    )


@pytest.mark.parametrize(
    ("media_type", "media_id"),
    [
        ("enigma2_directory", "/recordings/Deleted"),
        ("enigma2_directory", "/etc"),
        ("enigma2_recording", "root"),
    ],
)
def test_unknown_folder(media_type, media_id):
    with pytest.raises(BrowseError):
        browse_recordings(
            Snapshot(ReceiverState(False), movie_directory="/recordings"),
            "Receiver",
            media_type,
            media_id,
        )


def test_missing_directory_metadata_and_relative_filename():
    snapshot = Snapshot(
        ReceiverState(False),
        movies=[
            {
                "serviceref": "1:0:0:0:0:0:0:0:0:0:/Film.ts",
                "filename": "Film.ts",
            }
        ],
    )
    assert browse_recordings(snapshot, "Receiver").children[0].title == "Film.ts"


def test_empty_library():
    assert browse_recordings(Snapshot(ReceiverState(False)), "Receiver").children == []
