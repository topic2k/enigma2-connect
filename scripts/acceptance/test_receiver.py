# SPDX-License-Identifier: Apache-2.0
"""Explicit hardware entry point; excluded from normal testpaths and CI."""

from unittest.mock import patch

import pytest
import pytest_socket

from custom_components.enigma2_connect.api import OpenWebifClient
from scripts.receiver_acceptance import check_receiver, check_request

pytest_plugins = "pytest_homeassistant_custom_component"


async def test_receiver(hass, enable_custom_integrations, hass_storage, socket_enabled, request):
    try:
        config, report = request.getfixturevalue("receiver_acceptance_session")
    except pytest.FixtureLookupError:
        pytest.skip("Use scripts/receiver_acceptance.py to explicitly select a receiver")
    pytest_socket.socket_allow_hosts([config["host"], "127.0.0.1", "::1"])
    original = OpenWebifClient.request
    report["read_requests"] = 0

    async def readonly(client, path, params=None, **kwargs):
        check_request(path, params)
        report["read_requests"] += 1
        return await original(client, path, params, **kwargs)

    with (
        patch.object(OpenWebifClient, "request", readonly),
        patch("custom_components.enigma2_connect.recording_images.BACKGROUND_DELAY", 3600),
    ):
        await check_receiver(hass, config, report)
