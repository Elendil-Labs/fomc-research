"""Score collected regime-intelligence evidence into the dashboard's latest.json.

Reads regime_intel/latest_raw.json (produced by collect_regime_intel.py) and writes:

  * regime_intel/latest.json             — what the dashboard renders
  * regime_intel/history/YYYY-MM-DD.json — full daily snapshot (audit trail)
  * regime_intel/history.json            — compact net-lean series (trend chart)

Scoring model — weighted vote-share over DIRECTION (not an averaged magnitude):
  * Each source only contributes its DIRECTION (easing / neutral / tightening) — the
    reproducible call. We deliberately do not average the model's -2..+2 magnitude,
    which is the least stable thing an LLM produces run-to-run.
  * Each source carries a weight = source-tier x importance x confidence x recency, so
    a Fed statement outvotes a random blog.
  * Sources are clustered by event_key (the underlying event/release they report on)
    and each cluster votes ONCE via its max-weight source — ten outlets covering the
    same CPI print are one vote, not ten. Keyless sources are singleton clusters.
  * We report the weighted SHARE of evidence pointing each way, plus a 4-state regime
    descriptor anchored to the current (statement-derived) regime:
        Easing | Tightening                         (evidence confirms the regime)
        Potential pivot -> tightening | -> easing    (evidence points against the regime)

Failure handling: if collection errored or returned no sources, the previous good
latest.json is preserved and flagged {stale:true, error_summary:...}.

Usage:
    python scripts/score_regime_intel.py [--next-fomc 2026-07-29]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, datetime, timedelta, timezone
from typing import Callable

import _intel_common as ic

# Multiplicative weight components (surfaced transparently in the output "scoring" block).
IMPORTANCE_W = {"high": 1.0, "medium": 0.6, "low": 0.3}
CONFIDENCE_W = {"high": 1.0, "medium": 0.7, "low": 0.4}
# Evidentiary tier — documented fact / official data carry full weight; sell-side
# scenarios and pundit interpretation are discounted so narrative can't swamp the read.
CLAIM_TYPE_W = {
    "documented_fact": 1.0,
    "official_data": 1.0,
    "sell_side_scenario": 0.6,
    "interpretation": 0.4,
}
IMPORTANCE_RANK = {"high": 3, "medium": 2, "low": 1}
BUCKETS = ("employment", "inflation", "fed_communications", "market_pricing")

# (id, human text) for the regime-change checklist; statuses derived in build_checklist.
CHECKLIST_ITEMS = [
    ("comm_deemphasize_easing", "Fed communications explicitly de-emphasize further easing"),
    ("comm_inflation_over_labor", "Fed emphasizes inflation upside risks over labor weakness"),
    ("pricing_removes_cuts", "Market pricing removes expected cuts or starts pricing hikes"),
    ("twoy_rises", "2Y yields rise materially over the intermeeting window"),
    ("inflation_upside", "Inflation data surprises to the upside"),
    ("employment_firm", "Employment remains firm enough to reduce pressure for cuts"),
    ("spytlt_confirms", "SPY/TLT color and rate-market behavior confirm the macro read"),
]

REGIME_DIR = {"Easing": "easing", "Tightening": "tightening"}

# SPY/TLT market-confirmation signal (checklist item "spytlt_confirms").
SPYTLT_WINDOW = 10  # trading days the trend is measured over
SPYTLT_LOOKBACK_DAYS = 30  # calendar days of history fetched (~20 trading days)
SPYTLT_FLAT = 0.005  # |window return| below this reads as flat/no signal


def recency_decay(published_at: str, today: date, floored: bool) -> float:
    """0-7d 1.0, 8-14d 0.75, 15-30d 0.5, >30d 0.25; official/Fed floored at 0.5."""
    try:
        d = datetime.fromisoformat(published_at.replace("Z", "+00:00")).date()
        age = (today - d).days
    except (ValueError, AttributeError):
        age = 21  # unknown date -> treat as mid-stale
    if age <= 7:
        w = 1.0
    elif age <= 14:
        w = 0.75
    elif age <= 30:
        w = 0.5
    else:
        w = 0.25
    return max(w, 0.5) if floored else w


def weight_of(s: dict, today: date) -> float:
    """source-tier x claim-type x importance x confidence x recency.

    source-tier = WHO published (Fed > official data > news); claim-type = WHAT kind of
    claim (documented fact / official data > sell-side scenario > interpretation).
    """
    tier = ic.source_tier(s.get("publisher", ""), s.get("url", ""))
    return (
        ic.TIER_WEIGHTS[tier]
        * CLAIM_TYPE_W.get(ic.claim_type_of(s), 0.4)
        * IMPORTANCE_W.get(s.get("importance", "medium"), 0.6)
        * CONFIDENCE_W.get(s.get("confidence", "medium"), 0.7)
        * recency_decay(s.get("published_at", ""), today, floored=tier != "news")
    )


def cluster_events(sources: list[dict], today: date) -> list[dict]:
    """Collapse sources into one representative per underlying EVENT.

    URL/title dedup catches republication; this catches coverage volume — ten outlets
    covering the same CPI print share an event_key and become ONE cluster with ONE vote.
    Keyless/legacy sources fall back to their own URL, i.e. singleton clusters
    (pre-event_key behavior preserved exactly). Each cluster is represented by its
    max-weight source (ties: newer published_at), annotated with "cluster_size".
    """
    clusters: dict[str, list[dict]] = {}
    for s in sources:
        clusters.setdefault(ic.event_cluster_key(s), []).append(s)
    reps: list[dict] = []
    for members in clusters.values():
        rep = max(members, key=lambda s: (weight_of(s, today), s.get("published_at", "")))
        reps.append({**rep, "cluster_size": len(members)})
    return reps


def direction_shares(sources: list[dict], today: date) -> tuple[dict, float]:
    """Weighted share of evidence pointing easing / neutral / tightening (sums to 1).

    Votes are counted per EVENT cluster, not per source: only each cluster's
    representative (max-weight source) contributes, so coverage volume is not evidence.
    """
    w = {"easing": 0.0, "neutral": 0.0, "tightening": 0.0}
    total = 0.0
    for s in cluster_events(sources, today):
        wt = weight_of(s, today)
        d = s.get("direction", "neutral")
        if d not in w:
            d = "neutral"
        w[d] += wt
        total += wt
    if total == 0:
        return {"easing": 0.0, "neutral": 0.0, "tightening": 0.0}, 0.0
    return {k: round(v / total, 4) for k, v in w.items()}, round(total, 3)


def evidence_dir(shares: dict) -> str:
    t, e = shares["tightening"], shares["easing"]
    if t > e:
        return "tightening"
    if e > t:
        return "easing"
    return "neutral"


def descriptor(ev_dir: str, current_regime: str) -> str:
    """4-state read anchored to the current (statement-derived) regime."""
    rdir = REGIME_DIR.get(current_regime)
    if ev_dir == "neutral":
        return current_regime if rdir else "Mixed"
    if rdir is None:  # no regime anchor (Unknown) — just name the evidence direction
        return "Tightening" if ev_dir == "tightening" else "Easing"
    if ev_dir == rdir:
        return current_regime  # evidence confirms the regime -> settled
    return f"Potential pivot → {ev_dir}"  # evidence opposes the regime -> pivot pressure


def inferred_lean(ev_dir: str, current_regime: str) -> str:
    """Direction of the macro read the market should confirm.

    Mirrors descriptor()'s anchoring: the evidence direction when it is directional
    (that is what the inferred-regime label points at), else the statement-derived
    regime anchor; "neutral" when neither gives a direction.
    """
    if ev_dir in ("easing", "tightening"):
        return ev_dir
    return REGIME_DIR.get(current_regime, "neutral")


def _fetch_daily_closes(ticker: str, start: date, end: date) -> dict[date, float]:
    """Daily closes via the fomc package's yfinance helper (lazy import: network dep)."""
    from fomc.prices import fetch_yfinance_bars

    return {d: bar.close for d, bar in fetch_yfinance_bars(ticker, start=start, end=end).items()}


