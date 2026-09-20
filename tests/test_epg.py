# SPDX-License-Identifier: Apache-2.0
"""EPG search, event identity checks, one-shot writes and HA action responses."""

import asyncio
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.core import SupportsResponse
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr

from custom_components.enigma2_connect.api import (
    AuthenticationError,
    CommandRejectedError,
    CommandUnconfirmed,
    ConnectionError,
    OpenWebifClient,
    ProtocolError,
    UnsupportedError,
)
from custom_components.enigma2_connect.const import DOMAIN
from custom_components.enigma2_connect.epg import EpgError, EpgWorkflow

from .conftest import REFERENCE
from .test_api import client_for
from .test_integration import setup

EXPECTED = {"service_reference": REFERENCE, "event_id": 7, "begin": 2000, "end": 2300}
EVENT = {
    "sref": REFERENCE,
    "id": 7,
    "begin_timestamp": 2000,
    "duration_sec": 300,
    "title": "A &amp; B",
    "sname": "Station",
    "shortdesc": "Description",
}
DETAIL = {
    "sref": REFERENCE,
    "id": 7,
    "begin": 2000,
    "duration": 300,
    "title": "A &amp; B",
    "channel": "Station",
}
TIMER = {
    "serviceref": REFERENCE,
    "begin": 1700,
    "end": 2900,
    "eit": 7,
    "disabled": 0,
    "justplay": 0,
    "repeated": 0,
    "state": 0,
}


@pytest.fixture
def epg():
    client = OpenWebifClient(MagicMock(), "receiver.test")
    data = SimpleNamespace(
        detail=deepcopy(DETAIL),
        events=[deepcopy(EVENT)],
        timers=[],
        write_error=None,
        post_error=None,
        append=True,
        reply={"result": True},
        reads=0,
        changed=None,
        write_count=0,
        newtimer=deepcopy(TIMER),
    )

    async def get(endpoint, **params):
        if endpoint in ("epgsearch", "epgsimilar"):
            return {"events": deepcopy(data.events)}
        if endpoint == "event":
            data.reads += 1
            return {
                "event": deepcopy(data.changed if data.reads == 2 and data.changed else data.detail)
            }
        if endpoint == "timerlist":
            if data.write_count and data.post_error:
                raise data.post_error
            return {"timers": deepcopy(data.timers)}
        assert endpoint == "timeraddbyeventid"
        assert params == {"sRef": REFERENCE, "eventid": 7, "justplay": 0, "afterevent": 3}
        data.write_count += 1
        if data.append:
            data.timers.append(deepcopy(data.newtimer))
        if data.write_error:
            raise data.write_error
        return deepcopy(data.reply)

    client.get = AsyncMock(side_effect=get)
    with patch("custom_components.enigma2_connect.epg.time", return_value=1000) as clock:
        yield EpgWorkflow(client), data, clock


async def test_search_sort_filter_deduplicate_and_opaque_references(epg):
    flow, data, _ = epg
    other = {**EVENT, "begin_timestamp": 1500, "sref": "ref&amp;opaque"}
    data.events = [EVENT, EVENT, {**EVENT, "begin_timestamp": 1}, other]
    result = await flow.search("A & B")
    assert result["truncated"] is False
    assert result["events"][0] == {
        **EXPECTED,
        "service_reference": "ref&amp;opaque",
        "begin": 1500,
        "end": 1800,
        "title": "A & B",
        "service_name": "Station",
        "description": "Description",
    }
    flow.client.get.assert_awaited_once_with("epgsearch", search="A & B")
    assert len((await flow.search("A"))["events"]) == 2
    data.events = []
    assert await flow.search("Missing") == {"events": [], "truncated": False}


@pytest.mark.parametrize("rows", [None, {}, [None], [{}], [{**EVENT, "duration_sec": 0}]])
async def test_bad_search_is_not_empty_success(epg, rows):
    flow, data, _ = epg
    data.events = rows
    with pytest.raises(EpgError, match="epg_data"):
        await flow.search("News")


async def test_similar_checks_exact_event_and_normalizes_transport_array(epg):
    flow, _, _ = epg
    assert (await flow.similar(EXPECTED))["events"][0]["event_id"] == 7
    flow.client.get.assert_any_await("epgsimilar", sRef=REFERENCE, eventid=7)
    client, _ = client_for(data=[EVENT])
    assert await client.get("epgsimilar") == {"events": [EVENT]}
    with pytest.raises(ProtocolError):
        await client.get("timerlist")


@pytest.mark.parametrize(
    "detail",
    [
        None,
        {},
        {**DETAIL, "id": 8},
        {**DETAIL, "sref": "other"},
        {**DETAIL, "begin": 2001},
        {**DETAIL, "duration": 1},
        {**DETAIL, "title": ""},
    ],
)
async def test_stale_or_invalid_events_never_write(epg, detail):
    flow, data, _ = epg
    data.detail = detail
    with pytest.raises(EpgError, match="epg_changed"):
        await flow.record(EXPECTED)
    assert data.write_count == 0


