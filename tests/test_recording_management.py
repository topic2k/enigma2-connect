# SPDX-License-Identifier: Apache-2.0
"""Recording writes, conservative preflight and non-repeating reconciliation."""

import asyncio
from copy import deepcopy
from unittest.mock import AsyncMock, MagicMock
from urllib.parse import quote

import aiohttp
import pytest
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from yarl import URL

from custom_components.enigma2_connect.api import (
    AuthenticationError,
    CommandRejectedError,
    CommandUnconfirmed,
    ConnectionError,
    OpenWebifClient,
    UnsupportedError,
    power_command_middleware,
)
from custom_components.enigma2_connect.const import DOMAIN
from custom_components.enigma2_connect.recording_management import (
    RecordingManagementError,
    RecordingManager,
    movie_path,
    reference_path,
    revision,
    safe_path,
)
from custom_components.enigma2_connect.workflow_models import Recording

from .test_integration import setup

REF = "1:0:0:0:0:0:0:0:0:0:/media/movie/A%20&B.ts"
MOVIE = {
    "serviceref": REF,
    "eventname": "Original",
    "recordingtime": 1000,
    "filesize": 100,
    "length": "1:00",
    "servicename": "News",
}
REVISION = revision(Recording.parse(MOVIE))


def workflow():
    state = {
        "rows": [deepcopy(MOVIE)],
        "targets": [],
        "applied": False,
        "apply": True,
        "ack": {"result": True},
        "status": {"inStandby": False, "isRecording": False, "isStreaming": False},
        "timers": {"timers": []},
        "locations": {"locations": ["/media/target"]},
        "about": {"info": {"streams": []}},
    }
    client = OpenWebifClient(MagicMock(), "receiver.test")

    async def get(endpoint, **params):
        if endpoint == "movielist":
            directory = params.get("dirname", "/media/movie")
            if state.get("read_error") and state["applied"]:
                raise ConnectionError()
            return {
                "movies": deepcopy(
                    state["targets"] if directory == "/media/target" else state["rows"]
                ),
                "directory": state.get("directory", directory),
            }
        if endpoint == "statusinfo":
            return state["status"]
        if endpoint == "timerlist":
            return state["timers"]
        if endpoint == "about":
            if isinstance(state["about"], Exception):
                raise state["about"]
            return state["about"]
        if endpoint == "getlocations":
            return state["locations"]
        state["applied"] = True
        if state["apply"]:
            if endpoint == "movieinfo":
                state["rows"][0]["eventname"] = params["title"]
            elif endpoint == "moviedelete":
                state["rows"] = []
            else:
                state["targets"] = [
                    {**state["rows"][0], "serviceref": REF.replace("/media/movie", "/media/target")}
                ]
                state["rows"] = []
        if isinstance(state["ack"], BaseException):
            raise state["ack"]
        return state["ack"]

    client.get = AsyncMock(side_effect=get)
    return RecordingManager(client), state


@pytest.mark.parametrize("action", ["rename", "move", "delete"])
async def test_confirmed_operations_and_exact_parameters(action):
    manager, state = workflow()
    result = await manager.manage(
        REF, REVISION, action, title="New & Title", directory="/media/target", confirm_delete=True
    )
    assert result["status"] == "completed"
    assert manager.pending is None
    assert await manager.status() == result
    endpoint = {"rename": "movieinfo", "move": "moviemove", "delete": "moviedelete"}[action]
    expected = {"sRef": REF}
    if action == "rename":
        expected = {"sRef": quote(REF, safe=""), "title": "New & Title"}
    if action == "move":
        expected["dirname"] = "/media/target"
    calls = [c for c in manager.client.get.await_args_list if c.args[0] == endpoint]
    assert len(calls) == 1 and calls[0].kwargs == expected


