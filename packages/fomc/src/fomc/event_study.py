"""FOMC event study: SPY & TLT price action in the 5 trading days before and after
each FOMC decision date.

Event universe = dates that have BOTH a statement and a press-conference transcript
(i.e. genuine FOMC policy-communication days), drawn from data/fomc/manifest.json.
The two March 2020 COVID emergency decisions are flagged and excluded from the main
aggregates. Chair attribution: Warsh from his first meeting (2026-06-17) onward,
Powell before.

Windows (idx = event-day index in the trading-day series; returns use raw close):
    pre_5d   = close[idx-1] / close[idx-6] - 1     # run-up over the 5 sessions before
    event_0d = close[idx]   / close[idx-1] - 1     # decision-day reaction (2pm statement)
    post_1d  = close[idx+1] / close[idx]   - 1
    post_3d  = close[idx+3] / close[idx]   - 1
    post_5d  = close[idx+5] / close[idx]   - 1      # 5 sessions after, from decision close

Usage:
    python -m fomc.event_study                 # build report + CSVs
    python -m fomc.event_study --no-fetch      # skip yfinance backfill (CSV only)
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics as st
from bisect import bisect_left
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from fomc.prices import DailyBar, fetch_yfinance_bars, load_csv_bars, write_bars_csv

# packages/fomc/src/fomc/event_study.py -> parents[4] is the repo root.
REPO = Path(__file__).resolve().parents[4]
# Git-ignored local price cache (data/market/ is in .gitignore). Seeded from yfinance
# on the first `fomc truth` / `fomc study` run, then extended incrementally.
MARKET_DIR = REPO / "data" / "market"
SPY_CSV = MARKET_DIR / "SPY-history.csv"
TLT_CSV = MARKET_DIR / "TLT-history.csv"
MANIFEST = REPO / "data" / "fomc" / "manifest.json"
OUT_DIR = REPO / "data" / "fomc" / "analysis"

EMERGENCY = {"2020-03-03", "2020-03-15"}  # COVID inter-meeting cuts
POWELL_START = date(2018, 3, 21)  # Powell's first FOMC as chair (Mar 20-21, 2018)
WARSH_FIRST = date(2026, 6, 17)   # Warsh's first FOMC as chair


# --------------------------------------------------------------------------- prices
def _load_cached_bars(ticker: str, cache: Path, do_fetch: bool) -> dict[date, DailyBar]:
    """Bars for one ticker from the local cache, extended (and rewritten) via yfinance.

    * cache present, do_fetch  -> load, fetch from 7 days before the cache end, append
                                  only dates past the cache end, rewrite the cache
    * cache present, no fetch  -> load as-is
    * cache missing, do_fetch  -> fetch the full history (period=max), write the cache
    * cache missing, no fetch  -> FileNotFoundError with instructions
    """
    if cache.exists():
        bars = load_csv_bars(cache)
        if not do_fetch or not bars:
            return bars
        cache_end = max(bars)
        start = cache_end - timedelta(days=7)  # small overlap to stitch cleanly
        try:
            fresh = fetch_yfinance_bars(ticker, start=start)
        except Exception as exc:  # pragma: no cover - network
            print(f"  ! yfinance backfill failed for {ticker}: {exc}")
            return bars
        added = {d: b for d, b in fresh.items() if d > cache_end}
        if added:  # only extend past the cache; never overwrite settled history
            bars.update(added)
            write_bars_csv(cache, bars)
        return bars
    if not do_fetch:
        raise FileNotFoundError(
            f"No cached {ticker} history at {cache}. Run once without --no-fetch "
            "(e.g. `fomc truth`) to seed the local price cache from yfinance."
        )
    bars = fetch_yfinance_bars(ticker)  # period=max
    if not bars:
        raise RuntimeError(f"yfinance returned no daily bars for {ticker}")
    write_bars_csv(cache, bars)
    return bars


def load_prices(do_fetch: bool = True) -> tuple[list[date], dict[date, float], dict[date, float]]:
    """Raw daily closes from the local cache (+ yfinance extension when do_fetch).

    Returns (sorted common dates, spy closes, tlt closes).
    """
    spy = {d: b.close for d, b in _load_cached_bars("SPY", SPY_CSV, do_fetch).items()}
    tlt = {d: b.close for d, b in _load_cached_bars("TLT", TLT_CSV, do_fetch).items()}
    common = sorted(set(spy) & set(tlt))
    return common, spy, tlt


# --------------------------------------------------------------------------- events
def _chair_for(d: date) -> str:
    if d >= WARSH_FIRST:
        return "Warsh"
    if d >= POWELL_START:
        return "Powell"
    return "Yellen"  # e.g. the Jan 2018 meeting — excluded from Powell aggregates


def load_event_dates() -> list[dict]:
    """Scheduled FOMC decision days, with chair + emergency flags.

    Event = statement AND (minutes OR press conference). Minutes anchor scheduled
    meetings back to 2018 (pre-2019 non-quarterly meetings had no press conference);
    the press-conference OR-clause keeps the most recent meeting, whose minutes are
    not released yet. Pure inter-meeting Board actions (no minutes, no presser) drop out.
    """
    m = json.loads(MANIFEST.read_text())
    events = []
    for mt in m["meetings"]:
        docs = mt["documents"]
        has_stmt = any(k.startswith("statement") and v.get("ok") for k, v in docs.items())
        has_minutes = docs.get("minutes", {}).get("ok")
        has_presser = docs.get("press_conference_transcript", {}).get("ok")
        if not (has_stmt and (has_minutes or has_presser)):
            continue
        iso = mt["meeting_date"]
        d = date.fromisoformat(iso)
        events.append({
            "date": iso,
            "chair": _chair_for(d),
            "emergency": iso in EMERGENCY,
        })
    return sorted(events, key=lambda e: e["date"])


# --------------------------------------------------------------------------- windows
@dataclass
class EventWindow:
    date: str
    chair: str
    emergency: bool
    spy_pre5: float | None = None
    spy_event0: float | None = None
    spy_post1: float | None = None
    spy_post3: float | None = None
    spy_post5: float | None = None
    tlt_pre5: float | None = None
    tlt_event0: float | None = None
    tlt_post1: float | None = None
    tlt_post3: float | None = None
    tlt_post5: float | None = None
    event_color: str = ""  # SPY/TLT joint sign on decision day
    post5_complete: bool = True


def _ret(series: dict[date, float], dates: list[date], i: int, j: int) -> float | None:
    if i < 0 or j < 0 or i >= len(dates) or j >= len(dates):
        return None
    a, b = series[dates[i]], series[dates[j]]
    if a == 0:
        return None
    return b / a - 1.0


def _color(spy: float | None, tlt: float | None) -> str:
    if spy is None or tlt is None:
        return ""
    if spy >= 0 and tlt >= 0:
        return "Green"   # both up
    if spy >= 0 and tlt < 0:
        return "Orange"  # stocks up, bonds down (risk-on / rates up)
    if spy < 0 and tlt >= 0:
        return "Blue"    # stocks down, bonds up (flight to safety)
    return "Red"         # both down


def build_windows(events: list[dict], dates: list[date], spy: dict, tlt: dict) -> list[EventWindow]:
    out = []
    for ev in events:
        d = date.fromisoformat(ev["date"])
        idx = bisect_left(dates, d)
        # FOMC decisions fall on trading days; if exact date absent, use next session.
        if idx >= len(dates) or dates[idx] != d:
            if idx >= len(dates):
                continue
        w = EventWindow(date=ev["date"], chair=ev["chair"], emergency=ev["emergency"])
        w.spy_pre5 = _ret(spy, dates, idx - 6, idx - 1)
        w.spy_event0 = _ret(spy, dates, idx - 1, idx)
        w.spy_post1 = _ret(spy, dates, idx, idx + 1)
        w.spy_post3 = _ret(spy, dates, idx, idx + 3)
        w.spy_post5 = _ret(spy, dates, idx, idx + 5)
        w.tlt_pre5 = _ret(tlt, dates, idx - 6, idx - 1)
        w.tlt_event0 = _ret(tlt, dates, idx - 1, idx)
        w.tlt_post1 = _ret(tlt, dates, idx, idx + 1)
        w.tlt_post3 = _ret(tlt, dates, idx, idx + 3)
        w.tlt_post5 = _ret(tlt, dates, idx, idx + 5)
        w.event_color = _color(w.spy_event0, w.tlt_event0)
        w.post5_complete = w.spy_post5 is not None
        out.append(w)
    return out


# --------------------------------------------------------------------------- stats
def _summ(vals: list[float]) -> dict:
    vals = [v for v in vals if v is not None]
    if not vals:
        return {"n": 0}
    return {
        "n": len(vals),
        "mean_pct": round(100 * st.fmean(vals), 3),
        "median_pct": round(100 * st.median(vals), 3),
        "std_pct": round(100 * (st.pstdev(vals) if len(vals) > 1 else 0.0), 3),
        "hit_rate_pct": round(100 * sum(1 for v in vals if v > 0) / len(vals), 1),
        "min_pct": round(100 * min(vals), 3),
        "max_pct": round(100 * max(vals), 3),
    }


def _corr(xs: list, ys: list) -> float | None:
    pairs = [(x, y) for x, y in zip(xs, ys) if x is not None and y is not None]
    if len(pairs) < 3:
        return None
    try:
        return round(st.correlation([p[0] for p in pairs], [p[1] for p in pairs]), 3)
    except st.StatisticsError:
        return None


def aggregate(windows: list[EventWindow]) -> dict:
    powell = [w for w in windows if w.chair == "Powell" and not w.emergency]
    fields = ["spy_pre5", "spy_event0", "spy_post1", "spy_post3", "spy_post5",
              "tlt_pre5", "tlt_event0", "tlt_post1", "tlt_post3", "tlt_post5"]
    stats = {f: _summ([getattr(w, f) for w in powell]) for f in fields}
    # Reversal / drift relationships (Powell, scheduled).
    rel = {
        "corr_spy_pre5_vs_post5": _corr([w.spy_pre5 for w in powell], [w.spy_post5 for w in powell]),
        "corr_spy_event0_vs_post5": _corr([w.spy_event0 for w in powell], [w.spy_post5 for w in powell]),
        "corr_spy_tlt_event0": _corr([w.spy_event0 for w in powell], [w.tlt_event0 for w in powell]),
    }
    # Conditional: post5 given decision-day direction.
    def cond(sel) -> dict:
        return {"spy_post5": _summ([w.spy_post5 for w in powell if sel(w)]),
                "tlt_post5": _summ([w.tlt_post5 for w in powell if sel(w)])}
    conditional = {
        "spy_down_on_decision": cond(lambda w: (w.spy_event0 or 0) < 0),
        "spy_up_on_decision": cond(lambda w: (w.spy_event0 or 0) >= 0),
        "tlt_up_on_decision": cond(lambda w: (w.tlt_event0 or 0) >= 0),
    }
    colors: dict[str, int] = {}
    for w in powell:
        colors[w.event_color] = colors.get(w.event_color, 0) + 1
    return {"n_powell_scheduled": len(powell), "stats": stats, "relationships": rel,
            "conditional_post5": conditional, "event_day_color_counts": colors}


def percentile(value: float | None, sample: list[float]) -> float | None:
    sample = [v for v in sample if v is not None]
    if value is None or not sample:
        return None
    return round(100 * sum(1 for v in sample if v <= value) / len(sample), 1)


# --------------------------------------------------------------------------- report
def write_csv(windows: list[EventWindow]) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / "event_windows.csv"
    cols = list(asdict(windows[0]).keys())
    with path.open("w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=cols)
        wr.writeheader()
        for w in windows:
            row = asdict(w)
            for k, v in row.items():
                if isinstance(v, float):
                    row[k] = round(100 * v, 3)  # store as percent
            wr.writerow(row)
    return path


def _fmt(x) -> str:
    if x is None:
        return "  n/a"
    if isinstance(x, dict):
        return str(x)
    return f"{x:+.2f}%" if isinstance(x, float) and abs(x) < 1 else str(x)


def _pct(x: float | None) -> str:
    return "n/a" if x is None else f"{100*x:+.2f}%"


def write_report(windows: list[EventWindow], agg: dict, do_fetch: bool) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    powell = [w for w in windows if w.chair == "Powell" and not w.emergency]
    warsh = [w for w in windows if w.chair == "Warsh"]
    emerg = [w for w in windows if w.emergency]
    s = agg["stats"]

    def stat_row(label: str, f: str) -> str:
        d = s[f]
        if not d.get("n"):
            return f"| {label} | 0 | | | | | |"
        return (f"| {label} | {d['n']} | {d['mean_pct']:+.2f}% | {d['median_pct']:+.2f}% | "
                f"{d['hit_rate_pct']:.0f}% | {d['std_pct']:.2f}% | {d['min_pct']:+.1f}% / {d['max_pct']:+.1f}% |")

    L = []
    L.append("# FOMC Event Study — SPY & TLT around FOMC decisions\n")
    L.append(f"_Generated {datetime.now(timezone.utc).date()} · price source: local cache"
             f"{' + yfinance backfill' if do_fetch else ' only'} · returns use raw close._\n")
    L.append(f"**Event universe:** {len(powell)} scheduled Powell-era FOMC days "
             f"({powell[0].date} → {powell[-1].date}), plus {len(emerg)} flagged COVID emergency "
             f"decisions (excluded from aggregates), plus {len(warsh)} Warsh meeting(s).\n")

    L.append("## Powell era — SPY (scheduled meetings)\n")
    L.append("| Window | n | Mean | Median | Hit rate (up) | Std | Min / Max |")
    L.append("|---|---|---|---|---|---|---|")
    L.append(stat_row("Pre-5d run-up (t-5→t-1)", "spy_pre5"))
    L.append(stat_row("Decision day (t-1→t)", "spy_event0"))
    L.append(stat_row("Post +1d", "spy_post1"))
    L.append(stat_row("Post +3d", "spy_post3"))
    L.append(stat_row("Post +5d", "spy_post5"))
    L.append("\n## Powell era — TLT (scheduled meetings)\n")
    L.append("| Window | n | Mean | Median | Hit rate (up) | Std | Min / Max |")
    L.append("|---|---|---|---|---|---|---|")
    L.append(stat_row("Pre-5d run-up (t-5→t-1)", "tlt_pre5"))
    L.append(stat_row("Decision day (t-1→t)", "tlt_event0"))
    L.append(stat_row("Post +1d", "tlt_post1"))
    L.append(stat_row("Post +3d", "tlt_post3"))
    L.append(stat_row("Post +5d", "tlt_post5"))

    rel = agg["relationships"]
    L.append("\n## Relationships (Powell, scheduled)\n")
    L.append(f"- **Pre-FOMC drift:** mean SPY run-up into the decision = "
             f"{s['spy_pre5']['mean_pct']:+.2f}% (hit {s['spy_pre5']['hit_rate_pct']:.0f}%); "
             f"mean decision-day SPY = {s['spy_event0']['mean_pct']:+.2f}%.")
    L.append(f"- **Reversal check:** corr(SPY pre-5d, SPY post-5d) = {rel['corr_spy_pre5_vs_post5']}; "
             f"corr(SPY decision-day, SPY post-5d) = {rel['corr_spy_event0_vs_post5']}.")
    L.append(f"- **Stock/bond co-move on decision day:** corr(SPY, TLT) = {rel['corr_spy_tlt_event0']}.")
    L.append(f"- **Decision-day color counts (SPY×TLT sign):** {agg['event_day_color_counts']} "
             f"(Green=both up, Orange=stocks up/bonds down, Blue=stocks down/bonds up, Red=both down).")

    c = agg["conditional_post5"]
    L.append("\n## Conditional post-5d (Powell, scheduled)\n")
    L.append("| Condition on decision day | SPY post-5d mean (hit) | TLT post-5d mean (hit) |")
    L.append("|---|---|---|")
    for key, lbl in [("spy_down_on_decision", "SPY fell on decision day"),
                     ("spy_up_on_decision", "SPY rose on decision day"),
                     ("tlt_up_on_decision", "TLT rose on decision day")]:
        sp, tl = c[key]["spy_post5"], c[key]["tlt_post5"]
        sp_s = f"{sp['mean_pct']:+.2f}% ({sp['hit_rate_pct']:.0f}%, n={sp['n']})" if sp.get("n") else "n/a"
        tl_s = f"{tl['mean_pct']:+.2f}% ({tl['hit_rate_pct']:.0f}%, n={tl['n']})" if tl.get("n") else "n/a"
        L.append(f"| {lbl} | {sp_s} | {tl_s} |")

    # Warsh application
    L.append("\n## Warsh's first meeting — applying the Powell-era lens\n")
    if not warsh:
        L.append("_No Warsh meeting in the price window yet._")
    for w in warsh:
        comp = "incomplete (fewer than 5 post sessions settled)" if not w.post5_complete else "complete"
        L.append(f"### {w.date} (Warsh #1) — post-window {comp}\n")
        L.append("| Window | SPY | percentile vs Powell | TLT | percentile vs Powell |")
        L.append("|---|---|---|---|---|")
        for lbl, sf, tf in [("Pre-5d run-up", "spy_pre5", "tlt_pre5"),
                            ("Decision day", "spy_event0", "tlt_event0"),
                            ("Post +1d", "spy_post1", "tlt_post1"),
                            ("Post +3d", "spy_post3", "tlt_post3"),
                            ("Post +5d", "spy_post5", "tlt_post5")]:
            sv, tv = getattr(w, sf), getattr(w, tf)
            sp = percentile(sv, [getattr(p, sf) for p in powell])
            tp = percentile(tv, [getattr(p, tf) for p in powell])
            L.append(f"| {lbl} | {_pct(sv)} | {sp if sp is not None else 'n/a'}%ile | "
                     f"{_pct(tv)} | {tp if tp is not None else 'n/a'}%ile |")
        L.append(f"\nDecision-day color: **{w.event_color}**.")

    L.append("\n## Notes & caveats\n")
    L.append("- Returns use raw closing prices; 5-day dividend drag on TLT is negligible.")
    L.append("- Decision-day return captures the 2pm statement + press conference within that session's close.")
    L.append("- COVID emergency decisions (Mar 2020) are flagged and excluded from aggregates.")
    L.append("- Warsh post-window is partial until 5 sessions settle; re-run after more sessions.")
    L.append("- Event windows CSV: `data/fomc/analysis/event_windows.csv` (values in percent).")

    path = OUT_DIR / "fomc_spy_tlt_event_study.md"
    path.write_text("\n".join(L) + "\n", encoding="utf-8")
    return path


def run(do_fetch: bool = True) -> None:
    dates, spy, tlt = load_prices(do_fetch=do_fetch)
    print(f"Prices: {len(dates)} common sessions, {dates[0]} → {dates[-1]}")
    events = load_event_dates()
    windows = build_windows(events, dates, spy, tlt)
    print(f"Events: {len(windows)} FOMC communication days "
          f"({sum(1 for w in windows if w.chair=='Powell')} Powell, "
          f"{sum(1 for w in windows if w.chair=='Warsh')} Warsh, "
          f"{sum(1 for w in windows if w.emergency)} emergency)")
    agg = aggregate(windows)
    csv_path = write_csv(windows)
    rep_path = write_report(windows, agg, do_fetch)
    # also persist merged prices for reproducibility
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with (OUT_DIR / "prices_spy_tlt.csv").open("w", newline="") as f:
        wr = csv.writer(f)
        wr.writerow(["Date", "SPY_close", "TLT_close"])
        for d in dates:
            wr.writerow([d.isoformat(), f"{spy[d]:.4f}", f"{tlt[d]:.4f}"])
    print(f"Report:  {rep_path}")
    print(f"CSV:     {csv_path}")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="FOMC SPY/TLT event study")
    p.add_argument("--no-fetch", action="store_true", help="CSV only; skip yfinance backfill")
    args = p.parse_args(argv)
    run(do_fetch=not args.no_fetch)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
