"""The per-event 'source truth' table: how SPY and TLT traded around every FOMC event.

One row per scheduled FOMC decision (2018-03-21 onward), enriched with the parsed
regime/action/target, the decision-day closes, and SPY & TLT returns for the pre-5d
run-up, the decision day, and +1/+2/+3/+5/+10 sessions after. Written as a CSV (the
machine truth) and a wide Markdown table (the eyeball reference).

Usage:
    python -m fomc.truth
"""

from __future__ import annotations

import argparse
import csv
import sys
from bisect import bisect_left
from datetime import date, datetime, timezone

from fomc.event_study import OUT_DIR, load_event_dates, load_prices
from fomc.regime import audit_statements, build_timeline, format_alarm

FWD = [1, 2, 3, 5, 10]


def _ret(series, dates, i, j):
    if i < 0 or j < 0 or i >= len(dates) or j >= len(dates):
        return None
    a = series[dates[i]]
    return None if a == 0 else series[dates[j]] / a - 1.0


def _pct(v):
    return None if v is None else round(100 * v, 3)


def build_rows():
    dates, spy, tlt = load_prices(do_fetch=True)
    events = load_event_dates()
    timeline = build_timeline()
    tl = {r["date"]: r for r in timeline}

    rows = []
    for ev in events:
        iso = ev["date"]
        d = date.fromisoformat(iso)
        idx = bisect_left(dates, d)
        if idx >= len(dates):
            continue  # future / no price data
        # weekend/holiday announcements (e.g. Sun 2020-03-15) react on the next session
        dec = tl.get(iso, {})
        low, high = dec.get("target_low"), dec.get("target_high")
        ff = f"{low:.2f}-{high:.2f}" if low is not None else ""
        row = {
            "date": iso, "chair": ev["chair"],
            "regime": dec.get("regime", ""), "action": dec.get("action", ""),
            "ff_target": ff, "emergency": ev["emergency"],
            "spy_close": round(spy[dates[idx]], 4), "tlt_close": round(tlt[dates[idx]], 4),
            "spy_pre5": _pct(_ret(spy, dates, idx - 6, idx - 1)),
            "spy_d0": _pct(_ret(spy, dates, idx - 1, idx)),
            "tlt_pre5": _pct(_ret(tlt, dates, idx - 6, idx - 1)),
            "tlt_d0": _pct(_ret(tlt, dates, idx - 1, idx)),
        }
        for h in FWD:
            row[f"spy_p{h}"] = _pct(_ret(spy, dates, idx, idx + h))
            row[f"tlt_p{h}"] = _pct(_ret(tlt, dates, idx, idx + h))
        rows.append(row)
    return rows


def write_csv(rows) -> str:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    cols = (["date", "chair", "regime", "action", "ff_target", "emergency",
             "spy_close", "spy_pre5", "spy_d0"] + [f"spy_p{h}" for h in FWD]
            + ["tlt_close", "tlt_pre5", "tlt_d0"] + [f"tlt_p{h}" for h in FWD])
    path = OUT_DIR / "fomc_event_truth.csv"
    with path.open("w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=cols)
        wr.writeheader()
        wr.writerows(rows)
    return str(path)


def write_md(rows) -> str:
    def c(v):
        return "" if v is None else f"{v:+.2f}"
    L = []
    L.append("# FOMC Event Truth — SPY & TLT around every FOMC decision\n")
    L.append(f"_Generated {datetime.now(timezone.utc).date()} · returns in % from the "
             f"decision-day close (raw close) · `pN` = +N sessions after · full numeric "
             f"detail in `fomc_event_truth.csv`._\n")
    L.append("Action ∈ Hike/Hold/Cut; Regime = hiking (Tightening) vs easing cycle. "
             "`*` marks COVID emergency decisions.\n")
    L.append("| Date | Chair | Regime | Act | FF | SPY d0 | +1 | +3 | +5 | +10 "
             "| TLT d0 | +1 | +3 | +5 | +10 |")
    L.append("|---|---|---|---|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|")
    for r in rows:
        star = "*" if r["emergency"] else ""
        L.append(f"| {r['date']}{star} | {r['chair']} | {r['regime']} | {r['action']} "
                 f"| {r['ff_target']} | "
                 f"{c(r['spy_d0'])} | {c(r['spy_p1'])} | {c(r['spy_p3'])} | {c(r['spy_p5'])} "
                 f"| {c(r['spy_p10'])} | "
                 f"{c(r['tlt_d0'])} | {c(r['tlt_p1'])} | {c(r['tlt_p3'])} | {c(r['tlt_p5'])} "
                 f"| {c(r['tlt_p10'])} |")
    path = OUT_DIR / "fomc_event_truth.md"
    path.write_text("\n".join(L) + "\n", encoding="utf-8")
    return str(path)


def run() -> int:
    rows = build_rows()
    csv_path = write_csv(rows)
    md_path = write_md(rows)
    print(f"Truth table: {len(rows)} FOMC events, {rows[0]['date']} → {rows[-1]['date']}")
    print(f"  CSV: {csv_path}")
    print(f"  MD:  {md_path}")
    # Outputs are written above no matter what: operators keep the last-good data,
    # but the pipeline goes red if the newest statement failed to parse.
    audit = audit_statements()
    if audit["stale"]:
        print("\n" + format_alarm(audit), file=sys.stderr)
        return 2
    if audit["unparsed"]:
        dates = ", ".join(u["date"] for u in audit["unparsed"])
        print(f"WARNING: unparsed statement date(s): {dates}", file=sys.stderr)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="FOMC SPY/TLT per-event source-truth table")
    parser.parse_args(argv)
    return run()


if __name__ == "__main__":
    raise SystemExit(main())