@pytest.mark.parametrize(
    ("params", "reason"),
    [
        ({"action": "other"}, "recording_input"),
        ({"action": "delete"}, "recording_confirm"),
        ({"title": " "}, "recording_input"),
        ({"title": "bad\nname"}, "recording_input"),
        ({"title": "x" * 201}, "recording_input"),
        ({"expected_revision": "old"}, "recording_stale"),
        ({"service_reference": "foreign"}, "recording_stale"),
        ({"action": "move", "directory": "/media/unknown"}, "recording_destination"),
        ({"action": "move", "directory": "/media/movie"}, "recording_destination"),
    ],
)
async def test_preconditions_never_send_writes(params, reason):
    manager, state = workflow()
    kwargs = {
        "service_reference": REF,
        "expected_revision": REVISION,
        "action": "rename",
        "title": "New",
    } | params
    with pytest.raises(RecordingManagementError, match=reason):
        await manager.manage(**kwargs)
    assert not state["applied"]


@pytest.mark.parametrize(
    "raw",
    [
        {},
        {"inStandby": False},
        {"inStandby": False, "isRecording": True},
    ],
)
@pytest.mark.parametrize("action", ["rename", "move", "delete"])
async def test_unknown_or_recording_receiver_is_blocked(raw, action):
    manager, state = workflow()
    state["status"] = raw
    with pytest.raises(RecordingManagementError):
        await manager.manage(
            REF, REVISION, action, title="New", directory="/media/target", confirm_delete=True
        )
    assert not state["applied"]


@pytest.mark.parametrize(
    "timers",
    [
        {},
        {"timers": [{}]},
        {"timers": [{"serviceref": "ref", "begin": 1, "end": 2, "state": 1}]},
        {"timers": [{"serviceref": "ref", "begin": 1, "end": 2}]},
    ],
)
async def test_preparing_or_unknown_timers_block(timers):
    manager, state = workflow()
    state["timers"] = timers
    with pytest.raises(RecordingManagementError):
        await manager.manage(REF, REVISION, "rename", title="New")
    assert not state["applied"]


@pytest.mark.parametrize("path", ["relative", "//host/file", "/a/../b", "/a\nb", "/a\\b"])
def test_unsafe_paths(path):
    with pytest.raises(RecordingManagementError):
        safe_path(path)


@pytest.mark.parametrize("ref", ["opaque", "1:0:0:0:0:0:0:0:0:0:/", "1:0:0:0:0:0:0:0:0:0:/folder"])
def test_non_file_references(ref):
    with pytest.raises(RecordingManagementError):
        movie_path(Recording.parse({"serviceref": ref}))


@pytest.mark.parametrize("rows", [[MOVIE, MOVIE], [{}]])
async def test_ambiguous_catalog(rows):
    manager, state = workflow()
    state["rows"] = rows
    with pytest.raises(RecordingManagementError, match="recording_data"):
        await manager.manage(REF, REVISION, "rename", title="New")


@pytest.mark.parametrize("field", ["recordingtime", "filesize"])
async def test_unknown_identity_metadata(field):
    manager, state = workflow()
    state["rows"][0].pop(field)
    expected = revision(Recording.parse(state["rows"][0]))
    with pytest.raises(RecordingManagementError, match="recording_data"):
        await manager.manage(REF, expected, "rename", title="New")


@pytest.mark.parametrize("locations", [{}, {"locations": [1]}])
async def test_invalid_locations(locations):
    manager, state = workflow()
    state["locations"] = locations
    with pytest.raises(RecordingManagementError, match="recording_destination"):
        await manager.manage(REF, REVISION, "move", directory="/media/target")


async def test_wrong_directory_and_target_collision():
    manager, state = workflow()
    state["directory"] = "/wrong"
    with pytest.raises(RecordingManagementError, match="recording_destination"):
        await manager.manage(REF, REVISION, "move", directory="/media/target")
    del state["directory"]
    state["targets"] = [{**MOVIE, "serviceref": REF.replace("/media/movie", "/media/target")}]
    with pytest.raises(RecordingManagementError, match="recording_collision"):
        await manager.manage(REF, REVISION, "move", directory="/media/target")
    assert not state["applied"]


