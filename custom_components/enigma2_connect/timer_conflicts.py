# SPDX-License-Identifier: Apache-2.0
"""Project receiver conflict replies for translated errors and automation events."""

from datetime import UTC, datetime

from .models import JsonObject
from .workflow_models import DataFormatError, TimerConflict, parse_list


def conflicts(response: JsonObject) -> list[JsonObject]:
    try:
        parsed = parse_list(response, "conflicts", TimerConflict.parse)
    except DataFormatError:
        return []
    return [
        {**item.identity.response(), "name": item.name, "service_name": item.service_name}
        for item in parsed
    ]


def summary(items: list[JsonObject]) -> str:
    parts = []
    for item in items[:5]:
        # Keep receiver text bounded and single-line; never expose raw response fields.
        title = " ".join((item["name"] or "—").split())[:100]
        channel = " ".join((item["service_name"] or "—").split())[:80]
        try:
            begin = datetime.fromtimestamp(item["begin"], UTC).isoformat()
            end = datetime.fromtimestamp(item["end"], UTC).isoformat()
        except ValueError, OverflowError, OSError:
            begin, end = str(item["begin"]), str(item["end"])
        parts.append(f"{title} ({channel}, {begin} – {end})")
    if len(items) > 5:
        parts.append(f"+{len(items) - 5}")
    return "; ".join(parts)
