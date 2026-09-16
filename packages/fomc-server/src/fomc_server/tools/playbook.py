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
        next_meeting = cal.next_fomc(today)
        next_fomc: dict[str, Any] | None = None
        if next_meeting:
            next_fomc = {
                "date": next_meeting,
                "days_until": cal.days_until(next_meeting, today),
                "blackout_start": cal.blackout_start(next_meeting),
                "blackout_end": cal.blackout_end(next_meeting),
                "in_blackout": cal.in_blackout(today, next_meeting),
            }

        conditioned = condition_events(events, stated)
        filtered = (
            conditioned
            if action == "All"
            else condition_events(events, stated, action=action)
        )
        return {
            "as_of": today.isoformat(),
            "next_fomc": next_fomc,
            "calendar_note": cal.CALENDAR_NOTE,
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
    """The 2026 FOMC decision calendar: every scheduled decision date with its Fed
    communications-blackout window, whether it is past or upcoming, whether today is
    inside its blackout, and whether the SPY/TLT event-truth table has data for it.
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
                "date": d,
                "blackout_start": cal.blackout_start(d),
                "blackout_end": cal.blackout_end(d),
                "in_blackout_today": cal.in_blackout(today, d),
                "is_past": d < today.isoformat(),
                "has_truth_data": (d in truth_dates) if not warnings else None,
            }
            for d in cal.FOMC_DECISION_DATES
        ]
        return {
            "as_of": today.isoformat(),
            "meetings": meetings,
            "next_fomc": cal.next_fomc(today),
            "calendar_note": cal.CALENDAR_NOTE,
            "warnings": warnings or None,
            "provenance": provenance,
        }
    except Exception as exc:
        return error_dict(exc)


def register(mcp: Any) -> None:
    mcp.tool()(get_playbook)
    mcp.tool()(get_fomc_calendar)
