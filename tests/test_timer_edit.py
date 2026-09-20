# SPDX-License-Identifier: Apache-2.0
"""Timer editing, field preservation and conflicts through simulated receivers."""

import asyncio
from copy import deepcopy
from unittest.mock import AsyncMock, patch

import pytest
import voluptuous as vol
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import device_registry as dr

from custom_components.enigma2_connect.api import (
    AuthenticationError,
    CommandRejectedError,
    CommandUnconfirmed,
    ConnectionError,
    OpenWebifClient,
    UnsupportedError,
)
from custom_components.enigma2_connect.const import DOMAIN
from custom_components.enigma2_connect.models import timer_range
from custom_components.enigma2_connect.timer_conflicts import conflicts, summary
from custom_components.enigma2_connect.timer_edit import (
    TimerEditError,
    TimerEditor,
    TimerEditRejected,
    options,
    preserved,
)
from custom_components.enigma2_connect.workflow_models import DataFormatError, TimerIdentity

from .test_integration import setup

REF = "1:0:19:283D:3FB:1:C00000:0:0:0:"
ROW = {
    "serviceref": REF,
    "begin": 1789898400,
    "end": 1789898520,
    "name": "Old &amp; title",
    "description": "Original &amp; description",
    "servicename": "Channel",
    "disabled": 0,
    "justplay": 0,
    "afterevent": 3,
    "dirname": "/media/hdd/movie/",
    "tags": "keep Tag",
    "repeated": 0,
    "allow_duplicate": 1,
    "vpsplugin_enabled": False,
    "vpsplugin_overwrite": False,
    "vpsplugin_time": -1,
    "always_zap": 0,
    "pipzap": -1,
    "state": 0,
    "recordingtype": "normal",
    "marginbefore": 60,
    "marginafter": 120,
    "hasendtime": True,
    "eit": 123,
}
OLD = TimerIdentity.parse(ROW)


class Receiver:
    def __init__(self):
        self.rows = [deepcopy(ROW)]
        self.calls = []
        self.reply = {"result": True}
        self.mutate = True
        self.post_error = None
        self.written = False
        self.client = OpenWebifClient(None, "test")
        self.client.get = AsyncMock(side_effect=self.get)
        self.editor = TimerEditor(self.client)

    async def get(self, endpoint, **params):
        self.calls.append((endpoint, params))
        assert self.client.command_lock.locked()
        if endpoint == "timerlist":
            if self.written and self.post_error:
                raise self.post_error
            return {"timers": deepcopy(self.rows)}
        assert endpoint == "timerchange"
        self.written = True
        if self.mutate:
            for key, value in params.items():
                if key in ("channelOld", "beginOld", "endOld", "returntimer"):
                    continue
                if key in ("marginbefore", "marginafter"):
                    value *= 60
                self.rows[0]["serviceref" if key == "sRef" else key] = value
        if isinstance(self.reply, BaseException):
            raise self.reply
        return deepcopy(self.reply)


async def test_edit_preserves_options_and_separates_identity():
    r = Receiver()
    result = await r.editor.edit(OLD, {"end": OLD.end + 600, "name": "Changed"}, "single")
    assert result == {"action": "timer_edit", "timer": {**OLD.response(), "end": OLD.end + 600}}
    assert [name for name, _ in r.calls] == ["timerlist", "timerchange", "timerlist"]
    sent = r.calls[1][1]
    assert sent["channelOld"] == REF and sent["endOld"] == OLD.end
    assert sent["description"] == ROW["description"]
    assert sent["tags"] == "keep Tag" and sent["dirname"] == ROW["dirname"]
    assert sent["allow_duplicate"] == 1 and sent["marginbefore"] == 1
    assert "pipzap" not in sent and "eit" not in sent
    assert not r.client.command_lock.locked()


@pytest.mark.parametrize(
    "changes,scope,repeated",
    [
        ({"weekdays": ["mon", "fri", "mon"]}, "series", 17),
        ({"weekdays": []}, "series", 0),
    ],
)
async def test_series_scope_and_weekday_mask(changes, scope, repeated):
    r = Receiver()
    r.rows[0]["repeated"] = 127
    await r.editor.edit(OLD, changes, scope)
    assert r.rows[0]["repeated"] == repeated


