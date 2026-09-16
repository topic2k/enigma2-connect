# SPDX-License-Identifier: Apache-2.0
"""Concurrent stream admission, live sharing and independent playback lifetimes."""

import asyncio
import logging
from pathlib import Path
from time import monotonic
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.components.media_source import Unresolvable
from yarl import URL

from custom_components.enigma2_connect.media_stream import StreamSession

from . import test_media_stream as fixtures

configured = fixtures.configured
spawn = fixtures.spawn


@pytest.fixture
async def pool(entry, configured):
    await configured.async_close()
    manager = entry.runtime_data.media_stream
    manager.sessions.clear()
    return manager


async def test_new_channel_keeps_existing_browser_playing(
    hass, entry, pool, spawn, socket_enabled, hass_client_no_auth, caplog
):
    caplog.set_level(logging.DEBUG, logger="custom_components.enigma2_connect.media_stream")
    client = await hass_client_no_auth()
    first = await pool.async_play(URL("http://receiver.local:8001/sat1"), recording=False)
    second = await pool.async_play(URL("http://receiver.local:8001/pro7"), recording=False)
    assert first.url != second.url and len(pool.sessions) == 2
    for playback in (first, second):
        response = await client.get(playback.url)
        assert response.status == 200
        segment = await client.get(playback.url.replace("index.m3u8", "segment00000000.ts"))
        assert segment.status == 200 and await segment.read() == b"video"
    assert all(not process.kill.called for process, _ in spawn)
    sessions = list(pool.sessions)
    first_directory = sessions[0].directory.name
    await sessions[0].async_close()
    assert (await client.get(first.url)).status == 404
    assert (await client.get(second.url)).status == 200
    assert not await hass.async_add_executor_job(Path(first_directory).exists)
    await hass.config_entries.async_unload(entry.entry_id)
    assert pool.closed and not pool.sessions and not pool.pending
    assert (await client.get(second.url)).status == 404
    assert all(process.kill.called for process, _ in spawn)
    assert len({session.stream_id for session in sessions}) == 2
    for session in sessions:
        assert f"[stream={session.stream_id}] Pool slot reserved" in caplog.text
        assert f"[stream={session.stream_id}] Releasing playback resources" in caplog.text
    logs = "\n".join(
        record.getMessage() for record in caplog.records if record.name.endswith("media_stream")
    )
    assert "receiver.local" not in logs and "sat1" not in logs and "pro7" not in logs
    assert all(playback.url.split("/")[-2] not in logs for playback in (first, second))


async def test_default_limit_five_and_sixth_start_does_not_evict(
    hass, entry, pool, spawn, socket_enabled, hass_client_no_auth, caplog
):
    caplog.set_level(logging.DEBUG, logger="custom_components.enigma2_connect.media_stream")
    client = await hass_client_no_auth()
    results = await asyncio.gather(
        *(
            pool.async_play(URL(f"http://receiver.local:8001/channel{i}"), recording=False)
            for i in range(6)
        ),
        return_exceptions=True,
    )
    failures = [item for item in results if isinstance(item, Unresolvable)]
    assert len(failures) == 1
    assert failures[0].translation_key == "stream_limit_reached"
    assert failures[0].translation_placeholders == {"limit": "5"}
    assert len(pool.sessions) == len(spawn) == 5 and not pool.pending
    for result in results:
        if not isinstance(result, Exception):
            assert (await client.get(result.url)).status == 200
    assert all(not process.kill.called for process, _ in spawn)
    # An existing live source is still shareable when every slot is occupied.
    shared = await pool.async_play(URL("http://receiver.local:8001/channel0"), recording=False)
    assert shared.url == results[0].url and len(spawn) == 5
    assert "Stream request rejected: reason=stream_limit active=5 limit=5" in caplog.text
    assert "Live request shared: starting=False" in caplog.text


@pytest.mark.parametrize("limit", [1, 3, 0])
async def test_configurable_limit_and_unlimited(hass, entry, pool, spawn, socket_enabled, limit):
    hass.config_entries.async_update_entry(entry, options={**entry.options, "stream_limit": limit})
    count = limit or 7
    for index in range(count):
        await pool.async_play(URL(f"http://receiver.local/file?file={index}.ts"), recording=True)
    assert len(pool.sessions) == count
    if limit:
        with pytest.raises(Unresolvable):
            await pool.async_play(URL("http://receiver.local/file?file=extra.ts"), recording=True)
    await pool.async_close()
    with pytest.raises(Unresolvable) as raised:
        await pool.async_play(URL("http://receiver.local:8001/channel"), recording=False)
    assert raised.value.translation_key == "stream_disabled"


async def test_live_is_shared_but_recordings_start_independently(
    hass, entry, pool, spawn, socket_enabled
):
    source = URL("http://receiver.local:8001/channel")
    first = await pool.async_play(source, recording=False)
    session = next(iter(pool.sessions))
    session.touched = monotonic() - 60
    assert await pool.async_play(source, recording=False) == first
    assert monotonic() - session.touched < 2
    recording = URL("http://receiver.local/file?file=movie.ts")
    movie1 = await pool.async_play(recording, recording=True)
    movie2 = await pool.async_play(recording, recording=True)
    assert movie1.url != movie2.url
    assert len(pool.sessions) == len(spawn) == 3
    assert all("-re" in args for _, args in spawn[1:])


