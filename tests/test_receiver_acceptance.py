# SPDX-License-Identifier: Apache-2.0
"""Verify the manual acceptance and its command barrier with simulated responses."""

import pytest

from scripts.receiver_acceptance import check_receiver, check_request

from .conftest import DATA


@pytest.mark.parametrize(
    ("path", "params"),
    [
        ("/api/powerstate", {"newstate": 1}),
        ("/api/vol", {"set": "mute"}),
        ("/api/timerdelete", {}),
        ("/api/statusinfo", {"unexpected": "value"}),
        ("/grab", {}),
    ],
)
def test_mutations_and_unplanned_requests_blocked(path, params):
    with pytest.raises(RuntimeError, match="blocked"):
        check_request(path, params)


async def test_acceptance_with_simulated_receiver(hass, receiver):
    respond = receiver[1].side_effect

    async def guarded(endpoint, **params):
        check_request(f"/api/{endpoint}", params)
        return await respond(endpoint, **params)

    receiver[1].side_effect = guarded
    report = {}
    await check_receiver(hass, DATA, report)
    assert report["stage"] == "complete"
    assert report["unloaded"]
    assert report["disabled_signal_entities"] == 3
    assert all(secret not in str(report) for secret in ("receiver.local", "secret", "aabbcc"))