async def test_source_changed_during_preflight():
    manager, state = workflow()
    original = manager.client.get.side_effect

    async def get(endpoint, **params):
        if endpoint == "timerlist":
            state["rows"][0]["filesize"] += 1
        return await original(endpoint, **params)

    manager.client.get.side_effect = get
    with pytest.raises(RecordingManagementError, match="recording_stale"):
        await manager.manage(REF, REVISION, "rename", title="New")
    assert not state["applied"]


@pytest.mark.parametrize("action", ["rename", "move", "delete"])
async def test_pending_write_never_replays_and_later_read_confirms(action):
    manager, state = workflow()
    state["apply"] = False
    result = await manager.manage(
        REF, REVISION, action, title="New", directory="/media/target", confirm_delete=True
    )
    assert result["status"] == "pending"
    with pytest.raises(RecordingManagementError, match="recording_pending"):
        await manager.manage(REF, REVISION, action)
    if action == "rename":
        state["rows"][0]["eventname"] = "New"
    elif action == "delete":
        state["rows"] = []
    else:
        state["targets"] = [{**MOVIE, "serviceref": REF.replace("/media/movie", "/media/target")}]
        state["rows"] = []
    assert (await manager.status())["status"] == "completed"


@pytest.mark.parametrize("ack", [CommandUnconfirmed(), CommandRejectedError({"result": False}), {}])
async def test_uncertain_response_checks_actual_result(ack):
    manager, state = workflow()
    state["ack"] = ack
    assert (await manager.manage(REF, REVISION, "rename", title="New"))["status"] == "completed"


@pytest.mark.parametrize("error", [AuthenticationError(), UnsupportedError(), ConnectionError()])
async def test_definite_transport_failure_releases_guard(error):
    manager, state = workflow()
    state["ack"] = error
    state["apply"] = False
    with pytest.raises(type(error)):
        await manager.manage(REF, REVISION, "rename", title="New")
    assert manager.pending is None


async def test_lost_confirmation_and_cancellation_keep_guard():
    manager, state = workflow()
    state["read_error"] = True
    assert (await manager.manage(REF, REVISION, "rename", title="New"))["status"] == "pending"
    manager, state = workflow()
    state["ack"] = asyncio.CancelledError()
    with pytest.raises(asyncio.CancelledError):
        await manager.manage(REF, REVISION, "rename", title="New")
    assert manager.pending is not None


@pytest.mark.parametrize("endpoint", ["movieinfo", "moviemove", "moviedelete"])
async def test_recording_writes_are_not_replayed_by_aiohttp(endpoint):
    handler = AsyncMock(side_effect=aiohttp.ServerDisconnectedError())
    request = MagicMock(url=URL(f"http://receiver/api/{endpoint}"))
    with pytest.raises(CommandUnconfirmed):
        await power_command_middleware(request, handler)
    handler.assert_awaited_once()