def _window_return(closes: dict[date, float], dates: list[date], window: int) -> float:
    """Simple return over the last `window` trading days of `dates` (needs window+1)."""
    if len(dates) < window + 1:
        raise ValueError(f"need {window + 1} closes for a {window}-day return, got {len(dates)}")
    return closes[dates[-1]] / closes[dates[-1 - window]] - 1.0


def spytlt_status(spy_ret: float, tlt_ret: float, lean: str, flat: float = SPYTLT_FLAT) -> str:
    """Map N-day SPY/TLT returns to a checklist status for the given inferred lean.

    TLT is the rate proxy: TLT down = yields rising = tightening-consistent; TLT up =
    easing-consistent (conceptually the dashboard's color-day truth table, over a trend
    window instead of d0). SPY corroborates risk tone — hawkish repricing weighs on
    equities, dovish repricing supports them — and only upgrades/downgrades between
    partial and confirmed; TLT alone decides confirming vs not. Moves with
    |return| <= `flat` count as flat (boundary-inclusive neutral, matching the
    market-pricing axis dead-zone convention).

        lean=tightening                      lean=easing
        TLT down + SPY down -> confirmed     TLT up + SPY up   -> confirmed
        TLT down + SPY up/flat -> partial    TLT up + SPY down/flat -> partial
        TLT flat            -> partial       TLT flat          -> partial
        TLT up              -> not_confirmed TLT down          -> not_confirmed
        any other lean -> unknown (no directional macro read to confirm)
    """
    if lean not in ("easing", "tightening"):
        return "unknown"
    tlt_dir = "up" if tlt_ret > flat else "down" if tlt_ret < -flat else "flat"
    spy_dir = "up" if spy_ret > flat else "down" if spy_ret < -flat else "flat"
    confirming_tlt = "down" if lean == "tightening" else "up"
    corroborating_spy = "down" if lean == "tightening" else "up"
    if tlt_dir == "flat":
        return "partial"
    if tlt_dir != confirming_tlt:
        return "not_confirmed"
    return "confirmed" if spy_dir == corroborating_spy else "partial"


