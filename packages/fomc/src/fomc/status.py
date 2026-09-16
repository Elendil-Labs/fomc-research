"""`fomc status` — where are we now, and what's the SPY/TLT playbook for it?

Prints the current monetary-policy regime (from fomc.regime), the most recent FOMC
meeting and what SPY/TLT did, and the historical regime-conditioned playbook for a
decision-day dip. This is the forward-looking command to run before the next meeting.

Usage:
    python -m fomc.status
    python -m fomc.status --date 2019-01-01 --no-fetch
"""

from __future__ import annotations

import argparse
import statistics as st
from bisect import bisect_left
from datetime import date, datetime

from fomc.event_study import load_event_dates, load_prices
from fomc.regime import build_timeline, regime_on


def _ret(series, dates, i, j):
    if i < 0 or j < 0 or i >= len(dates) or j >= len(dates):
        return None
    a = series[dates[i]]
    return None if a == 0 else series[dates[j]] / a - 1.0


def _cohort(dates, spy, tlt, events, timeline, regime: str, horizon: int = 5):
    """Decision-day-dip cohort (SPY fell), Powell non-emergency, in `regime`."""
    spy_fwd, tlt_fwd = [], []
    for ev in events:
        if ev["chair"] != "Powell" or ev["emergency"]:
            continue
        d = date.fromisoformat(ev["date"])
        idx = bisect_left(dates, d)
        if idx >= len(dates):
            continue
        d0 = _ret(spy, dates, idx - 1, idx)
        if d0 is None or d0 >= 0:
            continue
        if regime_on(ev["date"], timeline)["regime"] != regime:
            continue
        s, t = _ret(spy, dates, idx, idx + horizon), _ret(tlt, dates, idx, idx + horizon)
        if s is not None:
            spy_fwd.append(s)
        if t is not None:
            tlt_fwd.append(t)
    return spy_fwd, tlt_fwd


def _fmt(vals):
    if not vals:
        return "no history"
    n = len(vals)
    mean = 100 * st.fmean(vals)
    win = 100 * sum(1 for v in vals if v > 0) / n
    return f"mean {mean:+.2f}%, win {win:.0f}% (n={n})"


def run(as_of: str | None = None, do_fetch: bool = True) -> None:
    dates, spy, tlt = load_prices(do_fetch=do_fetch)
    events = load_event_dates()
    timeline = build_timeline()
    as_of_d = date.fromisoformat(as_of) if as_of else datetime.now().date()

    cur = regime_on(as_of_d, timeline)
    regime = cur["regime"]
    # when did the current regime start?
    start = None
    for r in timeline:
        if date.fromisoformat(r["date"]) > as_of_d:
            break
        if r["regime"] != regime:
            start = None
        elif start is None:
            start = r["date"]

    # most recent meeting on/before as_of
    past = [e for e in events if date.fromisoformat(e["date"]) <= as_of_d]
    last = past[-1] if past else None

    print("=" * 64)
    print(f"  FOMC STATUS  —  as of {as_of_d}")
    print("=" * 64)
    print(f"\n  REGIME:  {regime.upper()}" + (f"  (since {start})" if start else ""))
    print(f"           target range {cur['target_low']:.2f}-{cur['target_high']:.2f}%  "
          f"· last move: {cur['action']} on {cur['as_of']}")

    if last:
        d = date.fromisoformat(last["date"])
        idx = bisect_left(dates, d)
        d0 = _ret(spy, dates, idx - 1, idx) if idx < len(dates) else None
        t0 = _ret(tlt, dates, idx - 1, idx) if idx < len(dates) else None
        p5 = _ret(spy, dates, idx, idx + 5) if idx < len(dates) else None
        print(f"\n  LAST MEETING:  {last['date']} ({last['chair']})")
        if d0 is not None:
            settled = "settled" if p5 is not None else "still settling"
            p5s = f"{100*p5:+.2f}%" if p5 is not None else "n/a"
            print(f"           SPY on the day {100*d0:+.2f}% · TLT {100*t0:+.2f}% · "
                  f"SPY +5d {p5s} ({settled})")

    print(f"\n  PLAYBOOK — {regime} regime · when SPY falls on the decision day, next 5 days:")
    spy_f, tlt_f = _cohort(dates, spy, tlt, events, timeline, regime)
    print(f"           SPY: {_fmt(spy_f)}")
    print(f"           TLT: {_fmt(tlt_f)}")
    if spy_f:
        lean = ("dips have been BUYABLE — bounce odds favor you"
                if st.fmean(spy_f) > 0 else
                "dips have tended to KEEP FALLING — be patient, don't rush in")
        article = "an" if regime[:1].upper() in "AEIOU" else "a"
        print(f"\n  READ:    In {article} {regime} regime, {lean}.")
    print("\n  CAVEAT:  Past patterns, not promises. A hawkish Warsh could flip the")
    print("           regime to Tightening, which flips the playbook.")
    print("\n  Full per-event detail: data/fomc/analysis/fomc_event_truth.md / .csv")
    print("=" * 64)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Current FOMC regime + SPY/TLT playbook")
    p.add_argument("--date", dest="as_of", help="evaluate as of this ISO date (default: today)")
    p.add_argument("--no-fetch", action="store_true", help="skip yfinance backfill")
    args = p.parse_args(argv)
    run(as_of=args.as_of, do_fetch=not args.no_fetch)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
