# SPDX-License-Identifier: Apache-2.0
"""Native timer forms: receiver choices, lifecycle and timezone boundaries."""

import json
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
import yaml
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.selector import DateTimeSelector, validate_selector
from homeassistant.helpers.service import async_get_all_descriptions
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.enigma2_connect.action_choices import (
    ActionChoices,
    action_epoch,
    choice,
    recording_directories,
    resolve_choices,
    selected,
)
from custom_components.enigma2_connect.const import DOMAIN
from custom_components.enigma2_connect.models import ReceiverState, Service, Snapshot
from custom_components.enigma2_connect.workflow_models import TimerIdentity

from .conftest import DATA, REFERENCE
from .test_integration import setup


@pytest.mark.parametrize(
    "value,zone,expected",
    [
        ("2026-09-21 18:00:00", "Europe/Berlin", "2026-09-21T16:00:00+00:00"),
        ("2026-12-21 18:00:00", "Europe/Berlin", "2026-12-21T17:00:00+00:00"),
        ("2026-09-21 18:00:00", "America/New_York", "2026-09-21T22:00:00+00:00"),
        ("2026-09-21 18:00:00", "UTC", "2026-09-21T18:00:00+00:00"),
        ("2026-10-25T02:30:00+02:00", "Europe/Berlin", "2026-10-25T00:30:00+00:00"),
        ("2026-10-25T02:30:00+01:00", "Europe/Berlin", "2026-10-25T01:30:00+00:00"),
        ("2026-09-21T16:00:00Z", "Europe/Berlin", "2026-09-21T16:00:00+00:00"),
    ],
)
def test_native_local_times_and_legacy_offsets(value, zone, expected):
    assert action_epoch(value, zone) == int(datetime.fromisoformat(expected).timestamp())
    assert action_epoch(100, zone) == 100
    assert DateTimeSelector()("2026-09-21 18:00:00") == "2026-09-21 18:00:00"


@pytest.mark.parametrize("value", ["2026-10-25 02:30:00", "2027-03-28 02:30:00", "bad", True])
def test_ambiguous_nonexistent_or_invalid_times(value):
    with pytest.raises(ValueError):
        action_epoch(value, "Europe/Berlin")


def test_tokens_are_stable_typed_and_receiver_bound():
    ref = "4097:0:0:0:0:0:0:0:0:0:http%3a//example.test/My Channel"
    token = choice("one", "channel", ref)
    assert selected(token, "one", "channel") == ref
    assert (
        selected(choice("one", "directory", "/media/a folder/"), "one", "directory")
        == "/media/a folder/"
    )
    for bad in (
        "not json",
        "{}",
        "[]",
        "null",
        '["one","channel",1]',
        '["one","channel"," "]',
        choice("other", "channel", ref),
        choice("one", "directory", "/media/"),
    ):
        with pytest.raises(ValueError):
            selected(bad, "one", "channel")
    with pytest.raises(ValueError):
        selected(choice("one", "directory", "relative"), "one", "directory")
    params = {
        "channel": token,
        "directory_selection": choice("one", "directory", "/media/a folder/"),
    }
    resolve_choices(params, "one", "old_service_reference")
    assert params == {"old_service_reference": ref, "directory": "/media/a folder/"}
    direct = {"service_reference": ref, "directory": ""}
    resolve_choices(direct, "one", "service_reference")
    assert direct["directory"] == ""
    for bad in (
        {},
        {"channel": token, "service_reference": ref},
        {
            "service_reference": ref,
            "directory": "",
            "directory_selection": choice("one", "directory", "/media/"),
        },
    ):
        with pytest.raises(ValueError):
            resolve_choices(bad, "one", "service_reference")