def compute_spytlt_signal(
    lean: str,
    today: date,
    window: int = SPYTLT_WINDOW,
    fetch_closes: Callable[[str, date, date], dict[date, float]] = _fetch_daily_closes,
) -> dict | None:
    """Fetch recent SPY/TLT closes and score the market-confirmation checklist item.

    Returns {window_days, spy_ret, tlt_ret, as_of, status} on success, or None on ANY
    failure (network outage, thin history, ...) — a price outage must never break
    scoring, so callers treat None as status "unknown". Returns are computed over the
    last `window` COMMON trading days so both legs cover the same span.
    """
    try:
        start = today - timedelta(days=SPYTLT_LOOKBACK_DAYS)
        spy = fetch_closes("SPY", start, today)
        tlt = fetch_closes("TLT", start, today)
        common = sorted(set(spy) & set(tlt))
        spy_ret = _window_return(spy, common, window)
        tlt_ret = _window_return(tlt, common, window)
        return {
            "window_days": window,
            "spy_ret": round(spy_ret, 4),
            "tlt_ret": round(tlt_ret, 4),
            "as_of": common[-1].isoformat(),
            "status": spytlt_status(spy_ret, tlt_ret, lean),
        }
    except Exception as exc:  # noqa: BLE001 — any price failure degrades to unknown
        print(f"spytlt signal unavailable, falling back to unknown: {exc}", file=sys.stderr)
        return None


def conviction(shares: dict, n: int) -> str:
    """How lopsided + how much evidence backs the directional call.

    `n` is the number of distinct EVENTS (clusters), not raw sources — ten articles
    about one CPI print are one piece of evidence, not ten.
    """
    t, e = shares["tightening"], shares["easing"]
    directional = t + e
    if directional == 0 or n < 2:
        return "Low"
    win = max(t, e) / directional
    if n >= 5 and win >= 0.70:
        return "High"
    if n >= 3 and win >= 0.58:
        return "Moderate"
    return "Low"


