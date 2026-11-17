"""FOMC decision calendar + Fed communications-blackout date math.

This module is a thin re-export of `fomc.calendar` in the lab package, which is the
single source of truth for the schedule (2026 + 2027 + January 2028, decision and
strategy meetings) and the blackout math. The server, the lab CLI, the refresh
workflow and the dashboard JSON all read that one list.

The legacy names (`FOMC_DECISION_DATES`, `next_fomc`, …) are kept so existing callers
— including the `--next-fomc` lookup in .github/workflows/refresh-dashboard.yml —
keep working unchanged.
"""

from __future__ import annotations

from fomc.calendar import (  # noqa: F401  (re-exported API)
    DECISION_DATES,
    FOMC_DECISION_DATES,
    MEETINGS,
    SCHEDULE_HORIZON_DAYS,
    FomcMeeting,
    blackout_end,
    blackout_start,
    calendar_document,
    days_until,
    in_blackout,
    last_decision,
    next_decision,
    next_fomc,
    next_meeting,
    provenance,
    schedule_warning,
    today_utc,
)

__all__ = [
    "DECISION_DATES",
    "FOMC_DECISION_DATES",
    "MEETINGS",
    "SCHEDULE_HORIZON_DAYS",
    "FomcMeeting",
    "blackout_end",
    "blackout_start",
    "calendar_document",
    "days_until",
    "in_blackout",
    "last_decision",
    "next_decision",
    "next_fomc",
    "next_meeting",
    "provenance",
    "schedule_warning",
    "today_utc",
]
