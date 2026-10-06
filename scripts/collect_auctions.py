"""Treasury auction monitor — is the long end clearing cleanly? (hard data, no LLM).

Pulls the last ~400 days of coupon auctions from the TreasuryDirect JSON API, keeps the
5/7/10/20/30-year notes and bonds (no TIPS, no FRNs), and scores each auction's demand
against the trailing 12 months of auctions of the same term: bid-to-cover, indirect
(foreign/real-money) share and primary-dealer share of competitive awards. Two weak
readings = "stress", one = "watch". The true tail (high yield vs the 1pm when-issued
yield) is NOT in the API, so tail_bp is always null and the doc says so.

Degrades to {available:false} if TreasuryDirect is unreachable; a failing calendar
fetch just leaves `upcoming` empty.

Usage:
    python scripts/collect_auctions.py
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta, timezone

import _intel_common as ic

AUCTIONED_URL = "https://www.treasurydirect.gov/TA_WS/securities/auctioned?days=400&format=json"
UPCOMING_URL = "https://www.treasurydirect.gov/TA_WS/securities/upcoming?format=json"
USER_AGENT = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")
AUCTION_MONITOR = ic.INTEL_DIR / "auction_monitor.json"
SOURCE = "TreasuryDirect TA_WS securities API"
NOTE_ON_TAIL = ("tail_bp is always null: the when-issued yield at the 1pm close, needed for "
                "the true tail/stop-through, is not published in the TreasuryDirect API.")

TERMS = ("5-Year", "7-Year", "10-Year", "20-Year", "30-Year")
LONG_END_TERMS = ("10-Year", "20-Year", "30-Year")
TRAILING_DAYS = 365
BC_GAP = 0.15  # bid-to-cover below trailing average by this much = weak
INDIRECT_GAP_PP = 8.0  # indirect share below average by this many pp = weak
DEALER_GAP_PP = 5.0  # dealer share above average by this many pp = weak


# ---------------------------------------------------------------- fetch


def fetch_json(url: str) -> list[dict]:
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=60, context=ic.ssl_context()) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    if not isinstance(payload, list):
        raise ValueError("unexpected TreasuryDirect payload")
    return payload


# ---------------------------------------------------------------- pure logic


def _num(v) -> float | None:
    try:
        return float(v) if v not in ("", None) else None
    except (TypeError, ValueError):
        return None


def _day(v) -> str | None:
    return str(v)[:10] if v else None


def is_coupon_in_scope(rec: dict) -> bool:
    """Nominal 5/7/10/20/30y notes and bonds; TIPS and FRNs excluded."""
    if rec.get("securityType") not in ("Note", "Bond"):
        return False
    if rec.get("tips") == "Yes" or rec.get("floatingRate") == "Yes":
        return False
    return term_of(rec) in TERMS


def term_of(rec: dict) -> str | None:
    """Reopenings carry securityTerm like '9-Year 10-Month'; `term` keeps '10-Year'."""
    return rec.get("term") or rec.get("originalSecurityTerm") or rec.get("securityTerm")


def pct(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or not denominator:
        return None
    return round(numerator / denominator * 100.0, 2)


def normalize(rec: dict) -> dict | None:
    """One auction result row from a raw API record; None if out of scope / no results."""
    if not is_coupon_in_scope(rec):
        return None
    bc = _num(rec.get("bidToCoverRatio"))
    if bc is None:
        return None  # announced but not yet auctioned
    competitive = _num(rec.get("competitiveAccepted")) or _num(rec.get("totalAccepted"))
    return {
        "cusip": rec.get("cusip"),
        "term": term_of(rec),
        "type": rec.get("securityType"),
        "reopening": rec.get("reopening") == "Yes",
        "auction_date": _day(rec.get("auctionDate")),
        "high_yield": _num(rec.get("highYield")),
        "bid_to_cover": bc,
        "indirect_pct": pct(_num(rec.get("indirectBidderAccepted")), competitive),
        "dealer_pct": pct(_num(rec.get("primaryDealerAccepted")), competitive),
    }


def _avg(values: list[float | None]) -> float | None:
    live = [v for v in values if v is not None]
    return round(sum(live) / len(live), 3) if live else None


def trailing_averages(auction: dict, universe: list[dict]) -> dict:
    """12-month trailing averages of same-term auctions STRICTLY BEFORE this one."""
    end = datetime.fromisoformat(auction["auction_date"]).date()
    begin = end - timedelta(days=TRAILING_DAYS)
    prior = [a for a in universe
             if a["term"] == auction["term"] and a["cusip"] != auction["cusip"]
             and begin.isoformat() <= a["auction_date"] < auction["auction_date"]]
    return {
        "bc_avg_12m": _avg([a["bid_to_cover"] for a in prior]),
        "indirect_avg_12m": _avg([a["indirect_pct"] for a in prior]),
        "dealer_avg_12m": _avg([a["dealer_pct"] for a in prior]),
    }


def classify(auction: dict, avgs: dict) -> tuple[list[str], str]:
    """Demand flags vs trailing averages; two = stress, one = watch, none = ok."""
    flags: list[str] = []
    bc, bc_avg = auction["bid_to_cover"], avgs["bc_avg_12m"]
    if bc is not None and bc_avg is not None and bc <= bc_avg - BC_GAP:
        flags.append(f"bid-to-cover {bc:.2f} below 12m avg {bc_avg:.2f} by >={BC_GAP:.2f}")
    ind, ind_avg = auction["indirect_pct"], avgs["indirect_avg_12m"]
    if ind is not None and ind_avg is not None and ind <= ind_avg - INDIRECT_GAP_PP:
        flags.append(f"indirect share {ind:.1f}% below 12m avg {ind_avg:.1f}% "
                     f"by >={INDIRECT_GAP_PP:.0f}pp")
    dlr, dlr_avg = auction["dealer_pct"], avgs["dealer_avg_12m"]
    if dlr is not None and dlr_avg is not None and dlr >= dlr_avg + DEALER_GAP_PP:
        flags.append(f"dealer share {dlr:.1f}% above 12m avg {dlr_avg:.1f}% "
                     f"by >={DEALER_GAP_PP:.0f}pp")
    status = "stress" if len(flags) >= 2 else "watch" if flags else "ok"
    return flags, status


def build_auctions(records: list[dict]) -> list[dict]:
    """Scored auction rows, newest first."""
    universe = [a for a in (normalize(r) for r in records) if a and a["auction_date"]]
    out: list[dict] = []
    for a in universe:
        avgs = trailing_averages(a, universe)
        flags, status = classify(a, avgs)
        out.append({**a, **avgs, "tail_bp": None, "flags": flags, "status": status})
    out.sort(key=lambda a: a["auction_date"], reverse=True)
    return out


def build_upcoming(records: list[dict]) -> list[dict]:
    rows = [{
        "term": term_of(r),
        "auction_date": _day(r.get("auctionDate")),
        "announcement_date": _day(r.get("announcementDate")),
        "offering_amount": r.get("offeringAmount") or None,
        "reopening": r.get("reopening") == "Yes",
    } for r in records if is_coupon_in_scope(r)]
    return sorted((r for r in rows if r["auction_date"]), key=lambda r: r["auction_date"])


def summarize(auctions: list[dict], upcoming: list[dict], today: date) -> dict:
    cutoff = (today - timedelta(days=90)).isoformat()
    recent = [a for a in auctions if a["auction_date"] >= cutoff]
    stress = sum(1 for a in recent if a["status"] == "stress")
    watch = sum(1 for a in recent if a["status"] == "watch")
    long_stress = next((a for a in auctions
                        if a["status"] == "stress" and a["term"] in LONG_END_TERMS), None)
    nxt = next((u for u in upcoming
                if u["term"] in LONG_END_TERMS and u["auction_date"] >= today.isoformat()), None)
    read = f"{stress} stress and {watch} watch auctions in the last 90 days"
    read += (f"; last long-end stress {long_stress['auction_date']} ({long_stress['term']})"
             if long_stress else "; no long-end stress in the window")
    read += (f"; next long-end auction {nxt['term']} on {nxt['auction_date']}."
             if nxt else "; no long-end auction on the calendar.")
    return {
        "last_long_end_stress": long_stress["auction_date"] if long_stress else None,
        "stress_count_90d": stress,
        "watch_count_90d": watch,
        "next_long_end_auction": ({"term": nxt["term"], "auction_date": nxt["auction_date"]}
                                  if nxt else None),
        "read": read,
    }


# ---------------------------------------------------------------- output


def write_unavailable(reason: str) -> None:
    """Write a clean 'pending' doc so the dashboard never shows broken rows."""
    ic.ensure_dirs()
    doc = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "available": False,
        "reason": reason,
        "source": SOURCE,
        "note_on_tail": NOTE_ON_TAIL,
        "auctions": [],
        "upcoming": [],
        "summary": {"last_long_end_stress": None, "stress_count_90d": 0, "watch_count_90d": 0,
                    "next_long_end_auction": None, "read": "unavailable"},
    }
    AUCTION_MONITOR.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    print(f"Auction monitor unavailable: {reason} -> wrote pending state.")


def main() -> int:
    try:
        records = fetch_json(AUCTIONED_URL)
    except (urllib.error.URLError, OSError, ValueError) as e:
        write_unavailable(f"TreasuryDirect unreachable: {str(e)[:80]}")
        return 0
    auctions = build_auctions(records)
    if not auctions:
        write_unavailable("TreasuryDirect returned no coupon auction results")
        return 0
    try:
        upcoming = build_upcoming(fetch_json(UPCOMING_URL))
    except (urllib.error.URLError, OSError, ValueError) as e:
        print(f"  upcoming calendar unavailable ({str(e)[:80]})")
        upcoming = []

    summary = summarize(auctions, upcoming, date.today())
    doc = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "available": True,
        "source": SOURCE,
        "method": ("Each 5/7/10/20/30y coupon auction scored vs the trailing 12 months of the "
                   "same term (excluding itself): bid-to-cover, indirect share and dealer share "
                   "of competitive awards; two weak readings = stress, one = watch (no LLM)."),
        "note_on_tail": NOTE_ON_TAIL,
        "auctions": auctions,
        "upcoming": upcoming,
        "summary": summary,
    }
    ic.ensure_dirs()
    AUCTION_MONITOR.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    print(f"Auction monitor: {summary['read']}")
    for a in auctions[:8]:
        print(f"  {a['auction_date']} {a['term']:8} b/c {a['bid_to_cover']:.2f}  "
              f"{a['status']:6} {'; '.join(a['flags'])}")
    print(f"  -> {AUCTION_MONITOR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
