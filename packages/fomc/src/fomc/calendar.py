"""The FOMC meeting calendar — the single source of truth for this repo.

Everything that needs a meeting date reads this module:

  * the fomc-intel MCP server (`fomc_server._calendar` re-exports these names)
  * `scripts/score_regime_intel.py` / the refresh workflow (`--next-fomc`)
  * the static dashboard, via the JSON exported by `fomc export-calendar` into
    `apps/fomc-dashboard/public/data/fomc_calendar.json`

Two kinds of meeting are represented:

  * ``kind="decision"`` — a regular two-day meeting that announces a policy decision
    on its second day. These are the only meetings that count as "decision dates".
  * ``kind="strategy"`` — a two-day meeting dedicated to broad monetary-policy strategy
    issues, with NO policy decision and no statement. The Fed's November 12, 2026
    release flags the October 26-27, 2027 meeting this way, and Chair Warsh confirmed
    at the October 28, 2026 press conference that it carries no decision.

The Fed's external-communications blackout applies to ALL FOMC meetings, strategy
meetings included, so ``blackout_start``/``blackout_end`` are defined for every
meeting; only the *decision* lookups (`next_decision`, `DECISION_DATES`) skip the
strategy meeting. Blackout math is unchanged from the original implementation:
second Saturday strictly before the meeting's second day through the first Thursday
strictly after it.

All comparisons are done on ISO yyyy-mm-dd calendar dates (UTC), never local
wall-clock time.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any, Literal

MeetingKind = Literal["decision", "strategy"]

# Press release carrying the 2027 + January 2028 schedule.
SOURCE_2027 = "https://www.federalreserve.gov/newsevents/pressreleases/monetary20261112a.htm"
PUBLISHED_2027 = "2026-11-12"

# The 2026 dates predate this module; the Fed's rolling calendar page is their home.
SOURCE_2026 = "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm"


@dataclass(frozen=True, slots=True)
class FomcMeeting:
    """One scheduled FOMC meeting.

    ``start``/``end`` are the two meeting days. ``decision_date`` is ``end`` for a
    regular meeting and ``None`` for a strategy meeting — reading the policy date off
    this property is what keeps strategy meetings out of decision logic by
    construction.
    """

    start: str
    end: str
    kind: MeetingKind
    source_url: str
    published: str | None = None

    @property
    def decision_date(self) -> str | None:
        return self.end if self.kind == "decision" else None

    @property
    def blackout_start(self) -> str:
        return blackout_start(self.end)

    @property
    def blackout_end(self) -> str:
        return blackout_end(self.end)

    def to_dict(self) -> dict[str, Any]:
        return {
            "start": self.start,
            "end": self.end,
            "kind": self.kind,
            "decision_date": self.decision_date,
            "blackout_start": self.blackout_start,
            "blackout_end": self.blackout_end,
            "source_url": self.source_url,
            "published": self.published,
        }


def _decision(start: str, end: str, source_url: str, published: str | None) -> FomcMeeting:
    return FomcMeeting(start=start, end=end, kind="decision", source_url=source_url,
                       published=published)


# Ascending by `end`. Extend here when the Fed publishes a new calendar, and move the
# horizon warning along with it (see `schedule_warning`).
MEETINGS: tuple[FomcMeeting, ...] = (
    _decision("2026-01-27", "2026-01-28", SOURCE_2026, None),
    _decision("2026-03-17", "2026-03-18", SOURCE_2026, None),
    _decision("2026-04-28", "2026-04-29", SOURCE_2026, None),
    _decision("2026-06-16", "2026-06-17", SOURCE_2026, None),
    _decision("2026-07-28", "2026-07-29", SOURCE_2026, None),
    _decision("2026-09-15", "2026-09-16", SOURCE_2026, None),
    _decision("2026-10-27", "2026-10-28", SOURCE_2026, None),
    _decision("2026-12-08", "2026-12-09", SOURCE_2026, None),
    _decision("2027-01-26", "2027-01-27", SOURCE_2027, PUBLISHED_2027),
    _decision("2027-03-16", "2027-03-17", SOURCE_2027, PUBLISHED_2027),
    _decision("2027-04-27", "2027-04-28", SOURCE_2027, PUBLISHED_2027),
    _decision("2027-06-08", "2027-06-09", SOURCE_2027, PUBLISHED_2027),
    _decision("2027-07-27", "2027-07-28", SOURCE_2027, PUBLISHED_2027),
    _decision("2027-09-14", "2027-09-15", SOURCE_2027, PUBLISHED_2027),
    # Dedicated to broad monetary-policy strategy issues: no policy decision, no
    # statement. Blackout still applies.
    FomcMeeting("2027-10-26", "2027-10-27", "strategy", SOURCE_2027, PUBLISHED_2027),
    _decision("2027-11-16", "2027-11-17", SOURCE_2027, PUBLISHED_2027),
    # No December 2027 meeting: the 2027 cycle ends in November.
    _decision("2028-01-25", "2028-01-26", SOURCE_2027, PUBLISHED_2027),
)

#: Policy-decision dates only (strategy meetings excluded), ascending.
DECISION_DATES: tuple[str, ...] = tuple(
    m.decision_date for m in MEETINGS if m.decision_date is not None
)

#: Backwards-compatible alias for the name the server and dashboard used to own.
FOMC_DECISION_DATES = DECISION_DATES

#: Warn when the last scheduled decision is closer than this (days).
SCHEDULE_HORIZON_DAYS = 120

SCHEDULE_WARNING = (
    "schedule needs extending: the last scheduled FOMC decision is {days} days away "
    "({last}). Add the Fed's next published calendar to fomc.calendar.MEETINGS."
)

_SATURDAY = 5  # date.weekday(): Mon=0 .. Sat=5, Sun=6
_THURSDAY = 3


def today_utc() -> date:
    return datetime.now(timezone.utc).date()


def blackout_start(meeting_end_iso: str) -> str:
    """Second Saturday STRICTLY before the meeting's second day.

    e.g. decision 2026-07-29 (Wed) -> Saturdays 07-25, 07-18 -> returns 2026-07-18.
    """
    cursor = date.fromisoformat(meeting_end_iso) - timedelta(days=1)
    saturdays = 0
    while True:
        if cursor.weekday() == _SATURDAY:
            saturdays += 1
            if saturdays == 2:
                return cursor.isoformat()
        cursor -= timedelta(days=1)


def blackout_end(meeting_end_iso: str) -> str:
    """First Thursday STRICTLY after the meeting's second day.

    e.g. decision 2026-07-29 (Wed) -> 2026-07-30 (Thu).
    """
    cursor = date.fromisoformat(meeting_end_iso) + timedelta(days=1)
    while cursor.weekday() != _THURSDAY:
        cursor += timedelta(days=1)
    return cursor.isoformat()


def in_blackout(today: date, meeting_end_iso: str) -> bool:
    """True when `today` falls inside the blackout window, endpoints inclusive."""
    t = today.isoformat()
    return blackout_start(meeting_end_iso) <= t <= blackout_end(meeting_end_iso)


def next_decision(today: date) -> str | None:
    """First scheduled DECISION date on/after `today`, or None if the schedule ran out.

    Strategy meetings are skipped: they announce nothing.
    """
    t = today.isoformat()
    for d in DECISION_DATES:
        if d >= t:
            return d
    return None


#: Backwards-compatible alias (the old server/dashboard name).
next_fomc = next_decision


def next_meeting(today: date, kind: MeetingKind | None = None) -> FomcMeeting | None:
    """First scheduled meeting whose second day is on/after `today`.

    `kind=None` considers every meeting; pass "strategy" to find the next
    non-decision meeting.
    """
    t = today.isoformat()
    for m in MEETINGS:
        if m.end >= t and (kind is None or m.kind == kind):
            return m
    return None


def last_decision() -> str:
    """Last policy-decision date currently in the schedule."""
    return DECISION_DATES[-1]


def days_until(iso: str, today: date) -> int:
    """Whole calendar days from `today` until the ISO date. Negative if past."""
    return (date.fromisoformat(iso) - today).days


def schedule_warning(today: date) -> str | None:
    """A "schedule needs extending" string once the horizon gets short, else None.

    Fires when the LAST scheduled decision is fewer than SCHEDULE_HORIZON_DAYS days
    away (including after it has passed), so the calendar gets topped up before the
    dashboard and the MCP tools run out of meetings.
    """
    last = last_decision()
    days = days_until(last, today)
    if days < SCHEDULE_HORIZON_DAYS:
        return SCHEDULE_WARNING.format(days=days, last=last)
    return None


def provenance(today: date | None = None) -> dict[str, Any]:
    """Where the schedule came from, and whether it needs extending."""
    today = today or today_utc()
    return {
        "sources": [
            {"url": SOURCE_2027, "published": PUBLISHED_2027,
             "covers": "2027 meetings + January 25-26, 2028"},
            {"url": SOURCE_2026, "published": None, "covers": "2026 meetings"},
        ],
        "coverage": {
            "first_decision": DECISION_DATES[0],
            "last_decision": last_decision(),
            "n_decisions": len(DECISION_DATES),
            "n_strategy_meetings": sum(1 for m in MEETINGS if m.kind == "strategy"),
        },
        "horizon_days": SCHEDULE_HORIZON_DAYS,
        "schedule_warning": schedule_warning(today),
    }


def calendar_document(today: date | None = None) -> dict[str, Any]:
    """The JSON document the dashboard fetches (see `fomc export-calendar`)."""
    today = today or today_utc()
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "as_of": today.isoformat(),
        "meetings": [m.to_dict() for m in MEETINGS],
        "decision_dates": list(DECISION_DATES),
        "next_decision": next_decision(today),
        "provenance": provenance(today),
    }
