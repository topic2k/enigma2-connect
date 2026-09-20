# SPDX-License-Identifier: Apache-2.0
"""Recording catalog validity, unknown metadata, filters and real HA actions."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.core import SupportsResponse
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import device_registry as dr

from custom_components.enigma2_connect.api import ConnectionError, OpenWebifClient
from custom_components.enigma2_connect.const import DOMAIN
from custom_components.enigma2_connect.recording_library import (
    RecordingLibrary,
    RecordingLibraryError,
    progress_group,
)
from custom_components.enigma2_connect.recordings import recording_title
from custom_components.enigma2_connect.workflow_models import Recording

from .test_integration import setup

REFERENCE = "1:0:0:0:0:0:0:0:0:0:/media/movie/A%20&B: Film.ts"
MOVIE = {
    "serviceref": REFERENCE,
    "eventname": "A &amp; B",
    "servicename": "News HD",
    "recordingtime": 1789000000,
    "length": "90:15",
    "filesize": 2**30,
    "tags": "Film News",
    "lastseen": 43,
}


def library(rows, **extra):
    client = OpenWebifClient(MagicMock(), "receiver.test")
    client.get = AsyncMock(return_value={"movies": rows, **extra})
    return RecordingLibrary(client)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (0, 0),
        ("43", 43),
        (100, 100),
        (None, None),
        (-1, None),
        (101, None),
        (True, None),
        (4.5, None),
        ("?:??", None),
    ],
)
def test_progress_is_receiver_percentage_or_unknown(raw, expected):
    assert Recording.parse({**MOVIE, "lastseen": raw}).progress_percent == expected


async def test_catalog_preserves_reference_and_returns_metadata_without_writes():
    workflow = library([MOVIE])
    result = await workflow.list()
    assert result == {
        "recordings": [
            {
                "service_reference": REFERENCE,
                "title": "A & B",
                "service_name": "News HD",
                "recorded_at": 1789000000,
                "duration": 5415,
                "size_bytes": 2**30,
                "tags": ["Film", "News"],
                "progress_percent": 43,
                "directory": "/media/movie",
            }
        ],
        "total": 1,
        "count": 1,
        "tags": ["Film", "News"],
        "directories": ["/media/movie"],
    }
    workflow.client.get.assert_awaited_once_with("movielist", recursive=1)


@pytest.mark.parametrize("filename", [None, "", 7, "relative.ts", "/media/other/fallback.ts"])
async def test_unknown_metadata_and_filename_fallback(filename):
    result = await library([{"serviceref": REFERENCE, "filename": filename, "filesize": 0}]).list()
    row = result["recordings"][0]
    assert row["size_bytes"] is row["tags"] is row["progress_percent"] is None
    assert row["duration"] is row["recorded_at"] is row["service_name"] is None
    assert row["title"] == (
        filename.split("/")[-1] if isinstance(filename, str) and filename else "A%20&B: Film.ts"
    )
    assert row["directory"] == (
        None
        if filename == "relative.ts"
        else "/media/other"
        if filename == "/media/other/fallback.ts"
        else "/media/movie"
    )


async def test_empty_tags_are_distinct_from_unknown():
    result = await library([{**MOVIE, "tags": ""}, {"serviceref": "opaque"}]).list()
    assert [r["tags"] for r in result["recordings"]] == [[], None]


@pytest.mark.parametrize(
    "data",
    [
        {},
        {"movies": None},
        {"movies": {}},
        {"movies": [None]},
        {"movies": [MOVIE, {}]},
        {"movies": [MOVIE], "result": False},
        {"movies": [], "result": "false"},
    ],
)
async def test_malformed_catalog_is_not_presented_as_empty_or_partial(data):
    workflow = library([])
    workflow.client.get.return_value = data
    with pytest.raises(RecordingLibraryError):
        await workflow.list()


@pytest.mark.parametrize(
    ("params", "count"),
    [
        ({"query": " a & b "}, 1),
        ({"query": "NEWS hd"}, 1),
        ({"query": "missing"}, 0),
        ({"tag": "Film"}, 1),
        ({"tag": "film"}, 0),
        ({"directory": "/media/movie"}, 1),
        ({"directory": "/media"}, 0),
        ({"progress": "in_progress"}, 1),
        ({"progress": "zero"}, 0),
        ({"progress": "unknown"}, 0),
        ({"progress": "complete"}, 0),
        ({"query": "News", "tag": "Missing"}, 0),
    ],
)
async def test_filters_are_combined_and_choices_come_from_entire_catalog(params, count):
    result = await library([MOVIE]).list(**params)
    assert result["count"] == count
    assert result["total"] == 1
    assert result["tags"] == ["Film", "News"]
    assert result["directories"] == ["/media/movie"]


@pytest.mark.parametrize(
    ("value", "group"),
    [(None, "unknown"), (0, "zero"), (1, "in_progress"), (99, "in_progress"), (100, "complete")],
)
def test_progress_groups_do_not_call_zero_unwatched(value, group):
    assert progress_group(value) == group


async def test_no_limit_and_newest_first_unknown_dates_last():
    rows = [{**MOVIE, "serviceref": str(i), "recordingtime": i + 1} for i in range(151)]
    result = await library([{"serviceref": "unknown"}, *rows]).list()
    assert result["count"] == result["total"] == 152
    assert result["recordings"][0]["service_reference"] == "150"
    assert result["recordings"][-1]["service_reference"] == "unknown"
    assert await library([]).list() == {
        "recordings": [],
        "count": 0,
        "total": 0,
        "tags": [],
        "directories": [],
    }


@pytest.mark.parametrize(
    ("size", "suffix"), [(2**30, "1.0 GiB"), (2**20, "1.0 MiB"), (0, ""), (None, "")]
)
def test_native_browser_adds_available_size_and_tags(size, suffix):
    title = recording_title({"eventname": "Movie", "filesize": size, "tags": "Film HD"})
    assert title == " · ".join(filter(None, ["Movie", suffix, "Film, HD"]))


async def test_ha_action_reads_fresh_catalog_and_returns_data(hass, entry, receiver):
    await setup(hass, entry)
    replies, get, command, keys = receiver
    device = dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id)[0]
    replies["movielist"] = {"movies": [MOVIE]}
    get.reset_mock()
    response = await hass.services.async_call(
        DOMAIN,
        "recordings_list",
        {
            "device_id": device.id,
            "query": "news",
            "tag": "Film",
            "progress": "in_progress",
        },
        blocking=True,
        return_response=True,
    )
    assert response["count"] == 1
    get.assert_awaited_once_with("movielist", recursive=1)
    command.assert_not_awaited()
    keys.assert_not_awaited()
    assert hass.services.supports_response(DOMAIN, "recordings_list") is SupportsResponse.ONLY


@pytest.mark.parametrize("reply", [{"movies": [{}]}, ConnectionError("Offline")])
async def test_ha_action_errors_and_missing_receiver(hass, entry, receiver, reply):
    await setup(hass, entry)
    device = dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id)[0]
    receiver[0]["movielist"] = reply
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN, "recordings_list", {"device_id": device.id}, blocking=True, return_response=True
        )
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN, "recordings_list", {"device_id": "missing"}, blocking=True, return_response=True
        )
