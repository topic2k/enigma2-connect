# SPDX-License-Identifier: Apache-2.0
"""Supported workflow formats and strict identities for later write decisions."""

import pytest

from custom_components.enigma2_connect.workflow_models import (
    DataFormatError,
    EpgEvent,
    Recording,
    Timer,
    TimerConflict,
    TimerIdentity,
    integer,
    parse_list,
    tags,
)

REFERENCE = "1:0:19:283D:3FB:1:C00000:0:0:0:"
TIMER = {"serviceref": REFERENCE, "begin": 1789898400, "end": 1789898520}


@pytest.mark.parametrize(
    "value", [True, False, 1.5, 1.0, -1, "NaN", "1.5", None, {}, "-1", "9" * 5000]
)
def test_invalid_integer_never_becomes_identity(value):
    assert integer(value) is None
    with pytest.raises(DataFormatError):
        TimerIdentity.parse({**TIMER, "begin": value})


def test_optional_values_stay_unknown_and_flags_are_normalized():
    timer = Timer.parse(TIMER)
    assert (
        timer.disabled,
        timer.justplay,
        timer.repeated,
        timer.event_id,
        timer.directory,
        timer.tags,
    ) == (None,) * 6
    timer = Timer.parse(
        {
            **TIMER,
            "begin": "1789898400",
            "disabled": "false",
            "justplay": 1,
            "repeated": "127",
            "eit": "0",
            "dirname": "/media/Series &amp; More/",
            "tags": "News Science",
            "name": "A &amp; B",
            "servicename": 3,
        }
    )
    assert timer.identity == TimerIdentity(REFERENCE, 1789898400, 1789898520)
    assert timer.disabled is False and timer.justplay is True
    assert timer.repeated == 127 and timer.event_id == 0
    assert timer.directory == "/media/Series &amp; More/"
    assert timer.tags == ("News", "Science") and timer.name == "A & B"
    assert timer.service_name is None
    assert Timer.parse({**TIMER, "repeated": 128, "dirname": "None"}).repeated is None
    assert Timer.parse({**TIMER, "dirname": "None"}).directory is None
    assert tags(["News", "Science"]) == ("News", "Science")
    assert tags([]) == () and tags("") == ()
    assert tags(["News", 1]) is None


def test_exact_identity_and_zero_length_zap_timer():
    ref = "4097:0:0:0:0:0:0:0:0:0:http%3a//example.test/a&amp;b:My Channel"
    identity = TimerIdentity.parse({"serviceref": " " + ref + "\t", "begin": 10, "end": 10})
    assert identity.response() == {"service_reference": ref, "begin": 10, "end": 10}
    with pytest.raises(DataFormatError):
        TimerIdentity.parse({**TIMER, "end": 1})


@pytest.mark.parametrize("reference", [None, "", "  ", 42, {}])
def test_missing_reference_is_not_a_valid_timer_or_recording(reference):
    for model in (Timer, Recording):
        with pytest.raises(DataFormatError):
            model.parse({**TIMER, "serviceref": reference})


@pytest.mark.parametrize(
    "data",
    [{}, {"timers": None}, {"timers": {}}, {"timers": [TIMER, None]}, {"timers": [TIMER, {}]}],
)
def test_partial_or_unavailable_catalog_is_never_empty_or_complete(data):
    with pytest.raises(DataFormatError):
        parse_list(data, "timers", Timer.parse)


def test_empty_and_known_catalog_and_conflict_projection():
    assert parse_list({"timers": []}, "timers", Timer.parse) == ()
    assert parse_list({"timers": [TIMER]}, "timers", Timer.parse) == (Timer.parse(TIMER),)
    data = {
        **TIMER,
        "name": "Private title",
        "servicename": "Channel",
        "message": "secret",
        "logentries": ["secret"],
    }
    conflict = TimerConflict.parse(data)
    assert conflict.name == "Private title" and conflict.service_name == "Channel"
    assert "secret" not in repr(conflict)


def test_epg_uses_seconds_not_display_minutes_and_preserves_missing_text():
    event = EpgEvent.parse(
        {
            "sref": REFERENCE,
            "id": "0",
            "begin_timestamp": "100",
            "duration_sec": "3600",
            "duration": 60,
            "title": "A &amp; B",
            "longdesc": "N/A",
            "shortdesc": "Details",
        }
    )
    assert (event.begin, event.end, event.event_id) == (100, 3700, 0)
    assert event.title == "A & B" and event.description == "Details" and event.service_name is None
    with pytest.raises(DataFormatError):
        EpgEvent.parse({"sref": REFERENCE, "id": 1, "begin_timestamp": 0, "duration_sec": 0})
    with pytest.raises(DataFormatError):
        EpgEvent.parse({"sref": REFERENCE, "id": 1, "begin_timestamp": 10, "duration": 60})


@pytest.mark.parametrize(
    ("length", "expected"),
    [
        ("90:15", 5415),
        ("0:00", 0),
        ("?:??", None),
        ("5:99", None),
        (50, None),
        (None, None),
        ("9" * 5000 + ":00", None),
    ],
)
def test_recording_duration_and_missing_metadata(length, expected):
    recording = Recording.parse(
        {"serviceref": REFERENCE, "length": length, "filesize_readable": "1 GB"}
    )
    assert recording.duration == expected
    assert recording.size_bytes is None and recording.recorded_at is None and recording.tags is None
    assert (
        Recording.parse(
            {"serviceref": REFERENCE, "filesize": "0", "recordingtime": "100"}
        ).size_bytes
        == 0
    )
