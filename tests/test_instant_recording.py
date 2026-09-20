# SPDX-License-Identifier: Apache-2.0
"""Instant recording boundaries, duplicate protection and HA action/button wiring."""

import asyncio
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.enigma2_connect.api import (
    AuthenticationError,
    CommandRejectedError,
    CommandUnconfirmed,
    ConnectionError,
    OpenWebifClient,
    UnsupportedError,
)
from custom_components.enigma2_connect.button import EnigmaRecordNow
from custom_components.enigma2_connect.const import DOMAIN
from custom_components.enigma2_connect.instant_recording import (
    InstantRecording,
    InstantRecordingError,
)

from .conftest import DATA, REFERENCE
from .test_integration import setup

EVENT = {
    "sref": REFERENCE,
    "id": 7,
    "begin_timestamp": 900,
    "duration_sec": 200,
    "title": "Current",
}
STATUS = {"inStandby": False, "currservice_serviceref": REFERENCE}
TIMER = {
    "serviceref": REFERENCE,
    "begin": 1000,
    "end": 1160,
    "eit": 7,
    "disabled": 0,
    "justplay": 0,
    "state": 2,
}


@pytest.fixture
def workflow():
    client = OpenWebifClient(MagicMock(), "receiver.test")
    data = SimpleNamespace(
        status=deepcopy(STATUS),
        event=deepcopy(EVENT),
        timers=[],
        reply={"result": True, "newtimer": deepcopy(TIMER)},
        write_error=None,
        append=True,
        reads=0,
        change=None,
        post_error=None,
    )

    async def get(endpoint, **params):
        if endpoint == "statusinfo":
            return deepcopy(data.status)
        if endpoint == "getcurrent":
            data.reads += 1
            event = data.change if data.reads % 2 == 0 and data.change else data.event
            return {"now": deepcopy(event)}
        if endpoint == "timerlist":
            if data.post_error and data.timers:
                raise data.post_error
            return {"timers": deepcopy(data.timers)}
        assert endpoint == "recordnow"
        assert params == {}
        if data.append:
            data.timers.append(deepcopy(TIMER))
        if data.write_error:
            raise data.write_error
        return deepcopy(data.reply)

    client.get = AsyncMock(side_effect=get)
    with patch(
        "custom_components.enigma2_connect.instant_recording.time", return_value=1000
    ) as clock:
        yield InstantRecording(client), data, clock


def writes(workflow):
    return [call for call in workflow.client.get.await_args_list if call.args == ("recordnow",)]


async def test_concurrent_starts_make_one_timer_and_preserve_receiver_end(workflow):
    flow, data, _ = workflow
    first, second = await asyncio.gather(flow.start(), flow.start())
    assert first == {
        "started": True,
        "timer": {"service_reference": REFERENCE, "begin": 1000, "end": 1160},
    }
    assert second == {**first, "started": False}
    assert len(data.timers) == len(writes(flow)) == 1
    assert not flow.client.command_lock.locked()


@pytest.mark.parametrize(
    ("status", "event", "reason"),
    [
        ({**STATUS, "inStandby": True}, EVENT, "recording_not_live"),
        ({}, EVENT, "recording_not_live"),
        ({"inStandby": False}, EVENT, "recording_not_live"),
        ({**STATUS, "currservice_filename": "/media/movie.ts"}, EVENT, "recording_not_live"),
        (STATUS, None, "recording_no_epg"),
        (STATUS, {}, "recording_no_epg"),
        (STATUS, {**EVENT, "duration_sec": 0}, "recording_no_epg"),
        (STATUS, {**EVENT, "begin_timestamp": 1001}, "recording_no_epg"),
        (STATUS, {**EVENT, "begin_timestamp": 800}, "recording_no_epg"),
        (STATUS, {**EVENT, "title": "N/A"}, "recording_no_epg"),
        (STATUS, {**EVENT, "sref": "other"}, "recording_changed"),
    ],
)
async def test_preconditions_never_write(workflow, status, event, reason):
    flow, data, _ = workflow
    data.status, data.event = status, event
    with pytest.raises(InstantRecordingError) as error:
        await flow.start()
    assert error.value.reason == reason
    assert writes(flow) == []


async def test_event_boundary_between_reads_does_not_record_next_programme(workflow):
    flow, data, _ = workflow
    data.change = {**EVENT, "id": 8}
    with pytest.raises(InstantRecordingError, match="recording_changed"):
        await flow.start()
    assert not writes(flow)


@pytest.mark.parametrize(
    "timer", [TIMER, {**TIMER, "state": 0}, {**TIMER, "begin": 1, "end": 2, "repeated": 127}]
)
async def test_existing_recording_is_preserved(workflow, timer):
    flow, data, _ = workflow
    data.timers = [deepcopy(timer)]
    response = await flow.start()
    assert response["started"] is False
    assert data.timers == [timer]
    assert not writes(flow)


