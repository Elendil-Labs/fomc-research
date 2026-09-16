"""Monetary-policy regime primitive, parsed from primary-source FOMC statements.

Every rate-setting statement names the action and the new target range, e.g.
  "raise the target range for the federal funds rate to 2-1/4 to 2-1/2 percent"
  "maintain the target range for the federal funds rate at 3-1/2 to 3-3/4 percent"
This module reads those straight from data/fomc/statement/text/*.txt, builds a rate
path, and labels each meeting with a hiking/easing regime via a simple state machine
(holds inherit the prior regime; the last directional move sets it). The reusable
primitive is `regime_on(date)` — "what regime were we in on any given day?".

Usage:
    python -m fomc.regime            # build + print the timeline, write CSV
    python -m fomc.regime --at 2024-06-01
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]  # packages/fomc/src/fomc -> repo root
STMT_DIR = REPO / "data" / "fomc" / "statement" / "text"
OUT = REPO / "data" / "fomc" / "analysis" / "regime_timeline.csv"

_FRAC = {"": 0.0, "0": 0.0, "1/4": 0.25, "1/2": 0.5, "3/4": 0.75}
# tolerate unicode hyphens/dashes the Fed uses inside fractions ("2‑1/2")
_DASHES = {"‐", "‑", "‒", "–", "—", "−"}
_RATE_RE = re.compile(
    r"\b(raise|increase|lower|reduce|decrease|maintain|keep|leave|hold)"
    r"\s+the target range for the federal funds rate\b"
    r"(?:[^.]*?)(?:\bat\b|\bto\b)\s+([0-9/\- ]+?)\s+to\s+([0-9/\- ]+?)\s+percent",
    re.IGNORECASE,
)
_ACTION = {
    "raise": "Hike", "increase": "Hike",
    "lower": "Cut", "reduce": "Cut", "decrease": "Cut",
    "maintain": "Hold", "keep": "Hold", "leave": "Hold", "hold": "Hold",
}


@dataclass
class RateDecision:
    date: str          # ISO
    action: str        # Hike | Cut | Hold
    target_low: float
    target_high: float
    target_mid: float


def _norm(s: str) -> str:
    for d in _DASHES:
        s = s.replace(d, "-")
    return s.replace(" ", " ").replace(" ", " ")


def _parse_rate(tok: str) -> float:
    """'3-1/2' -> 3.5, '5' -> 5.0, '1/4' -> 0.25, '0' -> 0.0."""
    tok = _norm(tok).strip()
    if "-" in tok and "/" in tok:          # whole + fraction, e.g. 3-1/2
        whole, frac = tok.split("-", 1)
        return int(whole) + _FRAC[frac.strip()]
    if "/" in tok:                          # bare fraction, e.g. 1/4
        return _FRAC[tok]
    return float(tok)


def parse_statements(stmt_dir: Path = STMT_DIR) -> list[RateDecision]:
    """One RateDecision per statement that sets the funds-rate target (incl. emergencies)."""
    by_date: dict[str, RateDecision] = {}
    for path in sorted(stmt_dir.glob("*.txt")):
        iso = path.name[:10]
        try:
            date.fromisoformat(iso)
        except ValueError:
            continue
        m = _RATE_RE.search(_norm(path.read_text(encoding="utf-8")))
        if not m:
            continue
        verb, low_s, high_s = m.group(1).lower(), m.group(2), m.group(3)
        try:
            low, high = _parse_rate(low_s), _parse_rate(high_s)
        except (KeyError, ValueError):
            continue
        # keep the first (main 'a') statement per date
        by_date.setdefault(
            iso, RateDecision(iso, _ACTION[verb], low, high, round((low + high) / 2, 4))
        )
    return [by_date[d] for d in sorted(by_date)]


def audit_statements(stmt_dir: Path = STMT_DIR) -> dict:
    """Cross-check every statement file against the rate-sentence parser.

    A file counts as parsed when _RATE_RE matches and both rate tokens are readable.
    `unparsed` lists only files on dates where NO statement parsed — companion
    releases (implementation notes, 'b'/'c' files) whose same-date sibling parsed
    are not a failure. `stale` is True iff the newest statement file's date is
    strictly newer than the newest parsed decision date: the most recent meeting
    failed to parse and the regime timeline is frozen at the prior meeting.
    """
    parsed = 0
    parsed_dates: set[str] = set()
    failures: list[dict] = []
    latest_statement: str | None = None
    for path in sorted(stmt_dir.glob("*.txt")):
        iso = path.name[:10]
        try:
            date.fromisoformat(iso)
        except ValueError:
            continue  # not a dated statement file (as in parse_statements)
        latest_statement = iso if latest_statement is None else max(latest_statement, iso)
        m = _RATE_RE.search(_norm(path.read_text(encoding="utf-8")))
        ok = False
        if m:
            try:
                _parse_rate(m.group(2))
                _parse_rate(m.group(3))
                ok = True
            except (KeyError, ValueError):
                ok = False
        if ok:
            parsed += 1
            parsed_dates.add(iso)
        else:
            failures.append({"date": iso, "file": path.name})
    unparsed = [f for f in failures if f["date"] not in parsed_dates]
    latest_parsed = max(parsed_dates) if parsed_dates else None
    stale = latest_statement is not None and (
        latest_parsed is None or latest_statement > latest_parsed
    )
    return {
        "parsed": parsed,
        "unparsed": unparsed,
        "latest_statement": latest_statement,
        "latest_parsed": latest_parsed,
        "stale": stale,
    }


def format_alarm(audit: dict) -> str:
    """Loud, copy-pasteable alarm block for the stale-parser failure mode."""
    files = ", ".join(u["file"] for u in audit["unparsed"]) or "(unknown)"
    return (
        "!! ALARM: FOMC statement parser is STALE !!\n"
        f"!! Newest statement on disk is {audit['latest_statement']} but the newest\n"
        f"!! PARSED rate decision is {audit['latest_parsed']} — the most recent\n"
        "!! statement did not match the rate-sentence pattern (_RATE_RE).\n"
        "!! The Fed may have rewritten the statement template; the stated policy\n"
        "!! regime is frozen at the last parsed meeting and MAY BE STALE.\n"
        f"!! Unmatched file(s): {files}\n"
        "!! Fix: extend _RATE_RE / _ACTION in packages/fomc/src/fomc/regime.py."
    )


def build_timeline(decisions: list[RateDecision] | None = None) -> list[dict]:
    """Attach regime label + change/trailing metrics to each decision."""
    decisions = decisions or parse_statements()
    rows: list[dict] = []
    regime = "Unknown"
    prev_mid: float | None = None
    for dec in decisions:
        if dec.action == "Hike":
            regime = "Tightening"
        elif dec.action == "Cut":
            regime = "Easing"
        # Hold inherits the prior regime
        change_bps = None if prev_mid is None else round((dec.target_mid - prev_mid) * 100)
        d = date.fromisoformat(dec.date)
        # trailing 12-month change: latest decision >= 365 days earlier
        prior_yr = [x for x in decisions if (d - date.fromisoformat(x.date)).days >= 365]
        trail = round((dec.target_mid - prior_yr[-1].target_mid) * 100) if prior_yr else None
        rows.append({**asdict(dec), "regime": regime, "change_bps": change_bps,
                     "trailing_12m_bps": trail})
        prev_mid = dec.target_mid
    return rows


def regime_on(d: date | str, timeline: list[dict] | None = None) -> dict:
    """Regime in effect on date `d` = the most recent decision on/before `d`.

    Returns {"regime", "action", "target_low", "target_high", "as_of"} — `action` is
    the move at the most recent meeting, "as_of" its date. Empty regime if before data.
    """
    if isinstance(d, str):
        d = date.fromisoformat(d)
    timeline = timeline or build_timeline()
    prior = [r for r in timeline if date.fromisoformat(r["date"]) <= d]
    if not prior:
        return {"regime": "Unknown", "action": None, "target_low": None,
                "target_high": None, "as_of": None}
    r = prior[-1]
    return {"regime": r["regime"], "action": r["action"], "target_low": r["target_low"],
            "target_high": r["target_high"], "as_of": r["date"]}


def write_csv(timeline: list[dict], out: Path = OUT) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    cols = ["date", "action", "regime", "target_low", "target_high", "target_mid",
            "change_bps", "trailing_12m_bps"]
    with out.open("w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=cols)
        wr.writeheader()
        for r in timeline:
            wr.writerow({k: r[k] for k in cols})
    return out


def run(at: str | None = None) -> None:
    timeline = build_timeline()
    path = write_csv(timeline)
    print(f"Parsed {len(timeline)} rate decisions, {timeline[0]['date']} → {timeline[-1]['date']}")
    # regime spans summary
    spans, cur = [], None
    for r in timeline:
        if r["regime"] != cur:
            spans.append([r["regime"], r["date"], r["date"]])
            cur = r["regime"]
        else:
            spans[-1][2] = r["date"]
    print("Regime spans:")
    for reg, a, b in spans:
        print(f"  {reg:11s} {a} → {b}")
    if at:
        print(f"\nregime_on({at}) = {regime_on(at, timeline)}")
    print(f"\nCSV: {path}")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="FOMC monetary-policy regime timeline")
    p.add_argument("--at", help="print the regime in effect on this ISO date")
    args = p.parse_args(argv)
    run(at=args.at)
    audit = audit_statements()
    if audit["unparsed"]:
        dates = ", ".join(u["date"] for u in audit["unparsed"])
        print(
            f"\nWARNING: {len(audit['unparsed'])} statement date(s) did not match the "
            f"rate-sentence pattern: {dates}",
            file=sys.stderr,
        )
    if audit["stale"]:
        print("\n" + format_alarm(audit), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