@pytest.mark.parametrize("previous,changes", [(127, {}), (0, {"weekdays": ["sun"]})])
async def test_series_requires_explicit_scope(previous, changes):
    r = Receiver()
    r.rows[0]["repeated"] = previous
    with pytest.raises(TimerEditError, match="timer_edit_scope"):
        await r.editor.edit(OLD, changes, "single")
    assert not r.written


@pytest.mark.parametrize("rows", [[], [ROW, ROW], [{**ROW, "serviceref": REF + "alias"}]])
async def test_stale_or_ambiguous_identity_never_written(rows):
    r = Receiver()
    r.rows = rows
    with pytest.raises(TimerEditError, match="timer_edit_missing"):
        await r.editor.edit(OLD, {"name": "new"}, "single")
    assert not r.written


@pytest.mark.parametrize(
    "key,value",
    [
        ("name", None),
        ("description", 3),
        ("dirname", None),
        ("disabled", "bad"),
        ("repeated", 128),
        ("afterevent", 4),
        ("tags", None),
        ("vpsplugin_time", "bad"),
        ("always_zap", "bad"),
        ("pipzap", 2),
        ("hasendtime", "bad"),
        ("recordingtype", "bad"),
        ("marginbefore", 61),
        ("marginafter", -1),
        ("begin", "bad"),
    ],
)
async def test_malformed_existing_data_fails_before_write(key, value):
    r = Receiver()
    r.rows[0][key] = value
    with pytest.raises(TimerEditError, match="timer_edit_data"):
        await r.editor.edit(OLD, {"name": "new"}, "single")
    assert not r.written


def test_missing_vps_and_supported_optional_formats():
    row = deepcopy(ROW)
    del row["vpsplugin_time"]
    with pytest.raises(DataFormatError):
        preserved(row)
    row.update(vpsplugin_time=123, vpsplugin_enabled=True, dirname="None", tags=["one", "two"])
    assert preserved(row)["vpsplugin_time"] == 123
    assert preserved(row)["dirname"] == ""
    assert preserved(row)["tags"] == "one two"
    del row["recordingtype"]
    assert "recordingtype" not in preserved(row)
    assert options(
        {
            "directory": "",
            "recording_type": "scrambled",
            "justplay": True,
            "disabled": False,
            "tags": [],
        }
    ) == {"dirname": "", "recordingtype": "scrambled", "justplay": 1, "disabled": 0, "tags": ""}


async def test_invalid_merged_interval():
    r = Receiver()
    with pytest.raises(TimerEditError, match="timer_edit_data"):
        await r.editor.edit(OLD, {"end": OLD.begin}, "single")
    assert not r.written


@pytest.mark.parametrize("mutate,state", [(False, "unchanged"), (True, "changed")])
async def test_conflict_rejection_reads_actual_state_without_rollback(mutate, state):
    r = Receiver()
    r.mutate = mutate
    r.reply = {"result": False, "conflicts": [ROW], "message": "secret"}
    with pytest.raises(TimerEditRejected) as caught:
        await r.editor.edit(OLD, {"end": OLD.end + 60}, "single")
    assert caught.value.timer_state == state
    assert conflicts(caught.value.response)[0]["name"] == "Old & title"
    assert "secret" not in str(caught.value)
    assert [name for name, _ in r.calls].count("timerchange") == 1
    assert r.rows[0]["end"] == OLD.end + (60 if mutate else 0)


async def test_rejection_with_failed_readback():
    r = Receiver()
    r.reply = CommandRejectedError({"result": False})
    r.post_error = ConnectionError("secret")
    with pytest.raises(TimerEditRejected) as caught:
        await r.editor.edit(OLD, {"name": "new"}, "single")
    assert caught.value.timer_state == "unknown"


