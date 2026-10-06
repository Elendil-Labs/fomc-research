"""Tests for the Treasury auction monitor (pure logic; no network)."""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import collect_auctions as au  # noqa: E402


def _rec(cusip: str, term: str, day: str, bc: float, indirect: float, dealer: float,
         competitive: float = 100.0, **extra) -> dict:
    """Raw TreasuryDirect-shaped record (strings, like the API)."""
    base = {
        "cusip": cusip, "securityType": "Bond" if term in ("20-Year", "30-Year") else "Note",
        "securityTerm": term, "term": term, "originalSecurityTerm": term,
        "auctionDate": f"{day}T00:00:00", "announcementDate": f"{day}T00:00:00",
        "highYield": "4.5000", "bidToCoverRatio": f"{bc:.6f}",
        "competitiveAccepted": str(int(competitive * 1e9)),
        "indirectBidderAccepted": str(int(indirect * 1e9)),
        "primaryDealerAccepted": str(int(dealer * 1e9)),
        "directBidderAccepted": "0", "totalAccepted": str(int((competitive + 1) * 1e9)),
        "offeringAmount": "70000000000", "reopening": "No", "tips": "No", "floatingRate": "No",
    }
    base.update(extra)
    return base


def test_scope_filter_keeps_nominal_coupons_only():
    assert au.is_coupon_in_scope(_rec("a", "5-Year", "2026-09-23", 2.2, 50, 10))
    assert au.is_coupon_in_scope(_rec("b", "30-Year", "2026-09-23", 2.2, 50, 10))
    assert not au.is_coupon_in_scope(_rec("c", "10-Year", "2026-09-23", 2.2, 50, 10, tips="Yes"))
    assert not au.is_coupon_in_scope(_rec("d", "2-Year", "2026-09-23", 2.2, 50, 10,
                                          floatingRate="Yes"))
    assert not au.is_coupon_in_scope(_rec("e", "3-Year", "2026-09-23", 2.2, 50, 10))
    assert not au.is_coupon_in_scope({**_rec("f", "10-Year", "2026-09-23", 2.2, 50, 10),
                                      "securityType": "Bill"})


def test_reopening_uses_term_not_security_term():
    rec = _rec("r", "10-Year", "2026-10-07", 2.4, 60, 12,
               securityTerm="9-Year 10-Month", reopening="Yes")
    assert au.term_of(rec) == "10-Year"
    row = au.normalize(rec)
    assert row["term"] == "10-Year" and row["reopening"] is True


def test_normalize_pct_math_and_fallbacks():
    row = au.normalize(_rec("x", "5-Year", "2026-09-23", 2.21, 37.837082, 10.99,
                            competitive=69.668682))
    assert row["bid_to_cover"] == 2.21
    assert row["indirect_pct"] == round(37.837082 / 69.668682 * 100, 2)  # 54.31
    assert row["dealer_pct"] == round(10.99 / 69.668682 * 100, 2)  # 15.77
    assert row["auction_date"] == "2026-09-23"
    assert row["high_yield"] == 4.5
    # competitiveAccepted missing -> totalAccepted is the denominator.
    rec = _rec("y", "5-Year", "2026-09-23", 2.2, 50, 10, competitive=100.0)
    rec["competitiveAccepted"] = ""
    assert au.normalize(rec)["indirect_pct"] == round(50 / 101 * 100, 2)
    # Announced-only record (no results yet) is dropped.
    rec = _rec("z", "5-Year", "2026-10-28", 2.2, 50, 10)
    rec["bidToCoverRatio"] = ""
    assert au.normalize(rec) is None
    assert au.pct(None, 100) is None and au.pct(10, 0) is None


def _universe() -> list[dict]:
    # Four prior 5-year auctions in the trailing year, one 2y-old, one 7-year, then the
    # 2026-09-23 weak 5-year.
    recs = [
        _rec("p1", "5-Year", "2025-11-25", 2.40, 65, 10),
        _rec("p2", "5-Year", "2026-02-24", 2.45, 70, 9),
        _rec("p3", "5-Year", "2026-05-27", 2.35, 66, 11),
        _rec("p4", "5-Year", "2026-08-26", 2.40, 67, 10),
        _rec("old", "5-Year", "2024-09-01", 1.00, 10, 60),  # outside 365d: ignored
        _rec("s7", "7-Year", "2026-09-24", 1.00, 10, 60),  # other term: ignored
        _rec("t", "5-Year", "2026-09-23", 2.21, 54.3, 15.8),
    ]
    return [au.normalize(r) for r in recs]


def test_trailing_averages_exclude_self_other_terms_and_stale():
    universe = _universe()
    target = next(a for a in universe if a["cusip"] == "t")
    avgs = au.trailing_averages(target, universe)
    assert avgs["bc_avg_12m"] == round((2.40 + 2.45 + 2.35 + 2.40) / 4, 3)  # 2.4
    assert avgs["indirect_avg_12m"] == round((65 + 70 + 66 + 67) / 4, 3)  # 67.0
    assert avgs["dealer_avg_12m"] == 10.0
    # Earliest auction has no priors -> None averages, no flags.
    first = next(a for a in universe if a["cusip"] == "old")
    assert au.trailing_averages(first, universe) == {"bc_avg_12m": None, "indirect_avg_12m": None,
                                                     "dealer_avg_12m": None}
    assert au.classify(first, au.trailing_averages(first, universe)) == ([], "ok")