@pytest.mark.parametrize("stale", ["idle", "lifetime", "failed", "closed"])
async def test_stale_session_releases_slot_without_waiting_for_watcher(
    hass, entry, pool, spawn, socket_enabled, stale
):
    hass.config_entries.async_update_entry(entry, options={**entry.options, "stream_limit": 1})
    first = await pool.async_play(URL("http://receiver.local:8001/first"), recording=False)
    session = next(iter(pool.sessions))
    if stale == "idle":
        session.touched -= 121
    elif stale == "lifetime":
        session.started -= 21601
    elif stale == "failed":
        session.process.returncode = 1
    else:
        await session.async_close()
    second = await pool.async_play(URL("http://receiver.local:8001/second"), recording=False)
    assert first.url != second.url and session not in pool.sessions
    assert session.closed and len(pool.sessions) == 1


async def test_failed_start_returns_slot_and_preserves_other_streams(
    hass, entry, pool, spawn, socket_enabled
):
    hass.config_entries.async_update_entry(entry, options={**entry.options, "stream_limit": 2})
    first = await pool.async_play(URL("http://receiver.local:8001/working"), recording=False)
    with patch.object(StreamSession, "_start", side_effect=OSError("failed")):
        with pytest.raises(Unresolvable):
            await pool.async_play(URL("http://receiver.local:8001/broken"), recording=False)
    assert len(pool.sessions) == 1 and not pool.pending
    assert (
        await pool.async_play(URL("http://receiver.local:8001/working"), recording=False)
    ).url == first.url
    await pool.async_play(URL("http://receiver.local:8001/new"), recording=False)
    assert len(pool.sessions) == 2 and not spawn[0][0].kill.called


async def test_shared_start_survives_one_cancelled_viewer(hass, entry, pool, spawn, socket_enabled):
    hass.config_entries.async_update_entry(entry, options={**entry.options, "stream_limit": 1})
    entered, release = asyncio.Event(), asyncio.Event()
    original = StreamSession._start

    async def blocked(session, source, **kwargs):
        entered.set()
        await release.wait()
        await original(session, source, **kwargs)

    source = URL("http://receiver.local:8001/channel")
    with patch.object(StreamSession, "_start", blocked):
        first = asyncio.create_task(pool.async_play(source, recording=False))
        await entered.wait()
        second = asyncio.create_task(pool.async_play(source, recording=False))
        await asyncio.sleep(0)
        first.cancel()
        with pytest.raises(asyncio.CancelledError):
            await first
        with pytest.raises(Unresolvable):
            await pool.async_play(URL("http://receiver.local:8001/extra"), recording=False)
        release.set()
        playback = await second
    assert len(pool.sessions) == len(spawn) == 1
    assert not pool.pending and not spawn[0][0].kill.called
    assert await pool.async_play(source, recording=False) == playback


async def test_unload_cancels_all_pending_starts(hass, entry, pool, socket_enabled):
    started = 0
    entered = asyncio.Event()

    async def blocked(session, source, **kwargs):
        nonlocal started
        started += 1
        if started == 2:
            entered.set()
        await asyncio.Event().wait()

    with patch.object(StreamSession, "_start", blocked):
        calls = [
            asyncio.create_task(
                pool.async_play(URL(f"http://receiver.local:8001/{i}"), recording=False)
            )
            for i in range(2)
        ]
        await entered.wait()
        sessions = list(pool.sessions)
        await hass.config_entries.async_unload(entry.entry_id)
        results = await asyncio.gather(*calls, return_exceptions=True)
    assert all(isinstance(result, asyncio.CancelledError) for result in results)
    assert all(session.closed for session in sessions)
    assert pool.closed and not pool.sessions and not pool.pending


async def test_disabled_pool_rejects_start(hass, entry, pool):
    hass.config_entries.async_update_entry(entry, options={})
    with pytest.raises(Unresolvable) as raised:
        await pool.async_play(URL("http://receiver.local/file"), recording=True)
    assert raised.value.translation_key == "stream_disabled"


async def test_limit_option_validation_and_save(hass, entry, pool):
    with patch.object(hass.config_entries, "async_reload", new_callable=AsyncMock):
        flow = await hass.config_entries.options.async_init(entry.entry_id)
        form = await hass.config_entries.options.async_configure(
            flow["flow_id"], {"next_step_id": "settings"}
        )
        values = form["data_schema"]({})
        assert values["stream_limit"] == 5
        import voluptuous as vol

        with pytest.raises(vol.Invalid):
            form["data_schema"]({**values, "stream_limit": -1})
        assert form["data_schema"]({**values, "stream_limit": 0})["stream_limit"] == 0
        assert form["data_schema"]({**values, "stream_limit": 20})["stream_limit"] == 20
        result = await hass.config_entries.options.async_configure(
            flow["flow_id"], {**values, "stream_limit": 3}
        )
        assert result["type"] == "create_entry" and entry.options["stream_limit"] == 3