@pytest.mark.parametrize(
    "timer",
    [
        {**TIMER, "serviceref": "other"},
        {**TIMER, "disabled": 1},
        {**TIMER, "justplay": 1},
        {**TIMER, "state": 3},
        {**TIMER, "state": 0, "begin": 1050},
    ],
)
async def test_other_or_inactive_timers_do_not_block_start(workflow, timer):
    flow, data, _ = workflow
    data.timers = [deepcopy(timer)]
    assert (await flow.start())["started"] is True
    assert data.timers[0] == timer and len(writes(flow)) == 1


@pytest.mark.parametrize(
    "timers", [None, {}, [None], [{}], [{**TIMER, "disabled": None}], [{**TIMER, "justplay": None}]]
)
async def test_unknown_timer_data_fails_closed(workflow, timers):
    flow, data, _ = workflow
    data.timers = timers
    with pytest.raises(InstantRecordingError, match="recording_timer_data"):
        await flow.start()
    assert not writes(flow)


@pytest.mark.parametrize("error", [CommandUnconfirmed(), asyncio.CancelledError()])
@pytest.mark.parametrize("applied", [False, True])
async def test_uncertain_or_cancelled_start_is_never_replayed(workflow, error, applied):
    flow, data, _ = workflow
    data.write_error, data.append = error, applied
    with pytest.raises(type(error)):
        await flow.start()
    data.write_error = None
    if applied:
        assert (await flow.start())["started"] is False
    else:
        with pytest.raises(CommandUnconfirmed):
            await flow.start()
    assert len(writes(flow)) == 1 and not flow.client.command_lock.locked()


@pytest.mark.parametrize(
    "error",
    [
        AuthenticationError(),
        UnsupportedError(),
        CommandRejectedError({"result": False}),
        ConnectionError(),
    ],
)
async def test_definite_rejection_allows_a_later_explicit_attempt(workflow, error):
    flow, data, _ = workflow
    data.write_error, data.append = error, False
    with pytest.raises(type(error)):
        await flow.start()
    data.write_error = None
    assert (await flow.start())["started"] is True
    assert len(writes(flow)) == 2


@pytest.mark.parametrize(
    "reply",
    [
        {},
        {"result": False, "message": "private"},
        {"result": True, "newtimer": []},
        {"result": True, "newtimer": {}},
        {"result": True, "newtimer": {**TIMER, "eit": 8}},
        {"result": True, "newtimer": {**TIMER, "serviceref": "other"}},
        {"result": True, "newtimer": {**TIMER, "begin": 800}},
        {"result": True, "newtimer": {**TIMER, "end": 1000}},
        {"result": True},
    ],
)
async def test_ambiguous_returned_timer_does_not_claim_success(workflow, reply):
    flow, data, _ = workflow
    data.reply, data.append = reply, False
    error = CommandRejectedError if reply.get("result") is False else CommandUnconfirmed
    with pytest.raises(error):
        await flow.start()
    assert len(writes(flow)) == 1


async def test_legacy_success_without_newtimer_is_confirmed_by_fresh_list(workflow):
    flow, data, _ = workflow
    data.reply = {"result": True}
    assert (await flow.start())["timer"]["end"] == 1160
    assert len(writes(flow)) == 1


@pytest.mark.parametrize("error", [ConnectionError(), AuthenticationError()])
async def test_post_write_read_failure_keeps_retry_guard(workflow, error):
    flow, data, _ = workflow
    data.reply, data.post_error = {"result": True}, error
    with pytest.raises(
        AuthenticationError if isinstance(error, AuthenticationError) else CommandUnconfirmed
    ):
        await flow.start()
    data.post_error, data.timers, data.append = None, [], False
    with pytest.raises(CommandUnconfirmed):
        await flow.start()
    assert len(writes(flow)) == 1


async def test_confirmed_start_guards_list_lag_then_allows_explicit_restart(workflow):
    flow, data, clock = workflow
    data.append = False
    assert (await flow.start())["started"]
    with pytest.raises(CommandUnconfirmed):
        await flow.start()
    clock.return_value = 1011
    assert (await flow.start())["started"]
    assert len(writes(flow)) == 2


async def test_uncertain_guard_expires_at_end_and_allows_new_event(workflow):
    flow, data, clock = workflow
    data.append, data.write_error = False, CommandUnconfirmed()
    with pytest.raises(CommandUnconfirmed):
        await flow.start()
    clock.return_value = 1100
    data.event = {**EVENT, "begin_timestamp": 1100, "id": 8}
    data.reply = {"result": True, "newtimer": {**TIMER, "begin": 1100, "end": 1300, "eit": 8}}
    data.write_error = None
    assert (await flow.start())["started"]
    assert len(writes(flow)) == 2


async def test_preflight_does_not_interleave_with_other_commands(workflow):
    flow, data, _ = workflow
    entered, release = asyncio.Event(), asyncio.Event()
    original = flow.client.get.side_effect

    async def blocked(endpoint, **params):
        if endpoint == "timerlist":
            entered.set()
            await release.wait()
        if endpoint == "message":
            return {"result": True}
        return await original(endpoint, **params)

    flow.client.get.side_effect = blocked
    start = asyncio.create_task(flow.start())
    await entered.wait()
    message = asyncio.create_task(flow.client.command("message", text="test"))
    await asyncio.sleep(0)
    assert not any(call.args == ("message",) for call in flow.client.get.await_args_list)
    release.set()
    await asyncio.gather(start, message)
    assert flow.client.get.await_args_list[-1].args == ("message",)


