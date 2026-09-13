# SPDX-License-Identifier: Apache-2.0
"""API type variations and catalog identity regressions."""

import pytest

from custom_components.enigma2_connect.models import (
    ReceiverState,
    boolean,
    identity,
    number,
    picon_candidates,
    services,
    signal_snr_db,
    timer_range,
)


def test_malformed_optional_metadata_is_ignored():
    assert signal_snr_db(None) is None
    assert identity({"ifaces": [None, {}, {"mac": "00:00:00:00:00:00"}]}) is None
    assert services([None, [1, "invalid"], ["ref", ""], {}, ["only-one"]]) == {}
    assert ReceiverState.parse({"inStandby": False}, {"next": ["invalid"]}).next_title is None
    assert picon_candidates("1:0:0:0:0:0:0:0:0:0:/recording.ts", "***") == [
        "/picon/starstarstar.png"
    ]
    assert picon_candidates("unknown", "---") == []


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (True, True),
        (False, False),
        ("true", True),
        ("False", False),
        (1, True),
        (0, False),
        (None, None),
        ("unknown", None),
    ],
)
def test_boolean(value, expected):
    assert boolean(value) is expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (0, 0),
        (70, 70),
        ("70%", 70),
        ("12.5 dB", 12.5),
        (None, None),
        ("", None),
        ("NaN", None),
        (True, None),
    ],
)
def test_number(value, expected):
    assert number(value) == expected


def test_receiver_status():
    state = ReceiverState.parse(
        {
            "inStandby": False,
            "isRecording": "true",
            "isStreaming": "false",
            "muted": "false",
            "volume": "25",
        },
        {"next": {"title": "A &amp; B"}},
    )
    assert state.recording is True
    assert state.streaming is False
    assert state.muted is False
    assert state.volume == 0.25
    assert state.next_title == "A & B"
    with pytest.raises(ValueError):
        ReceiverState.parse({})


def test_service_duplicates_and_markers():
    rows = [
        ["1:0:1:a", "Duplicate"],
        ["1:0:1:b", "Duplicate"],
        ["1:64:1:c", "Marker"],
        ["1:7:1:d", "Folder"],
        ["1:320:1:e", "Numbered marker"],
        ["bad", "Bad"],
        ["1:0:1:a", "Duplicate"],
    ]
    result = services(rows, channels=True)
    assert len(result) == 2
    assert set(result) == {"Duplicate [1:0:1:a]", "Duplicate [1:0:1:b]"}


def test_stable_identity():
    assert (
        identity({"ifaces": [{"mac": "00:00:00:00:00:00"}, {"mac": "AA-BB-CC-DD-EE-FF"}]})
        == "aabbccddeeff"
    )


def test_timer_range():
    assert (
        timer_range("2026-10-25T02:30:00+02:00", "2026-10-25T02:30:00+01:00")[1]
        - timer_range("2026-10-25T02:30:00+02:00", "2026-10-25T02:30:00+01:00")[0]
        == 3600
    )
    for start, end in [(10, 10), (11, 10), ("2026-01-01T10:00:00", "2026-01-01T11:00:00")]:
        with pytest.raises(ValueError):
            timer_range(start, end)