def lean_label(shares: dict) -> str:
    t, e = shares["tightening"], shares["easing"]
    if t == 0 and e == 0:
        return "no directional signal"
    if t > e:
        return "strongly tightening" if t / (t + e) >= 0.75 else "leaning tightening"
    if e > t:
        return "strongly easing" if e / (t + e) >= 0.75 else "leaning easing"
    return "mixed"


def score_buckets(sources: list[dict], today: date) -> dict:
    """Per-bucket vote shares + dominant lean."""
    out: dict[str, dict] = {}
    for bucket in BUCKETS:
        items = [s for s in sources if s.get("bucket") == bucket]
        reps = cluster_events(items, today)
        # reps are already one-per-event; re-clustering inside direction_shares is a
        # no-op (each rep keeps its own cluster key), so shares match the reps' weights.
        shares, total = direction_shares(reps, today)
        out[bucket] = {
            "shares": shares,
            "net": round(shares["tightening"] - shares["easing"], 4),
            "dominant": evidence_dir(shares),
            "label": lean_label(shares),
            "n": len(reps),
            "n_sources": len(items),
            "weight_sum": total,
        }
    return out


def build_checklist(bucket_scores: dict, spytlt_confirms: str = "unknown") -> list[dict]:
    net = {b: bucket_scores[b]["net"] for b in BUCKETS}

    def st(v: float, hi: float = 0.4, lo: float = 0.15) -> str:
        if v >= hi:
            return "confirmed"
        if v >= lo:
            return "partial"
        return "not_confirmed"

    emp = net["employment"]
    emp_status = "confirmed" if emp > 0.1 else "partial" if emp >= -0.1 else "not_confirmed"
    status = {
        "comm_deemphasize_easing": st(net["fed_communications"]),
        "comm_inflation_over_labor": st(net["fed_communications"]),
        "pricing_removes_cuts": st(net["market_pricing"]),
        "twoy_rises": st(net["market_pricing"], hi=0.25, lo=0.1),
        "inflation_upside": st(net["inflation"]),
        "employment_firm": emp_status,
        "spytlt_confirms": spytlt_confirms,  # computed from prices (compute_spytlt_signal)
    }
    return [{"id": i, "text": t, "status": status[i]} for i, t in CHECKLIST_ITEMS]


_QUOTE_ATTRIBUTION = re.compile(
    r"\b(said|says|stated|stating|told|noted|remarked|warned|added|declared)\b\s*[,:]?\s*"
    r"[\"'‘“]",
    re.IGNORECASE,
)


def contains_attributed_quote(text: str) -> bool:
    """True when `text` embeds a quotation attributed to a speaker ("Powell said, '...'").

    LLM-collected evidence_text can silently mangle quote spans — dropped words inside
    quote marks attributed to a named official are fabricated speech (found live: a
    garbled Powell quote from src_011 shipped in the public summary for two runs).
    Generated summaries must never emit such spans unless verified verbatim against the
    primary source, which scoring cannot do — so the summary layer refuses them wholesale.
    """
    return bool(_QUOTE_ATTRIBUTION.search(text or ""))


def top_source(sources: list[dict], bucket: str, direction: str | None = None) -> dict | None:
    """Highest-importance, most recent source in `bucket`; when `direction` is given,
    prefer sources voting that way (the summary's exemplar must not illustrate a
    'strongly tightening' bucket with a neutral source's text)."""
    ranked = sorted(
        (s for s in sources if s.get("bucket") == bucket),
        key=lambda s: (IMPORTANCE_RANK[s.get("importance", "medium")], s.get("published_at", "")),
        reverse=True,
    )
    if direction:
        for s in ranked:
            if s.get("direction") == direction:
                return s
    return ranked[0] if ranked else None


def _exemplar(bucket_scores: dict, sources: list[dict], bucket: str) -> str | None:
    """Headline-based citation for a bucket: the dominant-direction top source, cited as
    publisher + title. Never `evidence_text` — that is collector-generated prose whose
    quote spans cannot be verified verbatim (see contains_attributed_quote)."""
    dom = bucket_scores[bucket]["dominant"]
    src = top_source(sources, bucket, direction=dom if dom in ("easing", "tightening") else None)
    if not src:
        return None
    title = str(src.get("title") or "").strip().rstrip(".")
    publisher = str(src.get("publisher") or "").strip()
    if not title or contains_attributed_quote(title):
        return None
    return f"per {publisher}: {title}" if publisher else title