@pytest.mark.parametrize("stream_kind", ["live", "same", "other", "unknown"])
async def test_ha_actions_metadata_refresh_and_stream_guard(hass, entry, receiver, stream_kind):
    await setup(hass, entry)
    coordinator = entry.runtime_data
    device = dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id)[0]
    coordinator.recording_manager.manage = AsyncMock(return_value={"status": "completed"})
    data = {
        "device_id": device.id,
        "service_reference": REF,
        "expected_revision": REVISION,
        "action": "rename",
        "title": "New",
    }
    result = await hass.services.async_call(
        DOMAIN, "recording_manage", data, blocking=True, return_response=True
    )
    assert result == {"status": "completed"}
    coordinator.recording_manager.status = AsyncMock(return_value={"status": "idle"})
    assert (
        await hass.services.async_call(
            DOMAIN,
            "recording_operation_status",
            {"device_id": device.id},
            blocking=True,
            return_response=True,
        )
    )["status"] == "idle"
    receiver[0]["getlocations"] = {"locations": ["/a", "/a", "/b"]}
    assert (
        await hass.services.async_call(
            DOMAIN,
            "recording_destinations",
            {"device_id": device.id},
            blocking=True,
            return_response=True,
        )
    )["directories"] == ["/a", "/b"]
    receiver[0]["getlocations"] = {"locations": [7]}
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN,
            "recording_destinations",
            {"device_id": device.id},
            blocking=True,
            return_response=True,
        )
    session = MagicMock(async_close=AsyncMock())
    source = URL("http://receiver/file").with_query(
        file=REF.split(":", 10)[-1] if stream_kind == "same" else "/media/movie/other.ts"
    )
    if stream_kind == "unknown":
        source = URL("http://receiver/file")
    coordinator.media_stream.sessions[session] = (source, stream_kind != "live")
    calls = coordinator.recording_manager.manage.await_count
    try:
        assert await hass.services.async_call(
            DOMAIN, "recording_manage", data, blocking=True, return_response=True
        ) == {"status": "completed"}
        for action in ("move", "delete"):
            if stream_kind in ("same", "unknown"):
                with pytest.raises(HomeAssistantError) as error:
                    await hass.services.async_call(
                        DOMAIN, "recording_manage", data | {"action": action}, blocking=True
                    )
                assert error.value.translation_key == "recording_busy"
            else:
                assert await hass.services.async_call(
                    DOMAIN,
                    "recording_manage",
                    data | {"action": action},
                    blocking=True,
                    return_response=True,
                ) == {"status": "completed"}
        assert coordinator.recording_manager.manage.await_count == calls + (
            1 if stream_kind in ("same", "unknown") else 3
        )
        assert coordinator.media_stream.sessions[session] == (source, stream_kind != "live")
        session.async_close.assert_not_awaited()
        with pytest.raises(HomeAssistantError) as error:
            await hass.services.async_call(
                DOMAIN,
                "recording_manage",
                data | {"action": "delete", "service_reference": "1:0:0:0:0:0:0:0:0:0:/a/../b.ts"},
                blocking=True,
            )
        assert error.value.translation_key == "recording_path"
    finally:
        coordinator.media_stream.sessions.clear()
    coordinator.media_stream.sessions.clear()
    coordinator.recording_manager.manage.side_effect = RecordingManagementError("recording_stale")
    with pytest.raises(HomeAssistantError) as error:
        await hass.services.async_call(DOMAIN, "recording_manage", data, blocking=True)
    assert error.value.translation_key == "recording_stale"


@pytest.mark.parametrize("streaming", [False, True, None])
@pytest.mark.parametrize("playing", [False, True])
@pytest.mark.parametrize("action", ["rename", "move", "delete"])
async def test_unrelated_streaming_and_playback_do_not_block_management(streaming, playing, action):
    manager, state = workflow()
    state["status"]["isStreaming"] = streaming
    if playing:
        state["status"]["currservice_filename"] = "/media/movie/other.ts"
    original = deepcopy(state["rows"][0])
    kwargs = {"title": "New", "directory": "/media/target", "confirm_delete": True}
    assert (await manager.manage(REF, REVISION, action, **kwargs))["status"] == "completed"
    if action == "rename":
        assert state["rows"] == [original | {"eventname": "New"}]


async def test_missing_streaming_flag_does_not_block_title_change():
    manager, state = workflow()
    del state["status"]["isStreaming"]
    assert (await manager.manage(REF, REVISION, "rename", title="New"))["status"] == "completed"


@pytest.mark.parametrize("reader", ["filename", "reference", "stream"])
@pytest.mark.parametrize("action", ["rename", "move", "delete"])
async def test_matching_receiver_reader_blocks_file_changes_only(reader, action):
    manager, state = workflow()
    if reader == "filename":
        state["status"]["currservice_filename"] = REF.split(":", 10)[-1]
    elif reader == "reference":
        state["status"]["currservice_serviceref"] = REF
    else:
        state["about"]["info"]["streams"] = [{"ref": REF}]
    params = {"title": "New", "directory": "/media/target", "confirm_delete": True}
    if action == "rename":
        assert (await manager.manage(REF, REVISION, action, **params))["status"] == "completed"
    else:
        with pytest.raises(RecordingManagementError, match="recording_busy"):
            await manager.manage(REF, REVISION, action, **params)
        assert not state["applied"]


