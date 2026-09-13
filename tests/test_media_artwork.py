# SPDX-License-Identifier: Apache-2.0
"""Delayed media artwork, cancellation and stale-frame rejection."""

import asyncio
from dataclasses import replace
from unittest.mock import AsyncMock, patch

import pytest

from custom_components.enigma2_connect.media_player import EnigmaMediaPlayer

from .test_integration import setup

MODULE = "custom_components.enigma2_connect.media_player"


@pytest.fixture
async def player(hass, entry, receiver):
    hass.config_entries.async_update_entry(entry, options={"artwork": "screenshot"})
    await setup(hass, entry)
    with patch(MODULE + ".monotonic", return_value=100):
        player = EnigmaMediaPlayer(entry.runtime_data)
    player.async_write_ha_state = lambda: None
    return player


def change_channel(player, reference):
    coordinator = player.coordinator
    coordinator.data = replace(
        coordinator.data, state=replace(coordinator.data.state, reference=reference)
    )
    player._handle_coordinator_update()


async def test_capture_waits_for_settle_window(player):
    order = []

    async def wait(delay):
        assert delay == 1
        order.append("wait")

    async def capture():
        assert order == ["wait"]
        return b"new frame"

    with (
        patch(MODULE + ".monotonic", return_value=100),
        patch(MODULE + ".sleep", side_effect=wait),
        patch.object(player.coordinator.client, "screenshot", side_effect=capture),
    ):
        assert await player.async_get_media_image() == (b"new frame", "image/jpeg")


async def test_settled_channel_has_no_extra_delay(player):
    with (
        patch(MODULE + ".monotonic", return_value=102),
        patch(MODULE + ".sleep", new_callable=AsyncMock) as wait,
        patch.object(player.coordinator.client, "screenshot", return_value=b"image"),
    ):
        assert await player.async_get_media_image() == (b"image", "image/jpeg")
        wait.assert_not_awaited()


async def test_rapid_zap_while_waiting_does_not_capture_for_old_request(player):
    async def wait(delay):
        change_channel(player, "1:0:1:other")

    with (
        patch(MODULE + ".monotonic", return_value=100),
        patch(MODULE + ".sleep", side_effect=wait),
        patch.object(player.coordinator.client, "screenshot", new_callable=AsyncMock) as capture,
    ):
        assert await player.async_get_media_image() == (None, None)
        capture.assert_not_awaited()


async def test_zap_during_capture_discards_obsolete_frame(player):
    async def capture():
        change_channel(player, "1:0:1:other")
        return b"old frame"

    with (
        patch(MODULE + ".monotonic", return_value=102),
        patch.object(player.coordinator.client, "screenshot", side_effect=capture),
    ):
        assert await player.async_get_media_image() == (None, None)


async def test_revisit_and_reload_do_not_reuse_old_screenshot_cache_key(player):
    original = player.media_content_id
    first = player.media_image_hash
    with patch(MODULE + ".monotonic", return_value=102):
        player._handle_coordinator_update()
        assert player.media_image_hash == first
        change_channel(player, "1:0:1:other")
        other = player.media_image_hash
        change_channel(player, original)
        assert len({first, other, player.media_image_hash}) == 3
    reloaded = EnigmaMediaPlayer(player.coordinator)
    assert reloaded.media_image_hash != player.media_image_hash


async def test_picon_is_not_delayed_or_invalidated_on_revisit(player):
    player.coordinator.hass.config_entries.async_update_entry(
        player.coordinator.entry, options={"artwork": "picon"}
    )
    original = player.media_content_id
    first = player.media_image_hash
    change_channel(player, "1:0:1:other")
    change_channel(player, original)
    assert player.media_image_hash == first
    with (
        patch(MODULE + ".sleep", new_callable=AsyncMock) as wait,
        patch.object(player.coordinator.client, "picon", return_value=b"logo"),
    ):
        assert await player.async_get_media_image() == (b"logo", "image/png")
        wait.assert_not_awaited()


async def test_cancelled_wait_never_sends_capture(player):
    with (
        patch(MODULE + ".monotonic", return_value=100),
        patch(MODULE + ".sleep", side_effect=asyncio.CancelledError),
        patch.object(player.coordinator.client, "screenshot", new_callable=AsyncMock) as capture,
    ):
        with pytest.raises(asyncio.CancelledError):
            await player.async_get_media_image()
        capture.assert_not_awaited()


@pytest.mark.parametrize("change", ["standby", "unavailable", "disabled_artwork"])
async def test_state_change_while_waiting_skips_capture(player, change):
    async def wait(delay):
        coordinator = player.coordinator
        if change == "standby":
            coordinator.data = replace(
                coordinator.data, state=replace(coordinator.data.state, standby=True)
            )
            player._handle_coordinator_update()
        elif change == "unavailable":
            coordinator.last_update_success = False
        else:
            coordinator.hass.config_entries.async_update_entry(
                coordinator.entry, options={"artwork": "none"}
            )

    with (
        patch(MODULE + ".monotonic", return_value=100),
        patch(MODULE + ".sleep", side_effect=wait),
        patch.object(player.coordinator.client, "screenshot", new_callable=AsyncMock) as capture,
    ):
        assert await player.async_get_media_image() == (None, None)
        capture.assert_not_awaited()