def build_summary(
    descriptor_label: str, shares: dict, bucket_scores: dict, sources: list[dict]
) -> tuple[str, list[str]]:
    t_pct = round(shares["tightening"] * 100)
    e_pct = round(shares["easing"] * 100)
    n_pct = round(shares["neutral"] * 100)
    inf_ex = _exemplar(bucket_scores, sources, "inflation")
    fed_ex = _exemplar(bucket_scores, sources, "fed_communications")
    bits = [
        f"Regime read: {descriptor_label}. Of the weighted evidence, {t_pct}% points "
        f"tightening, {n_pct}% mixed, and {e_pct}% easing."
    ]
    inf_bit = f"Inflation is {bucket_scores['inflation']['label']}"
    if inf_ex:
        inf_bit += f" ({inf_ex})"
    bits.append(inf_bit + ".")
    fed_bit = f"Fed communications are {bucket_scores['fed_communications']['label']}"
    if fed_ex:
        fed_bit += f" ({fed_ex})"
    bits.append(fed_bit + ".")
    bits.append(
        f"Employment is {bucket_scores['employment']['label']} and market pricing is "
        f"{bucket_scores['market_pricing']['label']}."
    )
    what = [
        "A second consecutive upside inflation surprise.",
        "Front-end (2Y) yields rising materially further over the intermeeting window.",
        "A Fed official explicitly pushing back against near-term cuts.",
        "Fed funds futures repricing from 'fewer cuts' toward outright hikes.",
    ]
    return " ".join(bits), what


def current_repo_regime() -> str:
    if not ic.EVENT_TRUTH_JSON.exists():
        return "Unknown"
    doc = json.loads(ic.EVENT_TRUTH_JSON.read_text(encoding="utf-8"))
    events = doc.get("events", [])
    return (events[-1].get("regime") if events else "Unknown") or "Unknown"


