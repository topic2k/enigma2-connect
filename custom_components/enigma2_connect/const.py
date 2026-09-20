# SPDX-License-Identifier: Apache-2.0
"""Integration constants and standard Linux input key codes."""

DOMAIN = "enigma2_connect"
DEFAULT_INTERVAL = 15
SLOW_INTERVAL = 120
CATALOG_INTERVAL = 300
DIAGNOSTICS_INTERVAL = 300
KEYS = {
    **{str(n): n + 1 for n in range(1, 10)},
    "0": 11,
    "power": 116,
    "up": 103,
    "down": 108,
    "left": 105,
    "right": 106,
    "ok": 352,
    "menu": 139,
    "exit": 174,
    "red": 398,
    "green": 399,
    "yellow": 400,
    "blue": 401,
    "info": 358,
    "epg": 365,
    "help": 138,
    "audio": 392,
    "subtitle": 370,
    "text": 388,
    "tv": 377,
    "radio": 385,
    "favorites": 364,
    "play": 207,
    "pause": 119,
    "stop": 128,
    "record": 167,
    "fast_forward": 208,
    "rewind": 168,
    "next": 407,
    "previous": 412,
    "channel_up": 402,
    "channel_down": 403,
    "volume_up": 115,
    "volume_down": 114,
    "mute": 113,
}
