# SPDX-License-Identifier: Apache-2.0
"""A timer calendar. Repeated receiver timers are expanded in receiver local time."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.util import dt as dt_util

from .entity import EnigmaEntity
from .models import boolean

PARALLEL_UPDATES = 0


def _local_time_exists(value: datetime) -> bool:
    """Reject wall times skipped by an offset transition."""
    restored = datetime.fromtimestamp(value.timestamp(), value.tzinfo)
    return restored.replace(tzinfo=None) == value.replace(tzinfo=None)


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([EnigmaCalendar(entry.runtime_data, "calendar")])


class EnigmaCalendar(EnigmaEntity, CalendarEntity):
    @property
    def available(self):
        return super().available and self.coordinator.data.timers is not None

    def events(self, lower, upper):
        lower_stamp, upper_stamp = lower.timestamp(), upper.timestamp()
        if upper_stamp <= lower_stamp:
            return []
        zone = ZoneInfo(
            self.coordinator.entry.options.get("receiver_timezone", self.hass.config.time_zone)
        )
        events = []
        for timer in self.coordinator.data.timers or []:
            if not isinstance(timer, dict) or boolean(timer.get("disabled")) is True:
                continue
            try:
                begin = datetime.fromtimestamp(int(timer["begin"]), zone)
                end = datetime.fromtimestamp(int(timer["end"]), zone)
                repeated = int(timer.get("repeated", 0))
            except KeyError, TypeError, ValueError, OverflowError, OSError:
                continue
            # Same-zone datetime comparisons ignore fold during the repeated hour.
            # Receiver epochs, not wall-clock ordering, determine validity.
            if end.timestamp() <= begin.timestamp():
                continue
            occurrences = [(begin, end)]
            if repeated:
                occurrences = []
                # Recurrences follow receiver wall time across offset changes.
                duration = end.replace(tzinfo=None) - begin.replace(tzinfo=None)
                if duration <= timedelta(0):
                    # A concrete timer can cross backwards through the repeated hour.
                    # Use its elapsed duration when no positive wall duration exists.
                    duration = timedelta(seconds=end.timestamp() - begin.timestamp())
                day = max(begin.date(), (lower.astimezone(zone) - duration).date())
                while day <= upper.astimezone(zone).date():
                    # Enigma2 encodes weekdays as a bitmask starting with Monday.
                    if repeated & (1 << day.weekday()):
                        if day == begin.date():
                            # Preserve the concrete occurrence reported by the receiver,
                            # including an explicit second occurrence of the repeated hour.
                            occurrences.append((begin, end))
                        else:
                            start = datetime.combine(day, begin.timetz().replace(fold=0))
                            stop = start + duration
                            if (
                                _local_time_exists(start)
                                and _local_time_exists(stop)
                                and stop.timestamp() > start.timestamp()
                            ):
                                occurrences.append((start, stop))
                    day += timedelta(days=1)
            for start, stop in occurrences:
                if start.timestamp() < upper_stamp and stop.timestamp() > lower_stamp:
                    events.append(
                        CalendarEvent(
                            start=start,
                            end=stop,
                            summary=timer.get("name") or "Timer",
                            description=timer.get("description") or "",
                            uid=f"{timer.get('serviceref', '')}:{timer['begin']}:{int(start.timestamp())}",
                        )
                    )
        return sorted(events, key=lambda event: event.start.timestamp())

    @property
    def event(self):
        now = dt_util.utcnow()
        events = self.events(now, now + timedelta(days=8))
        if events:
            return events[0]
        # A one-shot timer may be further in the future.
        return next(iter(self.events(now, now + timedelta(days=366))), None)

    async def async_get_events(self, hass, start_date, end_date):
        return self.events(start_date, end_date)
