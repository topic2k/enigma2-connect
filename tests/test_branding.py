# SPDX-License-Identifier: Apache-2.0
"""Serve the shipped custom-integration artwork through HA's real brands API."""

import json
from io import BytesIO
from pathlib import Path
from unittest.mock import AsyncMock, patch

from homeassistant.setup import async_setup_component
from PIL import Image

from custom_components.enigma2_connect.const import DOMAIN


def test_icon_keys_match_the_entity_translation_catalog():
    component = Path(__file__).resolve().parents[1] / "custom_components" / DOMAIN
    icons = json.loads((component / "icons.json").read_text())["entity"]
    entities = json.loads((component / "strings.json").read_text())["entity"]
    for platform, descriptions in icons.items():
        assert set(descriptions) <= entities[platform].keys()
        assert all(
            description["default"].startswith("mdi:") for description in descriptions.values()
        )
    assert "connection" not in icons["binary_sensor"]  # Keep the device-class icon.


async def test_local_brand_images_are_served_without_cdn(hass, hass_client):
    assert await async_setup_component(hass, "brands", {})
    client = await hass_client()
    brand = Path(__file__).resolve().parents[1] / "custom_components" / DOMAIN / "brand"
    files = await hass.async_add_executor_job(
        lambda: {path.name: path.read_bytes() for path in brand.glob("*.png")}
    )
    assert len(files) == 8
    with patch(
        "homeassistant.components.brands._BrandsBaseView._fetch_and_cache", new_callable=AsyncMock
    ) as cdn:
        for filename, content in files.items():
            response = await client.get(f"/api/brands/integration/{DOMAIN}/{filename}")
            assert response.status == 200
            assert response.content_type == "image/png"
            assert await response.read() == content
            with Image.open(BytesIO(content)) as image:
                assert image.format == "PNG"
                assert image.mode == "RGBA"
                if "icon" in filename:
                    assert image.size == ((512, 512) if "@2x" in filename else (256, 256))
                else:
                    assert (
                        256 <= min(image.size) <= 512
                        if "@2x" in filename
                        else 128 <= min(image.size) <= 256
                    )
        cdn.assert_not_awaited()