def test_only_known_absolute_recording_paths_are_offered():
    data = {
        "locations": ["/media/a/", "/media/a/", None, 12, "relative", "/bad\n"],
        "default": "/media/default/",
        "timers": [{"dirname": "/media/timer/"}, {"dirname": "None"}, None],
    }
    assert recording_directories(data, "/media/movie/") == (
        "/media/a/",
        "/media/default/",
        "/media/movie/",
        "/media/timer/",
    )
    assert recording_directories({"locations": "bad", "timers": "bad"}, None) == ()
    assert recording_directories(None, None) == ()


def base_descriptions():
    path = Path(__file__).resolve().parents[1] / "custom_components" / DOMAIN / "services.yaml"
    return yaml.safe_load(path.read_text())


def test_catalog_changes_failure_and_unload_update_only_choices(hass):
    descriptions = base_descriptions()
    manager = ActionChoices(hass, descriptions)
    listeners = []
    # Coordinator listener removal is synchronous.
    removals = []

    def listen(callback):
        listeners.append(callback)
        return lambda: removals.append(True)

    coordinator = SimpleNamespace(
        entry=SimpleNamespace(entry_id="one", title="Receiver A"),
        last_update_success=True,
        data=Snapshot(
            ReceiverState(False),
            channels={"News": Service(REFERENCE, "News")},
            recording_directories=("/media/a/",),
        ),
        async_add_listener=listen,
    )
    with patch(
        "custom_components.enigma2_connect.action_choices.async_set_service_schema"
    ) as publish:
        remove = manager.bind(coordinator)
        assert publish.call_count == 4
        schema = publish.call_args_list[0].args[3]
        assert (
            schema["fields"]["channel"]["selector"]["select"]["options"][0]["label"]
            == "Receiver A · News"
        )
        assert schema["fields"]["begin"]["selector"] == {"datetime": {}}
        listeners[0]()
        assert publish.call_count == 4
        coordinator.last_update_success = False
        listeners[0]()
        assert (
            publish.call_args_list[-4].args[3]["fields"]["channel"]["selector"]["select"]["options"]
            == []
        )
        coordinator.last_update_success = True
        listeners[0]()
        remove()
        assert removals == [True] and manager.receivers == {}
    assert descriptions == base_descriptions()


async def test_real_ha_descriptions_choices_time_conversion_and_unload(hass, entry, receiver):
    await hass.config.async_set_time_zone("Europe/Berlin")
    receiver[0]["timerlist"].update(locations=["/media/hdd/movie/"], default="/media/default/")
    await setup(hass, entry)
    device = dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id)[0]
    services = (await async_get_all_descriptions(hass))[DOMAIN]
    fields = services["timer_add"]["fields"]
    for field in fields.values():
        validate_selector(field["selector"])
    channel = fields["channel"]["selector"]["select"]["options"][0]["value"]
    directory = fields["directory_selection"]["selector"]["select"]["options"][0]["value"]
    assert fields["begin"]["selector"] == {"datetime": {}}
    data = {
        "device_id": device.id,
        "channel": channel,
        "begin": "2026-09-21 18:00:00",
        "end": "2026-09-21 18:02:00",
        "name": "UI test",
        "directory_selection": directory,
    }
    await hass.services.async_call(DOMAIN, "timer_add", data, blocking=True)
    params = receiver[2].call_args.kwargs
    assert params["sRef"] == REFERENCE and params["begin"] == 1790006400
    assert params["end"] == 1790006520 and params["dirname"] == "/media/default/"
    # Reusing a named choice in YAML stays valid when another bouquet is selected.
    entry.runtime_data.async_set_updated_data(Snapshot(ReceiverState(False)))
    await hass.services.async_call(DOMAIN, "timer_add", data, blocking=True)
    assert await hass.config_entries.async_unload(entry.entry_id)
    descriptions = (await async_get_all_descriptions(hass))[DOMAIN]
    assert descriptions["timer_add"]["fields"]["channel"]["selector"]["select"]["options"] == []
    assert descriptions["timer_add"]["response"] == {"optional": True}