@pytest.mark.parametrize("error", [CommandUnconfirmed("lost"), asyncio.CancelledError()])
async def test_uncertain_write_blocks_replay(error):
    r = Receiver()
    r.reply = error
    with pytest.raises(type(error)):
        await r.editor.edit(OLD, {"name": "new"}, "single")
    with pytest.raises(CommandUnconfirmed):
        await r.editor.edit(OLD, {"name": "newer"}, "single")
    assert [name for name, _ in r.calls].count("timerchange") == 1
    assert not r.client.command_lock.locked()


@pytest.mark.parametrize(
    "error", [AuthenticationError("secret"), ConnectionError("secret"), asyncio.CancelledError()]
)
async def test_unreadable_success_readback_guards_later_edits(error):
    r = Receiver()
    r.post_error = error
    expected = (
        type(error)
        if isinstance(error, (AuthenticationError, asyncio.CancelledError))
        else CommandUnconfirmed
    )
    with pytest.raises(expected):
        await r.editor.edit(OLD, {"name": "new"}, "single")
    with pytest.raises(CommandUnconfirmed):
        await r.editor.edit(OLD, {}, "single")


@pytest.mark.parametrize("changes", [{"name": "new"}, {"end": OLD.end + 60}])
async def test_ack_without_applied_values_is_uncertain(changes):
    r = Receiver()
    r.mutate = False
    with pytest.raises(CommandUnconfirmed):
        await r.editor.edit(OLD, changes, "single")


@pytest.mark.parametrize(
    "error", [AuthenticationError("secret"), UnsupportedError("secret"), ConnectionError("secret")]
)
async def test_known_write_failure_does_not_block_explicit_retry(error):
    r = Receiver()
    r.reply = error
    with pytest.raises(type(error)):
        await r.editor.edit(OLD, {}, "single")
    r.reply = {"result": True}
    await r.editor.edit(OLD, {}, "single")


@pytest.mark.parametrize(
    "begin,end,seconds",
    [
        ("2026-09-21T23:55:00+02:00", "2026-09-22T00:05:00+02:00", 600),
        ("2026-10-25T02:30:00+02:00", "2026-10-25T02:30:00+01:00", 3600),
        ("2027-03-28T01:55:00+01:00", "2027-03-28T03:05:00+02:00", 600),
    ],
)
async def test_midnight_and_clock_change_offsets(begin, end, seconds):
    r = Receiver()
    start, stop = timer_range(begin, end)
    assert stop - start == seconds
    result = await r.editor.edit(OLD, {"begin": start, "end": stop, "weekdays": ["sun"]}, "series")
    assert result["timer"]["begin"] == start and result["timer"]["end"] == stop


@pytest.mark.parametrize(
    "response", [{}, {"conflicts": []}, {"conflicts": [ROW, {}]}, {"conflicts": "bad"}]
)
def test_unusable_conflicts_are_not_partial_evidence(response):
    assert conflicts(response) == []


def test_conflict_projection_and_bounded_summary():
    values = conflicts({"conflicts": [{**ROW, "logentries": ["secret"], "password": "secret"}] * 7})
    assert set(values[0]) == {"service_reference", "begin", "end", "name", "service_name"}
    assert "+2" in summary(values) and "secret" not in str(values)
    assert "Old & title" in summary(values)
    assert summary([{**OLD.response(), "name": None, "service_name": None, "begin": 10**40}])


async def test_other_commands_cannot_interleave():
    r = Receiver()
    entered, release = asyncio.Event(), asyncio.Event()
    original = r.get

    async def get(endpoint, **params):
        if endpoint == "timerchange":
            entered.set()
            await release.wait()
        return await original(endpoint, **params)

    r.client.get = AsyncMock(side_effect=get)
    edit = asyncio.create_task(r.editor.edit(OLD, {"name": "new"}, "single"))
    await entered.wait()

    async def other():
        async with r.client.command_lock:
            r.calls.append(("other", {}))

    second = asyncio.create_task(other())
    await asyncio.sleep(0)
    assert not second.done()
    release.set()
    await asyncio.gather(edit, second)
    assert [name for name, _ in r.calls] == ["timerlist", "timerchange", "timerlist", "other"]