@pytest.mark.parametrize("response", [False, True])
async def test_ha_action_and_button_refresh_and_share_guard(hass, entry, receiver, response):
    await setup(hass, entry)
    receiver[0]["statusinfo"].update(STATUS)
    receiver[0]["getcurrent"] = {"now": deepcopy(EVENT)}
    base_get = receiver[1].side_effect

    async def get(endpoint, **params):
        if endpoint == "recordnow":
            assert not params
            receiver[0]["timerlist"] = {"timers": [deepcopy(TIMER)]}
            receiver[0]["statusinfo"]["isRecording"] = True
            return {"result": True, "newtimer": deepcopy(TIMER)}
        return await base_get(endpoint, **params)

    receiver[1].side_effect = get
    device = dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id)[0]
    with patch("custom_components.enigma2_connect.instant_recording.time", return_value=1000):
        result = await hass.services.async_call(
            DOMAIN, "record_now", {"device_id": device.id}, blocking=True, return_response=response
        )
        assert result["started"] if response else result is None
        await hass.services.async_call(
            "button",
            "press",
            {"entity_id": "button.test_receiver_record_current_programme"},
            blocking=True,
        )
    assert sum(call.args == ("recordnow",) for call in receiver[1].await_args_list) == 1
    assert entry.runtime_data.data.state.recording is True
    assert len(entry.runtime_data.data.timers) == 1
    button = er.async_get(hass).async_get("button.test_receiver_record_current_programme")
    assert button.disabled_by is None and button.entity_category is None


@pytest.mark.parametrize(
    ("error", "key"),
    [
        (InstantRecordingError("recording_no_epg"), "recording_no_epg"),
        (CommandUnconfirmed(), "timer_unconfirmed"),
        (CommandRejectedError({"result": False}), "request_failed"),
    ],
)
async def test_ha_instant_failure_is_translated_and_refreshes(hass, entry, receiver, error, key):
    await setup(hass, entry)
    with (
        patch.object(entry.runtime_data.instant_recording, "start", side_effect=error),
        patch.object(entry.runtime_data, "async_request_refresh") as refresh,
    ):
        with pytest.raises(HomeAssistantError) as caught:
            await EnigmaRecordNow(entry.runtime_data, "record_now").async_press()
        assert caught.value.translation_key == key
        refresh.assert_awaited_once()
        assert entry.runtime_data._slow_due == 0


async def test_ha_cancellation_preserves_cancellation_and_invalidates(hass, entry, receiver):
    await setup(hass, entry)
    with (
        patch.object(
            entry.runtime_data.instant_recording, "start", side_effect=asyncio.CancelledError
        ),
        patch.object(entry.runtime_data, "async_request_refresh") as refresh,
    ):
        with pytest.raises(asyncio.CancelledError):
            await entry.runtime_data.async_record_now()
        assert entry.runtime_data._slow_due == 0
        refresh.assert_not_awaited()


async def test_ha_receiver_target_is_mandatory_and_isolated(hass, entry, receiver):
    await setup(hass, entry)
    receiver[0]["about"]["info"]["ifaces"][0]["mac"] = "11:22:33:44:55:66"
    second = MockConfigEntry(
        domain=DOMAIN,
        title="Second",
        unique_id="112233445566",
        data={**DATA, "host": "other.local"},
    )
    second.add_to_hass(hass)
    assert await hass.config_entries.async_setup(second.entry_id)
    device = dr.async_entries_for_config_entry(dr.async_get(hass), second.entry_id)[0]
    with (
        patch.object(entry.runtime_data.instant_recording, "start") as first,
        patch.object(
            second.runtime_data.instant_recording,
            "start",
            return_value={"started": False, "timer": {}},
        ) as target,
    ):
        with pytest.raises(ServiceValidationError):
            await hass.services.async_call(
                DOMAIN, "record_now", {"device_id": "missing"}, blocking=True
            )
        await hass.services.async_call(
            DOMAIN, "record_now", {"device_id": device.id}, blocking=True
        )
        target.assert_awaited_once()
        first.assert_not_awaited()


async def test_unknown_series_state_cannot_justify_another_start(workflow):
    flow, data, _ = workflow
    data.timers = [{**TIMER, "state": None, "begin": 1, "end": 2, "repeated": 127}]
    with pytest.raises(InstantRecordingError, match="recording_timer_data"):
        await flow.start()
    assert not writes(flow)


@pytest.mark.parametrize("update", [{"duration_sec": 300}, {"begin_timestamp": 950}])
async def test_epg_timing_updates_do_not_bypass_uncertain_start_guard(workflow, update):
    flow, data, _ = workflow
    data.append, data.write_error = False, CommandUnconfirmed()
    with pytest.raises(CommandUnconfirmed):
        await flow.start()
    data.write_error = None
    data.event.update(update)
    with pytest.raises(CommandUnconfirmed):
        await flow.start()
    assert len(writes(flow)) == 1
