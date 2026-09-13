# SPDX-License-Identifier: Apache-2.0
"""Real Home Assistant fixtures and a receiver transport double."""

from copy import deepcopy
from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.enigma2_connect.const import DOMAIN

pytest_plugins = "pytest_homeassistant_custom_component"

REFERENCE = "1:0:1:6DD2:44D:1:C00000:0:0:0:"
BOUQUET = '1:7:1:0:0:0:0:0:0:0:FROM BOUQUET "userbouquet.favourites.tv" ORDER BY bouquet'
DATA = {
    "host": "receiver.local",
    "port": 80,
    "username": "root",
    "password": "secret",
    "use_https": False,
    "verify_ssl": True,
}
RESPONSES = {
    "about": {
        "info": {
            "model": "Test Receiver",
            "brand": "Example",
            "webifver": "1.5.2",
            "ifaces": [{"mac": "AA:BB:CC:DD:EE:FF"}],
        }
    },
    "statusinfo": {
        "inStandby": "false",
        "volume": 25,
        "muted": False,
        "currservice_station": "Channel",
        "currservice_name": "News",
        "currservice_serviceref": REFERENCE,
        "isRecording": "false",
        "isStreaming": "true",
    },
    "getcurrent": {"now": {"title": "News"}, "next": {"title": "Next news"}},
    "signal": {"snr": 80, "snr_db": "12.5", "ber": 0},
    "bouquets": {"bouquets": [[BOUQUET, "Favorites"]]},
    "getservices": {"services": [{"servicereference": REFERENCE, "servicename": "Channel"}]},
    "timerlist": {"timers": []},
    "movielist": {"movies": []},
}


@pytest.fixture(autouse=True)
def custom_integration(enable_custom_integrations):
    yield


@pytest.fixture
def entry(hass):
    entry = MockConfigEntry(
        domain=DOMAIN, title="Test Receiver", unique_id="aabbccddeeff", data=DATA
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
def receiver():
    replies = deepcopy(RESPONSES)

    async def get(endpoint, **params):
        value = replies[endpoint]
        if isinstance(value, Exception):
            raise value
        return deepcopy(value)

    with (
        # Background artwork is exercised explicitly in test_recording_preparation.
        patch("custom_components.enigma2_connect.recording_images.BACKGROUND_DELAY", 3600),
        patch(
            "custom_components.enigma2_connect.api.OpenWebifClient.get", side_effect=get
        ) as get_mock,
        patch(
            "custom_components.enigma2_connect.api.OpenWebifClient.command", new_callable=AsyncMock
        ) as command,
        patch(
            "custom_components.enigma2_connect.api.OpenWebifClient.keys", new_callable=AsyncMock
        ) as keys,
    ):
        yield replies, get_mock, command, keys
