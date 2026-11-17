"""Playbook + calendar tools: next meeting, blackout window, conditional SPY/TLT stats."""

from __future__ import annotations

from typing import Any

from fomc_server import _calendar as cal
from fomc_server._data import load_latest, load_truth, truth_events
from fomc_server._playbook import (
    WINDOW_DEFINITIONS,
    action_counts,
    condition_events,
    playbook_table,
)
from fomc_server.tools import error_dict

_VALID_ACTIONS = ("All", "Hike", "Hold", "Cut")

TRANSITION_RISK_CAVEAT = (
    "Transition risk: the weighted evidence currently reads 'Potential pivot' — the "
    "stated regime these base rates are conditioned on may be about to change, so "
    "history conditioned on it is less representative than usual."
)


_STRATEGY_NOTE = (
    "Strategy meeting: dedicated to broad monetary-policy strategy issues, no policy "
    "decision and no statement. The communications blackout still applies."
)


def _strategy_dict(meeting: Any, today: Any) -> dict[str, Any] | None:
    """Serialise the next strategy meeting (or None when the schedule has no more)."""
    if meeting is None:
        return None
    return {
        "start": meeting.start,
        "end": meeting.end,
        "days_until": cal.days_until(meeting.end, today),
        "blackout_start": meeting.blackout_start,
        "blackout_end": meeting.blackout_end,
        "in_blackout": cal.in_blackout(today, meeting.end),
        "note": _STRATEGY_NOTE,
    }


def get_playbook(action: str = "All") -> dict[str, Any]:
    """FOMC playbook for the next scheduled decision: date, days until, the Fed
    communications-blackout window (second Saturday before the decision through the
    first Thursday after), and null-safe conditional SPY/TLT return stats (n, mean,
    median, win rate over d0/p1/p3/p5/p10) across past non-emergency FOMC events in
    the CURRENT stated regime, optionally filtered to one action (Hike/Hold/Cut).
    Historical/observational evidence only — not investment advice."""
    try:
        if action not in _VALID_ACTIONS:
            return {"error": f"invalid action {action!r}; expected one of {_VALID_ACTIONS}"}
        doc, prov_latest = load_latest()
        truth, prov_truth = load_truth()
        events = truth_events(truth)
        stated = str(doc.get("current_repo_regime") or "Unknown")
        inferred = str(doc.get("inferred_regime") or "")

        today = cal.today_utc()
        next_decision = cal.next_decision(today)
        next_fomc: dict[str, Any] | None = None
        if next_decision:
            next_fomc = {
                "date": next_decision,
                "days_until": cal.days_until(next_decision, today),
                "blackout_start": cal.blackout_start(next_decision),
                "blackout_end": cal.blackout_end(next_decision),
                "in_blackout": cal.in_blackout(today, next_decision),
            }
        # A strategy meeting announces nothing, so it is never `next_fomc` — surface it
        # separately so callers do not mistake its blackout for a decision window.
        strategy = cal.next_meeting(today, kind="strategy")

        conditioned = condition_events(events, stated)
        filtered = (
            conditioned
            if action == "All"
            else condition_events(events, stated, action=action)
        )
        return {
            "as_of": today.isoformat(),
            "next_fomc": next_fomc,
            "next_strategy_meeting": _strategy_dict(strategy, today),
            "calendar": cal.provenance(today),
            "conditioning": {
                "stated_regime": stated,
                "action_filter": action,
                "excludes_emergency_meetings": True,
                "n_events": len(filtered),
                "action_counts": action_counts(conditioned),
            },
            "stats": playbook_table(filtered),
            "window_definitions": WINDOW_DEFINITIONS,
            "transition_risk": (
                TRANSITION_RISK_CAVEAT if inferred.startswith("Potential pivot") else None
            ),
            "framing": "Small-n historical base rates, not a forecast.",
            "provenance": {"regime_intel": prov_latest, "event_truth": prov_truth},
        }
    except Exception as exc:
        return error_dict(exc)


def get_fomc_calendar() -> dict[str, Any]:
    """The FOMC meeting calendar (2026, 2027 and January 2028, per the Fed's published
    schedules): every scheduled meeting with its `kind` ("decision", or "strategy" for
    the October 26-27, 2027 broad-strategy meeting that announces no policy decision),
    its Fed communications-blackout window (which applies to strategy meetings too),
    whether it is past or upcoming, whether today is inside its blackout, and whether
    the SPY/TLT event-truth table has data for it. `calendar` carries the source URL
    and publication date, plus a "schedule needs extending" warning once the last
    scheduled decision is less than 120 days away.
    Historical/observational evidence only — not investment advice."""
    try:
        today = cal.today_utc()
        truth_dates: set[str] = set()
        provenance: dict[str, Any] | None = None
        warnings: list[str] = []
        try:
            truth, provenance = load_truth()
            truth_dates = {str(e.get("date")) for e in truth_events(truth)}
        except Exception as exc:
            warnings.append(f"event-truth table unavailable: {exc}")
        meetings = [
            {
                # `date` stays the second day for every meeting (back-compat); it is
                # the announcement day for decisions and None in `decision_date` for
                # the strategy meeting.
                "date": m.end,
                "start": m.start,
                "kind": m.kind,
                "decision_date": m.decision_date,
                "blackout_start": m.blackout_start,
                "blackout_end": m.blackout_end,
                "in_blackout_today": cal.in_blackout(today, m.end),
                "is_past": m.end < today.isoformat(),
                "has_truth_data": (m.end in truth_dates) if not warnings else None,
                "note": _STRATEGY_NOTE if m.kind == "strategy" else None,
            }
            for m in cal.MEETINGS
        ]
        calendar_prov = cal.provenance(today)
        if calendar_prov["schedule_warning"]:
            warnings.append(calendar_prov["schedule_warning"])
        return {
            "as_of": today.isoformat(),
            "meetings": meetings,
            "next_fomc": cal.next_decision(today),
            "next_strategy_meeting": _strategy_dict(cal.next_meeting(today, kind="strategy"),
                                                    today),
            "calendar": calendar_prov,
            "warnings": warnings or None,
            "provenance": provenance,
        }
    except Exception as exc:
        return error_dict(exc)


def register(mcp: Any) -> None:
    mcp.tool()(get_playbook)
    mcp.tool()(get_fomc_calendar)