@pytest.mark.parametrize("action", ["timer_toggle", "timer_delete", "timer_edit"])
async def test_channel_alternative_for_existing_timers(hass, entry, receiver, action):
    await setup(hass, entry)
    device = dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id)[0]
    data = {"device_id": device.id, "channel": choice(entry.entry_id, "channel", REFERENCE)}
    if action == "timer_edit":
        data.update(old_begin=100, old_end=200, scope="single", end="2026-09-21 18:00:00")
        with patch.object(
            entry.runtime_data, "async_timer_edit", return_value={"timer": {}}
        ) as edit:
            await hass.services.async_call(DOMAIN, action, data, blocking=True)
            assert edit.call_args.args[0] == TimerIdentity(REFERENCE, 100, 200)
    else:
        data.update(begin=100, end=200)
        await hass.services.async_call(DOMAIN, action, data, blocking=True)
        assert receiver[2].call_args.kwargs["sRef"] == REFERENCE


async def test_wrong_receiver_and_mixed_inputs_never_write(hass, entry, receiver):
    await setup(hass, entry)
    device = dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id)[0]
    data = {"device_id": device.id, "begin": 100, "end": 200, "name": "Test"}
    for fields in (
        {},
        {"channel": choice("other", "channel", REFERENCE)},
        {"channel": choice(entry.entry_id, "channel", REFERENCE), "service_reference": REFERENCE},
        {
            "service_reference": REFERENCE,
            "directory_selection": choice("other", "directory", "/media/"),
        },
        {
            "service_reference": REFERENCE,
            "directory_selection": choice(entry.entry_id, "directory", "/media/"),
            "directory": "/media/",
        },
    ):
        with pytest.raises(ServiceValidationError) as caught:
            await hass.services.async_call(DOMAIN, "timer_add", {**data, **fields}, blocking=True)
        assert caught.value.translation_key == "invalid_action_choice"
    receiver[2].assert_not_awaited()


async def test_clock_change_is_translated_before_writing(hass, entry, receiver):
    await hass.config.async_set_time_zone("Europe/Berlin")
    await setup(hass, entry)
    device = dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id)[0]
    with pytest.raises(ServiceValidationError) as caught:
        await hass.services.async_call(
            DOMAIN,
            "timer_add",
            {
                "device_id": device.id,
                "service_reference": REFERENCE,
                "begin": "2026-10-25 02:30:00",
                "end": "2026-10-25 03:30:00",
                "name": "Ambiguous",
            },
            blocking=True,
        )
    assert caught.value.translation_key == "invalid_time"
    receiver[2].assert_not_awaited()


async def test_two_receiver_lists_keep_choices_bound(hass, entry, receiver):
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
    fields = (await async_get_all_descriptions(hass))[DOMAIN]["timer_add"]["fields"]
    choices = fields["channel"]["selector"]["select"]["options"]
    assert len(choices) == 2
    assert {json.loads(item["value"])[0] for item in choices} == {entry.entry_id, second.entry_id}
    assert await hass.config_entries.async_unload(second.entry_id)
    fields = (await async_get_all_descriptions(hass))[DOMAIN]["timer_add"]["fields"]
    assert len(fields["channel"]["selector"]["select"]["options"]) == 1


async def test_path_catalog_refresh_and_malformed_timer_list(hass, entry, receiver):
    await setup(hass, entry)
    receiver[0]["timerlist"] = {"locations": ["/media/new/"], "timers": "invalid"}
    entry.runtime_data.invalidate_lists()
    await entry.runtime_data.async_refresh()
    assert entry.runtime_data.data.timers is None
    assert "timerlist" in entry.runtime_data.optional_errors
    assert entry.runtime_data.data.recording_directories == ("/media/new/",)
    receiver[0]["timerlist"] = {"timers": []}
    entry.runtime_data.invalidate_lists()
    await entry.runtime_data.async_refresh()
    assert entry.runtime_data.data.recording_directories == ()
    assert "timerlist" not in entry.runtime_data.optional_errors