def update_history_series(
    today_str: str, net_lean: float, descriptor_label: str, conviction_level: str, new_count: int
) -> None:
    series = {"description": "Daily net-lean + regime-read log (trend chart + daily-log table).",
              "points": []}
    if ic.HISTORY_SERIES.exists():
        try:
            series = json.loads(ic.HISTORY_SERIES.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    points = [p for p in series.get("points", []) if p.get("date") != today_str]
    points.append({
        "date": today_str,
        "net_lean": net_lean,
        "inferred_regime": descriptor_label,
        "conviction": conviction_level,
        "new_this_run": new_count,
    })
    points.sort(key=lambda p: p["date"])
    series["points"] = points[-120:]  # retain ~120 days
    ic.HISTORY_SERIES.write_text(json.dumps(series, indent=2) + "\n", encoding="utf-8")


def empty_bucket_scores() -> dict:
    zero = {"easing": 0.0, "neutral": 0.0, "tightening": 0.0}
    return {
        b: {"shares": zero, "net": 0.0, "dominant": "neutral", "label": "no data", "n": 0,
            "n_sources": 0, "weight_sum": 0.0}
        for b in BUCKETS
    }


def preserve_stale(reason: str, now: str) -> int:
    """Re-emit the previous latest.json flagged stale; create an empty-but-valid one if none."""
    ic.ensure_dirs()
    if ic.LATEST.exists():
        doc = json.loads(ic.LATEST.read_text(encoding="utf-8"))
    else:
        doc = {
            "generated_at": now,
            "window_start": ic.latest_event_date() or "",
            "window_end": ic.today_iso(),
            "current_repo_regime": current_repo_regime(),
            "inferred_regime": "Mixed",
            "conviction": "Low",
            "evidence_shares": {"easing": 0.0, "neutral": 0.0, "tightening": 0.0},
            "net_lean": 0.0,
            "evidence_dir": "neutral",
            "bucket_scores": empty_bucket_scores(),
            "summary": "No regime-intelligence evidence has been collected yet.",
            "what_would_change_the_call": [],
            "checklist": [],
            "sources": [],
        }
    doc["stale"] = True
    doc["error_summary"] = reason
    ic.LATEST.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    print(f"Pipeline degraded — preserved previous snapshot as stale: {reason}")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Score regime intelligence into latest.json")
    p.add_argument("--next-fomc", default=None, help="ISO date of the next FOMC meeting (optional)")
    args = p.parse_args(argv)

    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    today = date.today()
    today_str = today.isoformat()

    if not ic.LATEST_RAW.exists():
        return preserve_stale("no latest_raw.json — collection never ran", now)

    raw = json.loads(ic.LATEST_RAW.read_text(encoding="utf-8"))
    sources = raw.get("sources", [])
    if raw.get("error") or not sources:
        return preserve_stale(raw.get("error") or "collection returned no sources", now)

    # Ensure every source carries a resolved evidentiary tier (derive for older sources
    # collected before claim_type existed) so weighting and the UI are consistent.
    for s in sources:
        s["claim_type"] = ic.claim_type_of(s)

    regime = current_repo_regime()
    events = cluster_events(sources, today)  # one vote per underlying event
    shares, _total = direction_shares(sources, today)
    ev_dir = evidence_dir(shares)
    label = descriptor(ev_dir, regime)
    net_lean = round(shares["tightening"] - shares["easing"], 4)
    bucket_scores = score_buckets(sources, today)
    conv = conviction(shares, len(events))  # evidence volume = distinct events
    summary, what = build_summary(label, shares, bucket_scores, sources)
    spytlt = compute_spytlt_signal(inferred_lean(ev_dir, regime), today)

    doc = {
        "generated_at": now,
        "run_id": raw.get("generated_at", now),
        "window_start": raw.get("window_start", ic.latest_event_date() or ""),
        "window_end": raw.get("window_end", today_str),
        "current_repo_regime": regime,
        "inferred_regime": label,
        "conviction": conv,
        "evidence_shares": shares,
        "net_lean": net_lean,
        "evidence_dir": ev_dir,
        "next_fomc_meeting": args.next_fomc,
        "new_this_run": raw.get("new_this_run", 0),
        "n_sources": len(sources),
        "n_events": len(events),
        "stale": False,
        "error_summary": None,
        "bucket_scores": bucket_scores,
        "summary": summary,
        "what_would_change_the_call": what,
        "checklist": build_checklist(bucket_scores, spytlt["status"] if spytlt else "unknown"),
        # Evidence behind the spytlt_confirms checklist item; null when prices failed.
        "spytlt": spytlt,
        "scoring": {
            "method": ("weighted vote-share over source direction, one vote per event "
                       "cluster (no magnitude averaging)"),
            "clustering": ("one vote per event_key; representative = max-weight source; "
                           "keyless sources are singleton clusters"),
            "tier_weights": ic.TIER_WEIGHTS,
            "claim_type_weights": CLAIM_TYPE_W,
            "importance_weights": IMPORTANCE_W,
            "confidence_weights": CONFIDENCE_W,
            "recency_decay": "0-7d:1.0, 8-14d:0.75, 15-30d:0.5, >30d:0.25 (Fed/official floor 0.5)",
        },
        "sources": sources,
    }

    ic.ensure_dirs()
    payload = json.dumps(doc, indent=2) + "\n"
    snapshot = ic.HISTORY_DIR / f"{today_str}.json"
    ic.LATEST.write_text(payload, encoding="utf-8")
    snapshot.write_text(payload, encoding="utf-8")
    update_history_series(today_str, net_lean, label, conv, doc["new_this_run"])

    t_pct = round(shares["tightening"] * 100)
    e_pct = round(shares["easing"] * 100)
    print(f"Scored {len(sources)} sources / {len(events)} events -> {label} "
          f"(conviction {conv}); "
          f"{t_pct}% tightening / {e_pct}% easing, net {net_lean:+.2f}.")
    print(f"  latest : {ic.LATEST}")
    print(f"  snapshot: {snapshot}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
