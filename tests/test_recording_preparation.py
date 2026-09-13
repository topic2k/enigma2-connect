# SPDX-License-Identifier: Apache-2.0
"""Background artwork: lifecycle, new recordings, fairness and bounded warming."""

import asyncio
from dataclasses import replace
from time import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from custom_components.enigma2_connect.models import ReceiverState, Snapshot
from custom_components.enigma2_connect.recording_images import (
    CACHE_TTL,
    CONF_IMAGE_SOURCES,
    RecordingImages,
)

from .test_integration import setup
from .test_recording_images import MOVIE, picture


@pytest.fixture
def manager(hass, entry, tmp_path, monkeypatch):
    monkeypatch.setattr("custom_components.enigma2_connect.recording_images.BACKGROUND_DELAY", 0.01)
    coordinator = SimpleNamespace(
        entry=entry,
        last_update_success=True,
        data=Snapshot(ReceiverState(False, recording=False), movies=[MOVIE], timers=[]),
    )
    result = RecordingImages(hass, coordinator)
    result.cache = tmp_path
    return result


def movie(name, timestamp):
    return {**MOVIE, "serviceref": f"{MOVIE['serviceref']}-{name}", "recordingtime": timestamp}


async def finish(manager):
    if manager._worker:
        async with asyncio.timeout(3):
            await manager._worker


async def test_start_warms_newest_first_and_reuses_disk_cache(manager):
    old, new = movie("old", 100), movie("new", 200)
    manager.coordinator.data = replace(manager.coordinator.data, movies=[old, new])
    with patch.object(manager, "_from_source", AsyncMock(return_value=picture())) as source:
        manager.async_start()
        source.assert_not_awaited()  # Setup never waits for frame extraction.
        await finish(manager)
        assert [call.args[1] for call in source.await_args_list] == [new, old]
        manager.async_catalog_updated(manager.coordinator.data)
        await finish(manager)
        assert source.await_count == 2
        # A new manager after an integration restart uses the existing disk images.
        restarted = RecordingImages(manager.hass, manager.coordinator)
        restarted.cache = manager.cache
        with patch.object(restarted, "_from_source", AsyncMock(side_effect=AssertionError)):
            restarted.async_start()
            await finish(restarted)
        await restarted.async_close()
    await manager.async_close()


async def test_failed_images_retry_on_later_poll_and_expired_cache_is_renewed(manager, monkeypatch):
    now = time()
    monkeypatch.setattr("custom_components.enigma2_connect.recording_images.time", lambda: now)
    with patch.object(manager, "_from_source", AsyncMock(return_value=None)) as source:
        manager.async_start()
        await finish(manager)
        source.assert_awaited_once()
        manager.async_catalog_updated(manager.coordinator.data)
        await finish(manager)
        source.assert_awaited_once()
        now += 121
        source.return_value = picture()
        manager.async_catalog_updated(manager.coordinator.data)
        await finish(manager)
        assert source.await_count == 2
        now += CACHE_TTL + 1
        manager.async_catalog_updated(manager.coordinator.data)
        await finish(manager)
        assert source.await_count == 3
    await manager.async_close()


def test_running_recording_with_planned_duration_waits_for_actual_elapsed_time(manager):
    manager._snapshot = replace(
        manager.coordinator.data, state=ReceiverState(False, recording=True)
    )
    assert not manager._snapshot_ready({**MOVIE, "recordingtime": time() - 60, "length": "90:00"})


async def test_foreground_requests_run_before_next_background_item(manager):
    first, backlog, foreground_movie = (
        movie("first", 200),
        movie("backlog", 100),
        movie("visible", 50),
    )
    manager.coordinator.data = replace(manager.coordinator.data, movies=[first, backlog])
    started, release = asyncio.Event(), asyncio.Event()
    calls = []

    async def generate(source, item, options):
        calls.append(item)
        if item == first:
            started.set()
            await release.wait()
        return picture()

    with patch.object(manager, "_from_source", side_effect=generate):
        manager.async_start()
        await asyncio.wait_for(started.wait(), 3)
        foreground = asyncio.create_task(manager.async_image(foreground_movie))
        await asyncio.sleep(0)
        release.set()
        await foreground
        await finish(manager)
        assert calls == [first, foreground_movie, backlog]
    await manager.async_close()


async def test_new_recording_preempts_backlog_and_deleted_item_is_removed(manager):
    current, obsolete, added = movie("current", 200), movie("removed", 100), movie("new", 300)
    manager.coordinator.data = replace(manager.coordinator.data, movies=[current, obsolete])
    started, release = asyncio.Event(), asyncio.Event()
    calls = []

    async def generate(source, item, options):
        calls.append(item)
        if item == current:
            started.set()
            await release.wait()
        return picture()

    with patch.object(manager, "_from_source", side_effect=generate):
        manager.async_start()
        await asyncio.wait_for(started.wait(), 3)
        manager.async_catalog_updated(replace(manager.coordinator.data, movies=[current, added]))
        release.set()
        await finish(manager)
        assert calls == [current, added]
    await manager.async_close()