async def test_ha_edit_and_conflict_event(hass, entry, receiver):
    await setup(hass, entry)
    device = dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id)[0]
    data = {
        "device_id": device.id,
        "old_service_reference": " " + REF + " ",
        "old_begin": OLD.begin,
        "old_end": OLD.end,
        "scope": "single",
        "name": "new",
    }
    r = Receiver()
    with patch.object(entry.runtime_data.timer_editor, "client", r.client):
        result = await hass.services.async_call(
            DOMAIN, "timer_edit", data, blocking=True, return_response=True
        )
    assert result["timer"] == OLD.response()
    assert any(call.args == ("timerlist",) for call in receiver[1].call_args_list)
    events = []
    unsub = hass.bus.async_listen(f"{DOMAIN}_timer_conflict", events.append)
    r.reply = {"result": False, "conflicts": [ROW], "message": "secret"}
    with patch.object(entry.runtime_data.timer_editor, "client", r.client):
        with pytest.raises(HomeAssistantError) as caught:
            await hass.services.async_call(
                DOMAIN, "timer_edit", {**data, "name": "again"}, blocking=True
            )
    await hass.async_block_till_done()
    unsub()
    assert caught.value.translation_key == "timer_conflict"
    assert "Old & title" in caught.value.translation_placeholders["conflicts"]
    assert events[0].data["config_entry_id"] == entry.entry_id
    assert events[0].data["action"] == "timer_edit"
    assert events[0].data["timer_state"] == "changed"
    assert "secret" not in str(events[0].data)


async def test_ha_add_options_and_conflict(hass, entry, receiver):
    await setup(hass, entry)
    device = dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id)[0]
    data = {
        "device_id": device.id,
        "service_reference": REF,
        "begin": OLD.begin,
        "end": OLD.end,
        "name": "new",
        "weekdays": ["mon", "fri"],
        "tags": ["a", "b"],
        "directory": "/media/test/",
        "disabled": True,
        "recording_type": "scrambled",
    }
    await hass.services.async_call(DOMAIN, "timer_add", data, blocking=True)
    sent = receiver[2].call_args.kwargs
    assert sent["repeated"] == 17 and sent["disabled"] == 1
    assert sent["dirname"] == "/media/test/" and sent["recordingtype"] == "scrambled"
    assert sent["tags"] == "a b"
    with patch.object(
        entry.runtime_data.client,
        "command_result",
        side_effect=CommandRejectedError({"conflicts": [ROW]}),
    ):
        with pytest.raises(HomeAssistantError) as caught:
            await hass.services.async_call(
                DOMAIN, "timer_add", data, blocking=True, return_response=True
            )
    assert caught.value.translation_key == "timer_conflict"


@pytest.mark.parametrize("changes", [{"old_begin": "bad"}, {"old_end": 1}, {"end": "bad"}])
async def test_invalid_edit_times_in_ha(hass, entry, receiver, changes):
    await setup(hass, entry)
    device = dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id)[0]
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            "timer_edit",
            {
                "device_id": device.id,
                "old_service_reference": REF,
                "old_begin": OLD.begin,
                "old_end": OLD.end,
                "scope": "single",
                **changes,
            },
            blocking=True,
        )
    receiver[2].assert_not_awaited()


@pytest.mark.parametrize(
    "changes",
    [
        {"weekdays": ["Monday"]},
        {"tags": ["two words"]},
        {"directory": "relative"},
        {"scope": "occurrence"},
    ],
)
async def test_invalid_edit_options_in_ha(hass, entry, receiver, changes):
    await setup(hass, entry)
    device = dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id)[0]
    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            DOMAIN,
            "timer_edit",
            {
                "device_id": device.id,
                "old_service_reference": REF,
                "old_begin": OLD.begin,
                "old_end": OLD.end,
                "scope": "single",
                **changes,
            },
            blocking=True,
        )


async def test_ha_edit_rejection_and_precondition_are_translated(hass, entry, receiver):
    await setup(hass, entry)
    for error, key in [
        (TimerEditRejected({}, "unknown"), "timer_edit_rejected"),
        (TimerEditError("timer_edit_data"), "timer_edit_data"),
    ]:
        with patch.object(entry.runtime_data.timer_editor, "edit", side_effect=error):
            with pytest.raises(HomeAssistantError) as caught:
                await entry.runtime_data.async_timer_edit(OLD, {}, "single")
        assert caught.value.translation_key == key