async def test_expired_and_changed_between_preflight_reads(epg):
    flow, data, clock = epg
    clock.return_value = 2300
    with pytest.raises(EpgError, match="epg_changed"):
        await flow.record(EXPECTED)
    clock.return_value = 1000
    data.reads = 0
    data.changed = {**DETAIL, "id": 8}
    with pytest.raises(EpgError, match="epg_changed"):
        await flow.record(EXPECTED)
    assert data.write_count == 0


async def test_concurrent_calls_create_once_preserve_margins_and_existing(epg):
    flow, data, _ = epg
    first, second = await asyncio.gather(flow.record(EXPECTED), flow.record(EXPECTED))
    assert first == {
        "created": True,
        "timer": {"service_reference": REFERENCE, "begin": 1700, "end": 2900},
    }
    assert second == {**first, "created": False}
    assert data.write_count == 1
    assert not flow.client.command_lock.locked()


@pytest.mark.parametrize(
    "timer",
    [
        {**TIMER, "serviceref": "other"},
        {**TIMER, "state": 3, "begin": 1, "end": 2},
        {**TIMER, "begin": 1, "end": 2},
        {**TIMER, "begin": 2300, "end": 2500},
    ],
)
async def test_other_finished_and_nonoverlapping_timers_preserved(epg, timer):
    flow, data, _ = epg
    data.timers = [timer]
    assert (await flow.record(EXPECTED))["created"] is True
    assert data.timers[0] == timer


@pytest.mark.parametrize(
    "changes",
    [
        {"disabled": 1},
        {"justplay": 1},
        {"state": None},
        {"repeated": 1},
        {"repeated": None},
        {"begin": 2050},
        {"end": 2200},
    ],
)
async def test_uncertain_or_partial_existing_timer_never_modified(epg, changes):
    flow, data, _ = epg
    data.timers = [{**TIMER, **changes}]
    with pytest.raises(EpgError, match="epg_timer_ambiguous"):
        await flow.record(EXPECTED)
    assert data.write_count == 0


async def test_bad_timer_list_blocks_write(epg):
    flow, data, _ = epg
    data.timers = [{}]
    with pytest.raises(EpgError, match="recording_timer_data"):
        await flow.record(EXPECTED)
    assert data.write_count == 0


@pytest.mark.parametrize(
    "error", [CommandUnconfirmed("lost"), ProtocolError("bad"), asyncio.CancelledError()]
)
async def test_uncertain_write_and_cancellation_never_replayed(epg, error):
    flow, data, _ = epg
    data.append = False
    data.write_error = error
    with pytest.raises(type(error)):
        await flow.record(EXPECTED)
    with pytest.raises(CommandUnconfirmed):
        await flow.record(EXPECTED)
    assert data.write_count == 1
    assert not flow.client.command_lock.locked()


@pytest.mark.parametrize(
    "error",
    [
        AuthenticationError(),
        UnsupportedError(),
        CommandRejectedError({"result": False}),
        ConnectionError(),
    ],
)
async def test_definite_rejection_allows_explicit_retry(epg, error):
    flow, data, _ = epg
    data.append = False
    data.write_error = error
    with pytest.raises(type(error)):
        await flow.record(EXPECTED)
    data.write_error = None
    data.append = True
    assert (await flow.record(EXPECTED))["created"] is True


@pytest.mark.parametrize(
    "mode", ["missing", "wrong_id", "ambiguous", "auth", "offline", "bad_ack", "bad_list"]
)
async def test_confirmation_failure_keeps_guard(epg, mode):
    flow, data, _ = epg
    if mode == "missing":
        data.append = False
    elif mode == "wrong_id":
        data.newtimer["eit"] = 8
    elif mode == "ambiguous":
        data.newtimer["disabled"] = 1
    elif mode == "auth":
        data.post_error = AuthenticationError()
    elif mode == "offline":
        data.post_error = ConnectionError()
    elif mode == "bad_ack":
        data.reply = {}
    else:
        data.newtimer = {}
    with pytest.raises(AuthenticationError if mode == "auth" else CommandUnconfirmed):
        await flow.record(EXPECTED)
    data.timers = []
    data.post_error = None
    with pytest.raises(CommandUnconfirmed):
        await flow.record(EXPECTED)
    assert data.write_count == 1


async def test_confirmed_write_list_lag_and_expired_guard(epg):
    flow, data, clock = epg
    await flow.record(EXPECTED)
    data.timers = []
    with pytest.raises(CommandUnconfirmed):
        await flow.record(EXPECTED)
    clock.return_value = 1011
    assert (await flow.record(EXPECTED))["created"] is True


