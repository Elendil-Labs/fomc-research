"""get_event_history — filtered per-event SPY/TLT truth table with day-0 color."""

from __future__ import annotations

from typing import Any

from fomc_server._data import load_truth, truth_events
from fomc_server._playbook import color_of
from fomc_server.tools import error_dict

_VALID_COLORS = ("green", "orange", "blue", "red")


def get_event_history(
    regime: str | None = None,
    action: str | None = None,
    chair: str | None = None,
    color: str | None = None,
    since: str | None = None,
    until: str | None = None,
    limit: int = 200,
) -> dict[str, Any]:
    """Per-event FOMC truth table (date, chair, stated regime, action, target range,
    SPY/TLT returns around the decision), filterable by regime, action, chair, day-0
    SPY/TLT color (green = both up, orange = SPY up/TLT down, blue = SPY down/TLT up,
    red = both down; zero counts as up; null when day-0 returns are missing) and an
    ISO date range. Chronological; `limit` keeps the most recent N matches.
    Historical/observational evidence only — not investment advice."""
    try:
        if color is not None and color not in _VALID_COLORS:
            return {"error": f"invalid color {color!r}; expected one of {_VALID_COLORS}"}
        doc, prov = load_truth()
        out: list[dict[str, Any]] = []
        for e in truth_events(doc):
            row_color = color_of(e.get("spy_d0"), e.get("tlt_d0"))
            d = str(e.get("date") or "")
            if regime is not None and (e.get("regime") or "Unknown") != regime:
                continue
            if action is not None and e.get("action") != action:
                continue
            if chair is not None and e.get("chair") != chair:
                continue
            if color is not None and row_color != color:
                continue
            if since is not None and d < since:
                continue
            if until is not None and d > until:
                continue
            out.append({**e, "color": row_color})
        truncated = len(out) > max(limit, 0)
        if truncated:
            out = out[-limit:]  # keep the most recent N, still chronological
        return {
            "n": len(out),
            "truncated": truncated,
            "events": out,
            "returns_unit": "percent",
            "provenance": prov,
        }
    except Exception as exc:
        return error_dict(exc)


def register(mcp: Any) -> None:
    mcp.tool()(get_event_history)