@pytest.mark.parametrize("error", [AuthenticationError("secret"), asyncio.CancelledError()])
async def test_rejected_readback_auth_and_cancel_propagate(error):
    r = Receiver()
    r.reply = CommandRejectedError({"conflicts": [ROW]})
    r.post_error = error
    with pytest.raises(type(error)):
        await r.editor.edit(OLD, {"name": "new"}, "single")
    with pytest.raises(CommandUnconfirmed):
        await r.editor.edit(OLD, {}, "single")


async def test_vps_without_explicit_time_and_legacy_optional_fields():
    r = Receiver()
    r.rows[0].update(vpsplugin_enabled=True, vpsplugin_time=None)
    for key in (
        "recordingtype",
        "marginbefore",
        "marginafter",
        "always_zap",
        "pipzap",
        "hasendtime",
    ):
        del r.rows[0][key]
    await r.editor.edit(OLD, {"name": "new"}, "single")
    assert r.rows[0]["vpsplugin_enabled"] == 1
    assert r.rows[0]["vpsplugin_time"] == -1


async def test_two_receivers_and_success_without_response(hass, entry, receiver):
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    from .conftest import DATA

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
    data = {
        "device_id": device.id,
        "old_service_reference": REF,
        "old_begin": OLD.begin,
        "old_end": OLD.end,
        "scope": "single",
        "end": OLD.end + 60,
    }
    with (
        patch.object(entry.runtime_data.timer_editor, "edit") as other,
        patch.object(
            second.runtime_data.timer_editor,
            "edit",
            return_value={"action": "timer_edit", "timer": OLD.response()},
        ) as target,
    ):
        assert await hass.services.async_call(DOMAIN, "timer_edit", data, blocking=True) is None
        target.assert_awaited_once_with(OLD, {"end": OLD.end + 60}, "single")
        other.assert_not_awaited()
        with pytest.raises(ServiceValidationError):
            await hass.services.async_call(
                DOMAIN, "timer_edit", {**data, "device_id": "missing"}, blocking=True
            )


def test_service_metadata_uses_valid_ha_selectors():
    import json
    from pathlib import Path

    import yaml
    from homeassistant.helpers.selector import validate_selector

    root = Path(__file__).resolve().parents[1] / "custom_components" / DOMAIN
    services = yaml.safe_load((root / "services.yaml").read_text())
    strings = json.loads((root / "strings.json").read_text())
    for action in ("timer_add", "timer_edit"):
        assert services[action]["fields"].keys() == strings["services"][action]["fields"].keys()
        for field in services[action]["fields"].values():
            validate_selector(field["selector"])


async def test_conflict_events_only_for_timer_actions_and_correct_action_names(
    hass, entry, receiver
):
    await setup(hass, entry)
    events = []
    unsub = hass.bus.async_listen(f"{DOMAIN}_timer_conflict", events.append)
    fail = AsyncMock(side_effect=CommandRejectedError({"conflicts": [ROW]}))
    with pytest.raises(HomeAssistantError) as caught:
        await entry.runtime_data.perform(fail, "message")
    assert caught.value.translation_key == "request_failed"
    for action in ("timer_add", "timer_toggle", "record_now"):
        with pytest.raises(HomeAssistantError) as caught:
            await entry.runtime_data.perform(fail, timer_action=action)
        assert caught.value.translation_key == "timer_conflict"
    await hass.async_block_till_done()
    unsub()
    assert [event.data["action"] for event in events] == ["timer_add", "timer_toggle", "record_now"]


async def test_cancelled_edit_refresh_handling(hass, entry, receiver):
    await setup(hass, entry)
    with (
        patch.object(entry.runtime_data.timer_editor, "edit", side_effect=asyncio.CancelledError),
        patch.object(entry.runtime_data, "async_request_refresh") as refresh,
    ):
        with pytest.raises(asyncio.CancelledError):
            await entry.runtime_data.async_timer_edit(OLD, {}, "single")
        assert entry.runtime_data._slow_due == 0
        refresh.assert_not_awaited()