async def test_actions_responses_validation_conflicts_and_refresh(hass, entry, receiver):
    import voluptuous as vol

    await setup(hass, entry)
    device = dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id)[0]
    coordinator = entry.runtime_data
    assert hass.services.supports_response(DOMAIN, "epg_search") is SupportsResponse.ONLY
    with patch.object(
        coordinator.epg, "search", AsyncMock(return_value={"events": [], "truncated": False})
    ) as search:
        result = await hass.services.async_call(
            DOMAIN,
            "epg_search",
            {"device_id": device.id, "query": " News "},
            blocking=True,
            return_response=True,
        )
        assert result["events"] == []
        search.assert_awaited_once_with(query="News")
    with patch.object(
        coordinator.epg, "similar", AsyncMock(return_value={"events": []})
    ) as similar:
        assert await hass.services.async_call(
            DOMAIN,
            "epg_similar",
            {"device_id": device.id, **EXPECTED},
            blocking=True,
            return_response=True,
        ) == {"events": []}
        similar.assert_awaited_once_with(EXPECTED)
    with (
        patch.object(
            coordinator.epg, "record", AsyncMock(return_value={"created": True})
        ) as record,
        patch.object(coordinator, "async_request_refresh", AsyncMock()) as refresh,
    ):
        assert await hass.services.async_call(
            DOMAIN,
            "record_event",
            {"device_id": device.id, **EXPECTED},
            blocking=True,
            return_response=True,
        ) == {"created": True}
        assert (
            await hass.services.async_call(
                DOMAIN, "record_event", {"device_id": device.id, **EXPECTED}, blocking=True
            )
            is None
        )
        assert refresh.await_count == 2
        record.side_effect = EpgError("epg_changed")
        with pytest.raises(HomeAssistantError) as error:
            await hass.services.async_call(
                DOMAIN, "record_event", {"device_id": device.id, **EXPECTED}, blocking=True
            )
        assert error.value.translation_key == "epg_changed"
        record.side_effect = CommandRejectedError({"conflicts": [TIMER]})
        events = []
        hass.bus.async_listen(DOMAIN + "_timer_conflict", lambda event: events.append(event.data))
        with pytest.raises(HomeAssistantError) as error:
            await hass.services.async_call(
                DOMAIN, "record_event", {"device_id": device.id, **EXPECTED}, blocking=True
            )
        assert error.value.translation_key == "timer_conflict"
        await hass.async_block_till_done()
        assert events[0]["action"] == "record_event"
    for changes in [{"event_id": True}, {"begin": 2.5}, {"event_id": -1}]:
        with pytest.raises(vol.Invalid):
            await hass.services.async_call(
                DOMAIN,
                "record_event",
                {"device_id": device.id, **EXPECTED, **changes},
                blocking=True,
            )
    for changes in [{"query": " "}, {"query": "News", "limit": 51}]:
        with pytest.raises(vol.Invalid):
            await hass.services.async_call(
                DOMAIN,
                "epg_search",
                {"device_id": device.id, **changes},
                blocking=True,
                return_response=True,
            )


async def test_search_record_calendar_end_to_end_with_ha(hass, entry, receiver):
    from datetime import UTC, datetime

    await setup(hass, entry)
    device = dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id)[0]
    receiver[0]["event"] = {"event": DETAIL}
    receiver[0]["epgsearch"] = {"events": [EVENT]}
    base_get = receiver[1].side_effect

    async def get(endpoint, **params):
        if endpoint == "timeraddbyeventid":
            receiver[0]["timerlist"] = {"timers": [{**TIMER, "name": "EPG test"}]}
            return {"result": True}
        return await base_get(endpoint, **params)

    receiver[1].side_effect = get
    with patch("custom_components.enigma2_connect.epg.time", return_value=1000):
        result = await hass.services.async_call(
            DOMAIN,
            "epg_search",
            {"device_id": device.id, "query": "A"},
            blocking=True,
            return_response=True,
        )
        selected = {k: result["events"][0][k] for k in EXPECTED}
        result = await hass.services.async_call(
            DOMAIN,
            "record_event",
            {"device_id": device.id, **selected},
            blocking=True,
            return_response=True,
        )
        assert result["created"] is True
        entity_id = hass.states.async_all("calendar")[0].entity_id
        response = await hass.services.async_call(
            "calendar",
            "get_events",
            {
                "entity_id": entity_id,
                "start_date_time": datetime.fromtimestamp(1000, UTC).isoformat(),
                "end_date_time": datetime.fromtimestamp(4000, UTC).isoformat(),
            },
            blocking=True,
            return_response=True,
        )
        events = response[entity_id]["events"]
        assert len(events) == 1 and events[0]["summary"] == "EPG test"
        assert datetime.fromisoformat(events[0]["start"]).timestamp() == 1700
        assert datetime.fromisoformat(events[0]["end"]).timestamp() == 2900


async def test_search_and_similar_return_all_received_matches(epg):
    flow, data, _ = epg
    data.events = [{**EVENT, "id": i} for i in range(123)]
    for result in (await flow.search("News"), await flow.similar(EXPECTED)):
        assert len(result["events"]) == 123
        assert result["events"][-1]["event_id"] == 122
        assert result["truncated"] is False
