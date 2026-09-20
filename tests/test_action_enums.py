# SPDX-License-Identifier: Apache-2.0
"""Named action options keep their existing numeric wire values and defaults."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest
import voluptuous as vol
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.selector import SelectSelector, validate_selector
from homeassistant.helpers.service import async_get_all_descriptions

from custom_components.enigma2_connect.const import DOMAIN

from .conftest import REFERENCE
from .test_integration import setup


async def test_named_options_and_legacy_integers_share_wire_values(hass, entry, receiver):
    await setup(hass, entry)
    device = dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id)[0]
    timer = {
        "device_id": device.id,
        "service_reference": REFERENCE,
        "begin": 100,
        "end": 200,
        "name": "Test",
    }
    editing = {
        "device_id": device.id,
        "old_service_reference": REFERENCE,
        "old_begin": 100,
        "old_end": 200,
        "scope": "single",
    }
    for value in (0, 1, 2, 3, "0", "1", "2", "3"):
        await hass.services.async_call(
            DOMAIN,
            "message",
            {"device_id": device.id, "text": "Test", "type": value},
            blocking=True,
        )
        assert receiver[2].call_args.kwargs["type"] == int(value)
        await hass.services.async_call(
            DOMAIN, "timer_add", {**timer, "afterevent": value}, blocking=True
        )
        assert receiver[2].call_args.kwargs["afterevent"] == int(value)
        with patch.object(entry.runtime_data, "async_timer_edit", return_value={}) as edit:
            await hass.services.async_call(
                DOMAIN, "timer_edit", {**editing, "afterevent": value}, blocking=True
            )
            assert edit.call_args.args[1]["afterevent"] == int(value)
    await hass.services.async_call(
        DOMAIN, "message", {"device_id": device.id, "text": "Test"}, blocking=True
    )
    assert receiver[2].call_args.kwargs["type"] == 1
    await hass.services.async_call(DOMAIN, "timer_add", timer, blocking=True)
    assert receiver[2].call_args.kwargs["afterevent"] == 3
    with patch.object(entry.runtime_data, "async_timer_edit", return_value={}) as edit:
        await hass.services.async_call(DOMAIN, "timer_edit", editing, blocking=True)
        assert "afterevent" not in edit.call_args.args[1]
    for value in (-1, 4, "warning", "1.0", 1.5):
        with pytest.raises(vol.Invalid):
            await hass.services.async_call(
                DOMAIN,
                "message",
                {"device_id": device.id, "text": "Test", "type": value},
                blocking=True,
            )
        with pytest.raises(vol.Invalid):
            await hass.services.async_call(
                DOMAIN, "timer_add", {**timer, "afterevent": value}, blocking=True
            )


async def test_enum_selectors_have_translated_labels(hass, entry, receiver):
    await setup(hass, entry)
    services = (await async_get_all_descriptions(hass))[DOMAIN]
    root = Path(__file__).resolve().parents[1] / "custom_components" / DOMAIN
    for action, field, key in [
        ("message", "type", "message_type"),
        ("timer_add", "afterevent", "after_recording"),
        ("timer_edit", "afterevent", "after_recording"),
    ]:
        selector = services[action]["fields"][field]["selector"]
        validate_selector(selector)
        assert selector["select"]["translation_key"] == key
        assert selector["select"]["options"] == ["0", "1", "2", "3"]
        assert SelectSelector(selector["select"])("2") == "2"
        for lang in ("de", "en"):
            labels = json.loads((root / f"translations/{lang}.json").read_text())["selector"][key][
                "options"
            ]
            assert set(labels) == {"0", "1", "2", "3"}
            assert all(labels.values())