def test_classify_thresholds_and_boundaries():
    avgs = {"bc_avg_12m": 2.40, "indirect_avg_12m": 67.0, "dealer_avg_12m": 10.0}
    stress = {"bid_to_cover": 2.21, "indirect_pct": 54.3, "dealer_pct": 15.8}
    flags, status = au.classify(stress, avgs)
    assert status == "stress" and len(flags) == 3
    # Exactly on each boundary still flags.
    on = {"bid_to_cover": 2.25, "indirect_pct": 59.0, "dealer_pct": 15.0}
    assert au.classify(on, avgs)[1] == "stress"
    # One tick inside each boundary -> ok.
    inside = {"bid_to_cover": 2.26, "indirect_pct": 59.1, "dealer_pct": 14.9}
    assert au.classify(inside, avgs) == ([], "ok")
    # Single flag -> watch.
    one = {"bid_to_cover": 2.20, "indirect_pct": 67.0, "dealer_pct": 10.0}
    flags, status = au.classify(one, avgs)
    assert status == "watch" and flags[0].startswith("bid-to-cover 2.20 below 12m avg 2.40")
    # Missing pct -> that rule skipped, never raises.
    assert au.classify({"bid_to_cover": 2.20, "indirect_pct": None, "dealer_pct": None},
                       avgs)[1] == "watch"


def test_build_auctions_sorted_newest_first_with_status_and_null_tail():
    recs = [
        _rec("p1", "5-Year", "2025-11-25", 2.40, 65, 10),
        _rec("p2", "5-Year", "2026-02-24", 2.45, 70, 9),
        _rec("p3", "5-Year", "2026-05-27", 2.35, 66, 11),
        _rec("p4", "5-Year", "2026-08-26", 2.40, 67, 10),
        _rec("t", "5-Year", "2026-09-23", 2.21, 54.3, 15.8),
        _rec("tips", "10-Year", "2026-09-17", 2.0, 50, 10, tips="Yes"),
    ]
    rows = au.build_auctions(recs)
    assert [r["cusip"] for r in rows] == ["t", "p4", "p3", "p2", "p1"]
    top = rows[0]
    assert top["status"] == "stress" and top["tail_bp"] is None
    assert top["bc_avg_12m"] == 2.4 and top["indirect_avg_12m"] == 67.0
    assert rows[-1]["status"] == "ok" and rows[-1]["bc_avg_12m"] is None


def test_build_upcoming_filters_and_sorts():
    recs = [
        _rec("u2", "30-Year", "2026-10-08", 0, 0, 0, reopening="Yes",
             securityTerm="29-Year 10-Month"),
        _rec("u1", "10-Year", "2026-10-07", 0, 0, 0),
        _rec("u3", "3-Year", "2026-10-06", 0, 0, 0),
    ]
    up = au.build_upcoming(recs)
    assert [u["term"] for u in up] == ["10-Year", "30-Year"]
    assert up[1] == {"term": "30-Year", "auction_date": "2026-10-08",
                     "announcement_date": "2026-10-08", "offering_amount": "70000000000",
                     "reopening": True}


def test_summarize_counts_and_next_long_end():
    auctions = [
        {"term": "5-Year", "auction_date": "2026-09-23", "status": "stress"},
        {"term": "30-Year", "auction_date": "2026-09-10", "status": "stress"},
        {"term": "10-Year", "auction_date": "2026-09-09", "status": "watch"},
        {"term": "20-Year", "auction_date": "2026-06-01", "status": "stress"},  # > 90d old
    ]
    upcoming = [
        {"term": "5-Year", "auction_date": "2026-10-06"},
        {"term": "10-Year", "auction_date": "2026-10-07"},
        {"term": "30-Year", "auction_date": "2026-10-08"},
    ]
    s = au.summarize(auctions, upcoming, date(2026, 10, 6))
    assert s["stress_count_90d"] == 2 and s["watch_count_90d"] == 1
    assert s["last_long_end_stress"] == "2026-09-10"
    assert s["next_long_end_auction"] == {"term": "10-Year", "auction_date": "2026-10-07"}
    assert s["read"] == ("2 stress and 1 watch auctions in the last 90 days; last long-end "
                         "stress 2026-09-10 (30-Year); next long-end auction 10-Year on "
                         "2026-10-07.")
    empty = au.summarize([], [], date(2026, 10, 6))
    assert empty["last_long_end_stress"] is None and empty["next_long_end_auction"] is None


def test_write_unavailable_writes_pending_doc(tmp_path, monkeypatch):
    monkeypatch.setattr(au, "AUCTION_MONITOR", tmp_path / "auction_monitor.json")
    au.write_unavailable("TreasuryDirect unreachable")
    doc = json.loads((tmp_path / "auction_monitor.json").read_text(encoding="utf-8"))
    assert doc["available"] is False
    assert doc["auctions"] == [] and doc["upcoming"] == []
    assert doc["summary"]["stress_count_90d"] == 0
    assert "tail_bp" in doc["note_on_tail"]
