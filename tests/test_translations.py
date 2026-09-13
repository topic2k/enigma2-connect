# SPDX-License-Identifier: Apache-2.0
"""Verify localization through Home Assistant and keep catalogs in sync."""

import json
from pathlib import Path
from string import Formatter

import pytest
from homeassistant.components import media_source
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.translation import async_get_translations
from homeassistant.setup import async_setup_component

from custom_components.enigma2_connect.const import DOMAIN
from custom_components.enigma2_connect.media_player import EnigmaMediaPlayer
from custom_components.enigma2_connect.remote import key_codes

from .test_integration import setup

ROOT = Path(__file__).resolve().parents[1] / "custom_components" / DOMAIN


def flatten(value, prefix=""):
    return {
        key: leaf
        for name, child in value.items()
        for key, leaf in (
            flatten(child, f"{prefix}.{name}").items()
            if isinstance(child, dict)
            else [(f"{prefix}.{name}", child)]
        )
    }


def test_translation_keys_and_placeholders_match():
    english = json.loads((ROOT / "translations/en.json").read_text(encoding="utf-8"))
    assert english == json.loads((ROOT / "strings.json").read_text(encoding="utf-8"))
    source = flatten(english)
    for language in ("de", "en"):
        translated = flatten(
            json.loads((ROOT / f"translations/{language}.json").read_text(encoding="utf-8"))
        )
        assert translated.keys() == source.keys()
        for key, value in translated.items():
            assert isinstance(value, str) and value.strip(), key
            assert "[%key:" not in value, key
            assert {field for _, field, _, _ in Formatter().parse(value) if field} == {
                field for _, field, _, _ in Formatter().parse(source[key]) if field
            }, key


@pytest.mark.parametrize(
    ("language", "tile", "fallback", "artwork", "error"),
    [
        (
            "de",
            "Enigma2-Aufnahmen",
            "Aufnahme",
            "Kein Bild",
            "Unbekannte Fernbedienungstaste: nope",
        ),
        ("en", "Enigma2 recordings", "Recording", "No artwork", "Unknown remote key: nope"),
        ("fr", "Enigma2 recordings", "Recording", "No artwork", "Unknown remote key: nope"),
    ],
)
async def test_localized_media_options_and_errors(
    hass, entry, receiver, language, tile, fallback, artwork, error
):
    hass.config.language = language
    receiver[0]["movielist"] = {"movies": [{"serviceref": "1:0:0:0:0:0:0:0:0:0:"}]}
    await setup(hass, entry)
    assert await async_setup_component(hass, "media_source", {})
    await hass.async_block_till_done()
    sources = await media_source.async_browse_media(hass, None)
    source = next(
        child for child in sources.children if child.media_content_id == f"media-source://{DOMAIN}"
    )
    assert source.title == tile
    root = await media_source.async_browse_media(hass, source.media_content_id)
    assert root.title == tile
    folder = await media_source.async_browse_media(hass, root.children[0].media_content_id)
    assert folder.children[0].title == fallback
    player = EnigmaMediaPlayer(entry.runtime_data)
    player.hass = hass
    assert (await player.async_browse_media()).children[0].title == fallback
    with pytest.raises(ServiceValidationError) as raised:
        key_codes(["nope"])
    exception = raised.value
    assert exception.translation_domain == DOMAIN
    exceptions = await async_get_translations(hass, language, "exceptions", {DOMAIN})
    template = exceptions[f"component.{DOMAIN}.exceptions.{exception.translation_key}.message"]
    assert template.format(**exception.translation_placeholders) == error
    selector = await async_get_translations(hass, language, "selector", {DOMAIN})
    assert selector[f"component.{DOMAIN}.selector.artwork.options.none"] == artwork
    options = await async_get_translations(hass, language, "options", {DOMAIN})
    assert options[f"component.{DOMAIN}.options.step.init.menu_options.regenerate_images"] == (
        "Vorschaubilder neu generieren" if language == "de" else "Regenerate thumbnails"
    )
    flow = await hass.config_entries.options.async_init(entry.entry_id)
    flow = await hass.config_entries.options.async_configure(
        flow["flow_id"], {"next_step_id": "settings"}
    )
    selectors = {str(key): value for key, value in flow["data_schema"].schema.items()}
    for key, values in {
        "artwork": ["picon", "screenshot", "none"],
        "off_mode": ["standby", "deep_standby"],
    }.items():
        assert selectors[key].config["translation_key"] == key
        assert selectors[key].config["options"] == values
        for value in values:
            assert selectors[key](value) == value
