"""Pure conditional-stats + event-color helpers (port of the dashboard's lib/playbook.ts
and lib/colorDay.ts logic). "Given the current stated regime, what historically happened
around FOMC decisions like the next one?" Historical conditional evidence only.
"""

from __future__ import annotations

from collections import Counter
from statistics import median as _median
from typing import Any

PLAYBOOK_WINDOWS: tuple[str, ...] = ("d0", "p1", "p3", "p5", "p10")
PLAYBOOK_ASSETS: tuple[str, ...] = ("spy", "tlt")

WINDOW_DEFINITIONS: dict[str, str] = {
    "d0": "decision-day return, % (close vs prior close)",
    "p1": "return over the 1 trading day after the decision, %",
    "p3": "return over the 3 trading days after the decision, %",
    "p5": "return over the 5 trading days after the decision, %",
    "p10": "return over the 10 trading days after the decision, %",
}

Event = dict[str, Any]


def condition_events(events: list[Event], regime: str, action: str | None = None) -> list[Event]:
    """Filter to the conditioning set: same regime (missing regime -> "Unknown"),
    optionally same action, and NEVER emergency meetings — unscheduled decisions
    are a different animal and would pollute the base rates."""
    want = regime or "Unknown"
    out: list[Event] = []
    for e in events:
        if e.get("emergency"):
            continue
        if (e.get("regime") or "Unknown") != want:
            continue
        if action and e.get("action") != action:
            continue
        out.append(e)
    return out


def window_stats(events: list[Event], key: str) -> dict[str, Any]:
    """Null-safe summary stats over one return column (e.g. "spy_p5")."""
    vals = [v for e in events if isinstance(v := e.get(key), (int, float)) and v == v]
    n = len(vals)
    if n == 0:
        return {"n": 0, "mean": None, "median": None, "win_rate": None}
    return {
        "n": n,
        "mean": round(sum(vals) / n, 2),
        "median": round(_median(vals), 2),
        "win_rate": round(sum(1 for v in vals if v > 0) / n, 4),
    }


def playbook_table(events: list[Event]) -> dict[str, dict[str, Any]]:
    """Full SPY/TLT x window stats grid for an (already conditioned) event set."""
    return {
        asset: {w: window_stats(events, f"{asset}_{w}") for w in PLAYBOOK_WINDOWS}
        for asset in PLAYBOOK_ASSETS
    }


def action_counts(events: list[Event]) -> dict[str, int]:
    return dict(Counter(str(e.get("action")) for e in events))


def color_of(spy_d0: float | None, tlt_d0: float | None) -> str | None:
    """SPY/TLT day-0 color. Zero counts as up. Null inputs -> None (no color).

    green: SPY>=0 & TLT>=0 | orange: SPY>=0 & TLT<0 | blue: SPY<0 & TLT>=0 | red: both<0.
    """
    if spy_d0 is None or tlt_d0 is None:
        return None
    if spy_d0 >= 0:
        return "green" if tlt_d0 >= 0 else "orange"
    return "blue" if tlt_d0 >= 0 else "red"