@pytest.mark.parametrize(
    "about",
    [
        {},
        {"info": {}},
        UnsupportedError(),
        {"info": {"streams": [{"ref": "1:0:1:live"}, {"ref": REF.replace("A%20&B", "other")}]}},
    ],
)
async def test_absent_optional_or_unrelated_stream_info_is_not_a_global_guard(about):
    manager, state = workflow()
    state["about"] = about
    assert (await manager.manage(REF, REVISION, "delete", confirm_delete=True))[
        "status"
    ] == "completed"


@pytest.mark.parametrize(
    "about", [{"info": []}, {"info": {"streams": None}}, {"info": {"streams": [{}]}}]
)
async def test_malformed_supplied_stream_information_blocks_writes(about):
    manager, state = workflow()
    state["about"] = about
    with pytest.raises(RecordingManagementError, match="recording_data"):
        await manager.manage(REF, REVISION, "delete", confirm_delete=True)
    assert not state["applied"]


@pytest.mark.parametrize("timer_state", [1, 2, None])
@pytest.mark.parametrize("same", [False, True])
@pytest.mark.parametrize("suffix", [False, True])
async def test_recording_and_preparation_match_exact_timer_filename(timer_state, same, suffix):
    manager, state = workflow()
    path = REF.split(":", 10)[-1] if same else "/media/movie/other.ts"
    timer = {
        "serviceref": "channel",
        "begin": 1,
        "end": 2,
        "state": timer_state,
        "filename": path if suffix else path[:-3],
    }
    state["timers"] = {"timers": [timer]}
    state["status"]["isRecording"] = timer_state == 2
    if same:
        with pytest.raises(RecordingManagementError, match="recording_busy"):
            await manager.manage(REF, REVISION, "delete", confirm_delete=True)
        assert not state["applied"]
    else:
        assert (await manager.manage(REF, REVISION, "delete", confirm_delete=True))[
            "status"
        ] == "completed"


@pytest.mark.parametrize("flags", [{"disabled": True}, {"justplay": True}])
async def test_disabled_and_zap_timers_do_not_lock_files(flags):
    manager, state = workflow()
    state["timers"] = {
        "timers": [{"serviceref": "channel", "begin": 1, "end": 2, "state": 1, **flags}]
    }
    assert (await manager.manage(REF, REVISION, "delete", confirm_delete=True))[
        "status"
    ] == "completed"


async def test_unidentified_receiver_playback_has_specific_error():
    manager, state = workflow()
    state["status"]["currservice_filename"] = "relative.ts"
    with pytest.raises(RecordingManagementError, match="recording_activity_unknown"):
        await manager.manage(REF, REVISION, "delete", confirm_delete=True)
    assert not state["applied"]


def test_pending_guard_covers_only_source_and_destination_and_preserves_literal_paths():
    manager, _ = workflow()
    source = REF.split(":", 10)[-1]
    target = "/media/target/A%20&B.ts"
    assert not manager.blocks_stream(source)
    manager.pending = {"action": "rename", "service_reference": REF}
    assert not manager.blocks_stream(source)
    manager.pending = {"action": "move", "service_reference": REF, "target_path": target}
    assert manager.blocks_stream(source) and manager.blocks_stream(target)
    assert manager.blocks_stream(None)
    assert not manager.blocks_stream("/media/movie/other.ts")
    assert not manager.blocks_stream("/media/movie/A &B.ts")
    manager.pending = {"action": "delete"}
    assert manager.blocks_stream(source)
    assert reference_path(None) is None and reference_path("live:reference") is None
    assert str(reference_path("/a:b:c:d:e:f:g:h:i:j:k.ts")) == "/a:b:c:d:e:f:g:h:i:j:k.ts"