async def test_growing_recording_waits_for_position_then_finished_short_uses_midpoint(manager):
    growing = {**MOVIE, "length": "5:00", "recordingtime": time() - 300}
    timer = {"filename": MOVIE["filename"][:-3], "state": 2, "justplay": 0}
    snapshot = replace(manager.coordinator.data, movies=[growing], timers=[timer])
    manager.coordinator.data = snapshot
    with patch.object(manager, "_from_source", AsyncMock(return_value=picture())) as source:
        manager.async_start()
        await finish(manager)
        source.assert_not_awaited()
        mature = {**growing, "length": "11:00", "recordingtime": time() - 660}
        manager.async_catalog_updated(replace(snapshot, movies=[mature]))
        await finish(manager)
        source.assert_awaited_once()
        finished = {**growing, "serviceref": growing["serviceref"] + "-finished"}
        manager.async_catalog_updated(replace(snapshot, movies=[finished], timers=[]))
        await finish(manager)
        assert source.await_count == 2
    await manager.async_close()


async def test_internet_posters_do_not_wait_for_snapshot_position(manager):
    manager.hass.config_entries.async_update_entry(
        manager.coordinator.entry, options={CONF_IMAGE_SOURCES: ["custom", "snapshot"]}
    )
    manager.coordinator.data = replace(
        manager.coordinator.data,
        state=ReceiverState(False, recording=True),
        movies=[{**MOVIE, "length": "1:00", "recordingtime": time() - 60}],
    )
    with patch.object(manager, "_from_source", AsyncMock(return_value=picture())) as source:
        manager.async_start()
        await finish(manager)
        assert source.await_args.args[0] == "custom"
    await manager.async_close()


async def test_foreground_shares_active_background_job_and_close_cancels_it(manager):
    started = asyncio.Event()

    async def generate(*args):
        started.set()
        await asyncio.Event().wait()

    with patch.object(manager, "_from_source", side_effect=generate) as source:
        manager.async_start()
        await asyncio.wait_for(started.wait(), 3)
        foreground = asyncio.create_task(manager.async_image(MOVIE))
        await asyncio.sleep(0)
        source.assert_awaited_once()
        await manager.async_close()
        with pytest.raises(asyncio.CancelledError):
            await foreground
        assert manager._worker is None and not manager._queue
        assert await manager.async_image(MOVIE) is None


async def test_cache_capacity_does_not_cause_endless_archive_regeneration(manager, monkeypatch):
    monkeypatch.setattr("custom_components.enigma2_connect.recording_images.CACHE_LIMIT", 2)
    manager.coordinator.data = replace(
        manager.coordinator.data, movies=[movie(str(index), index) for index in range(10)]
    )
    with patch.object(manager, "_from_source", AsyncMock(return_value=picture())) as source:
        manager.async_start()
        await finish(manager)
        assert [call.args[1]["recordingtime"] for call in source.await_args_list] == [9, 8]
        # Browsing an older recording can evict a prepared image. A catalog poll
        # must not immediately warm the whole archive again and undo that choice.
        assert await manager.async_image(movie("0", 0))
        manager.async_catalog_updated(manager.coordinator.data)
        await finish(manager)
        assert source.await_count == 3
        assert len(list(manager.cache.glob("*.jpg"))) == 2
    await manager.async_close()


async def test_disabled_or_unavailable_catalog_does_not_start_work(manager):
    manager.hass.config_entries.async_update_entry(
        manager.coordinator.entry, options={CONF_IMAGE_SOURCES: []}
    )
    with patch.object(manager, "_from_source", AsyncMock()) as source:
        manager.async_start()
        assert manager._worker is None
        manager.hass.config_entries.async_update_entry(manager.coordinator.entry, options={})
        manager.async_catalog_updated(replace(manager.coordinator.data, movies=None))
        assert manager._worker is None
        manager.coordinator.last_update_success = False
        manager.async_catalog_updated(manager.coordinator.data)
        await finish(manager)
        source.assert_not_awaited()
        manager.coordinator.last_update_success = True
        source.return_value = picture()
        manager.async_catalog_updated(manager.coordinator.data)
        await finish(manager)
        source.assert_awaited_once()
    await manager.async_close()


async def test_malformed_optional_rows_do_not_break_catalog_preparation(manager):
    manager.coordinator.data = replace(
        manager.coordinator.data,
        movies=[None, "invalid", {}, {"serviceref": 123}, {**MOVIE, "filename": 123}, MOVIE],
        timers=[None, "invalid"],
    )
    with patch.object(manager, "_from_source", AsyncMock(return_value=picture())) as source:
        manager.async_start()
        await finish(manager)
        source.assert_awaited_once()
    await manager.async_close()


async def test_real_coordinator_initial_setup_and_later_catalog_trigger(
    hass, entry, receiver, monkeypatch
):
    receiver[0]["movielist"] = {"movies": [MOVIE]}
    monkeypatch.setattr("custom_components.enigma2_connect.recording_images.BACKGROUND_DELAY", 0.01)
    with patch.object(RecordingImages, "_from_source", AsyncMock(return_value=picture())) as source:
        await setup(hass, entry)
        manager = entry.runtime_data.recording_images
        await finish(manager)
        source.assert_awaited_once()
        receiver[0]["movielist"]["movies"].append(movie("new", 200))
        entry.runtime_data.invalidate_lists()
        await entry.runtime_data.async_refresh()
        await finish(manager)
        assert source.await_count == 2
        assert await hass.config_entries.async_unload(entry.entry_id)
        assert manager._closed and manager._worker is None
