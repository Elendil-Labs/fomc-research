"""FOMC decision calendar + Fed communications-blackout date math.

Python port of the dashboard's src/lib/fomcSchedule.ts. All comparisons are done on
ISO yyyy-mm-dd calendar dates (UTC), never local wall-clock time.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

# Scheduled FOMC decision (second/announcement) days.
# NOTE: extend this list when the Fed publishes the 2027 calendar.
FOMC_DECISION_DATES: tuple[str, ...] = (
    "2026-01-28",
    "2026-03-18",
    "2026-04-29",
    "2026-06-17",
    "2026-07-29",
    "2026-09-16",
    "2026-10-28",
    "2026-12-09",
)

CALENDAR_NOTE = "Schedule covers 2026 only; extend FOMC_DECISION_DATES for 2027."

_SATURDAY = 5  # date.weekday(): Mon=0 .. Sat=5, Sun=6
_THURSDAY = 3


def today_utc() -> date:
    return datetime.now(timezone.utc).date()


def blackout_start(decision_iso: str) -> str:
    """Second Saturday STRICTLY before the decision date.

    e.g. decision 2026-07-29 (Wed) -> Saturdays 07-25, 07-18 -> returns 2026-07-18.
    """
    cursor = date.fromisoformat(decision_iso) - timedelta(days=1)
    saturdays = 0
    while True:
        if cursor.weekday() == _SATURDAY:
            saturdays += 1
            if saturdays == 2:
                return cursor.isoformat()
        cursor -= timedelta(days=1)


def blackout_end(decision_iso: str) -> str:
    """First Thursday STRICTLY after the decision date.

    e.g. decision 2026-07-29 (Wed) -> 2026-07-30 (Thu).
    """
    cursor = date.fromisoformat(decision_iso) + timedelta(days=1)
    while cursor.weekday() != _THURSDAY:
        cursor += timedelta(days=1)
    return cursor.isoformat()


def in_blackout(today: date, decision_iso: str) -> bool:
    """True when `today` falls inside the blackout window, endpoints inclusive."""
    t = today.isoformat()
    return blackout_start(decision_iso) <= t <= blackout_end(decision_iso)


def next_fomc(today: date) -> str | None:
    """First scheduled decision date on/after `today`, or None if the schedule ran out."""
    t = today.isoformat()
    for d in FOMC_DECISION_DATES:
        if d >= t:
            return d
    return None


def days_until(iso: str, today: date) -> int:
    """Whole calendar days from `today` until the ISO date. Negative if past."""
    return (date.fromisoformat(iso) - today).days
