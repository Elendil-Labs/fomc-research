"""Phase C long-end tools against inline fixtures written to a sandbox repo root
(flat layout: <root>/apps/fomc-dashboard/public/data/regime_intel/)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from fomc_server._paths import ENV_REPO_ROOT
from fomc_server.tools.longend import (
    AUCTION_STRESS_WINDOW_DAYS,
    get_auction_monitor,
    get_cftc_positioning,
    get_long_end_axis,
    get_long_end_watch,
)

GEN_AXIS = "2026-10-05T11:00:00+00:00"
GEN_AUCT = "2026-10-06T09:30:00+00:00"
GEN_CFTC = "2026-10-04T22:15:00+00:00"

PROV_KEYS = {"data_as_of", "retrieved_at", "source", "is_stale"}


def _indicator(
    iid: str, group: str, checked: bool | None, name: str | None = None
) -> dict:
    return {
        "id": iid,
        "name": name or iid,
        "unit": "%",
        "group": group,
        "latest": 1.0,
        "as_of": "2026-10-03",
        "change_20d": 0.1,
        "threshold": 1.5,
        "rule": f"{iid} >= 1.5",
        "checked": checked,
        "detail": f"{iid} detail",
        "note": "n",
    }


def axis_doc(**overrides) -> dict:
    doc = {
        "generated_at": GEN_AXIS,
        "available": True,
        "source": "FRED API (api.stlouisfed.org)",
        "method": "threshold rules",
        "analogs": {
            "2022-10-24": {"DFII10": 1.74, "ACMTP10": 0.45, "MOVE": 160.0},
            "2023-10-19": {"DFII10": 2.50, "ACMTP10": 0.47, "MOVE": 135.0},
        },
        "summary": {
            "checked": 3,
            "total": 9,
            "valuation_checked": 2,
            "valuation_total": 4,
            "timing_checked": 1,
            "timing_total": 5,
            "read": "3 of 9",
        },
        "indicators": [
            _indicator("DFII10", "valuation", True),
            _indicator("ACMTP10", "valuation", True),
            _indicator("T10YIE", "valuation", False),
            _indicator("MOVE", "valuation", False),
            _indicator("TWO_YEAR_STALL", "timing", True),
            _indicator("DGS10", "timing", False),
            _indicator("DGS30", "timing", None),
            _indicator("T10Y2Y", "timing", False),
            _indicator("FIVE_THIRTY", "timing", False),
            _indicator("MORTGAGE30US", "context", None),
        ],
    }
    doc.update(overrides)
    return doc


def _auction(term: str, day: str, status: str, cusip: str = "912810XX1") -> dict:
    return {
        "cusip": cusip,
        "term": term,
        "type": "Note" if term in ("2-Year", "5-Year", "7-Year", "10-Year") else "Bond",
        "reopening": False,
        "auction_date": day,
        "high_yield": 4.1,
        "bid_to_cover": 2.3,
        "bc_avg_12m": 2.5,
        "indirect_pct": 60.0,
        "indirect_avg_12m": 66.0,
        "dealer_pct": 20.0,
        "dealer_avg_12m": 14.0,
        "tail_bp": None,
        "flags": ["bid_to_cover_low"] if status != "ok" else [],
        "status": status,
    }


def auction_doc(**overrides) -> dict:
    doc = {
        "generated_at": GEN_AUCT,
        "available": True,
        "source": "TreasuryDirect auction results API",
        "method": "vs 12m averages",
        "note_on_tail": "tail requires a when-issued reference; null when absent",
        "auctions": [
            _auction("30-Year", "2026-09-25", "stress"),
            _auction("10-Year", "2026-09-24", "watch"),
            _auction("2-Year", "2026-09-22", "ok"),
            _auction("20-Year", "2026-09-17", "ok"),
            _auction("5-Year", "2026-09-16", "ok"),
            _auction("30-Year", "2026-08-28", "ok"),
            _auction("10-Year", "2026-08-27", "stress"),
        ],
        "upcoming": [
            {
                "term": "10-Year",
                "auction_date": "2026-10-08",
                "announcement_date": "2026-10-02",
                "offering_amount": 39_000_000_000,
                "reopening": True,
            }
        ],
        "summary": {
            "last_long_end_stress": "2026-09-25",
            "stress_count_90d": 2,
            "watch_count_90d": 1,
            "next_long_end_auction": {"term": "10-Year", "auction_date": "2026-10-08"},
            "read": "stress",
        },
    }
    doc.update(overrides)
    return doc


def _contract(cid: str, **kw) -> dict:
    c = {
        "id": cid,
        "name": cid.replace("_", " "),
        "as_of": "2026-09-30",
        "open_interest": 4_500_000,
        "am_net": 1_200_000,
        "am_net_change_1w": -5_000,
        "am_net_change_4w": -42_000,
        "lf_net": -900_000,
        "lf_net_change_1w": 3_000,
        "lf_net_change_4w": 25_000,
        "dealer_net": -100_000,
        "am_selling_streak_weeks": 3,
        "am_stopped_selling": False,
        "lf_net_26w_low": False,
        "history": [
            {"report_date": f"2026-0{m}-0{d}", "am_net": 1_000_000 + d, "lf_net": -800_000 - d}
            for m in (7, 8, 9)
            for d in (1, 2, 3, 4)
        ],
    }
    c.update(kw)
    return c


def cftc_doc(**overrides) -> dict:
    doc = {
        "generated_at": GEN_CFTC,
        "available": True,
        "source": "CFTC Traders in Financial Futures",
        "method": "net = long - short",
        "contracts": [
            _contract("UST_10Y"),
            _contract("ULTRA_10Y", am_stopped_selling=True, am_selling_streak_weeks=0),
            _contract("UST_BOND"),
            _contract("ULTRA_BOND", lf_net_26w_low=True),
        ],
        "summary": {
            "as_of": "2026-09-30",
            "real_money_distribution": True,
            "spec_capitulation": False,
            "am_stopped_selling_count": 1,
            "read": "real money still distributing",
        },
    }
    doc.update(overrides)
    return doc


@pytest.fixture
def intel_dir(tmp_path: Path, monkeypatch) -> Path:
    d = tmp_path / "apps" / "fomc-dashboard" / "public" / "data" / "regime_intel"
    d.mkdir(parents=True)
    monkeypatch.setenv(ENV_REPO_ROOT, str(tmp_path))
    return d


def _write(d: Path, name: str, doc: dict) -> None:
    (d / name).write_text(json.dumps(doc), encoding="utf-8")


def _write_all(d: Path, axis=None, auct=None, cftc=None) -> None:
    _write(d, "long_end_axis.json", axis or axis_doc())
    _write(d, "auction_monitor.json", auct or auction_doc())
    _write(d, "cftc_positioning.json", cftc or cftc_doc())


# ------------------------------------------------------------------ long-end axis


def test_long_end_axis_happy_path(intel_dir):
    _write(intel_dir, "long_end_axis.json", axis_doc())
    out = get_long_end_axis()
    assert "error" not in out and out["available"] is True
    assert out["summary"]["checked"] == 3
    assert set(out["analogs"]) == {"2022-10-24", "2023-10-19"}
    assert [i["id"] for i in out["indicators"]][:2] == ["DFII10", "ACMTP10"]
    assert out["upstream_source"].startswith("FRED")
    assert set(out["provenance"]) >= PROV_KEYS
    assert out["provenance"]["data_as_of"] == GEN_AXIS


def test_long_end_axis_available_false_passthrough(intel_dir):
    _write(intel_dir, "long_end_axis.json", axis_doc(available=False, indicators=[]))
    out = get_long_end_axis()
    assert out["available"] is False and "note" in out
    assert "indicators" not in out
    assert set(out["provenance"]) >= PROV_KEYS


def test_long_end_axis_missing_file_is_pending_not_error(intel_dir):
    out = get_long_end_axis()
    assert "error" not in out and out["available"] is False and "note" in out


def test_long_end_axis_corrupt_file_returns_error_dict(intel_dir):
    (intel_dir / "long_end_axis.json").write_text("[1,2,3]", encoding="utf-8")
    out = get_long_end_axis()
    assert isinstance(out, dict) and "error" in out


# ---------------------------------------------------------------- auction monitor


def test_auction_monitor_happy_path_newest_first(intel_dir):
    _write(intel_dir, "auction_monitor.json", auction_doc())
    out = get_auction_monitor()
    assert "error" not in out and out["available"] is True
    dates = [a["auction_date"] for a in out["auctions"]]
    assert dates == sorted(dates, reverse=True)
    assert out["n_auctions"] == 7 and out["n_matching"] == 7
    assert out["terms"] == ["10-Year", "2-Year", "20-Year", "30-Year", "5-Year"]
    assert out["upcoming"][0]["term"] == "10-Year"
    assert out["summary"]["last_long_end_stress"] == "2026-09-25"
    assert out["note_on_tail"]
    assert set(out["provenance"]) >= PROV_KEYS


def test_auction_monitor_terms_filter_is_spelling_tolerant(intel_dir):
    _write(intel_dir, "auction_monitor.json", auction_doc())
    out = get_auction_monitor(terms=["30y", "10-year"])
    assert {a["term"] for a in out["auctions"]} == {"30-Year", "10-Year"}
    assert out["n_auctions"] == 4
    assert out["terms"] == ["30y", "10-year"]


def test_auction_monitor_limit_keeps_newest(intel_dir):
    _write(intel_dir, "auction_monitor.json", auction_doc())
    out = get_auction_monitor(limit=2)
    assert [a["auction_date"] for a in out["auctions"]] == ["2026-09-25", "2026-09-24"]
    assert out["n_auctions"] == 2 and out["n_matching"] == 7


def test_auction_monitor_unknown_term_and_bad_limit_error(intel_dir):
    _write(intel_dir, "auction_monitor.json", auction_doc())
    out = get_auction_monitor(terms=["3-Year"])
    assert "error" in out and "available terms" in out["error"]
    assert "error" in get_auction_monitor(limit=0)


def test_auction_monitor_available_false_passthrough(intel_dir):
    _write(intel_dir, "auction_monitor.json", auction_doc(available=False, auctions=[]))
    out = get_auction_monitor()
    assert out["available"] is False and "note" in out and "auctions" not in out


def test_auction_monitor_missing_file_returns_error_dict(intel_dir):
    out = get_auction_monitor()
    assert isinstance(out, dict) and "error" in out


# ------------------------------------------------------------------------- cftc


def test_cftc_positioning_happy_path_history_off_by_default(intel_dir):
    _write(intel_dir, "cftc_positioning.json", cftc_doc())
    out = get_cftc_positioning()
    assert "error" not in out and out["available"] is True
    assert out["contract_ids"] == ["UST_10Y", "ULTRA_10Y", "UST_BOND", "ULTRA_BOND"]
    assert len(out["contracts"]) == 4
    assert all("history" not in c for c in out["contracts"])
    assert out["include_history"] is False
    assert out["summary"]["real_money_distribution"] is True
    assert set(out["provenance"]) >= PROV_KEYS


def test_cftc_positioning_include_history(intel_dir):
    _write(intel_dir, "cftc_positioning.json", cftc_doc())
    out = get_cftc_positioning(include_history=True)
    assert all(len(c["history"]) == 12 for c in out["contracts"])


def test_cftc_positioning_contract_filter(intel_dir):
    _write(intel_dir, "cftc_positioning.json", cftc_doc())
    out = get_cftc_positioning(contract="ultra_bond")
    assert [c["id"] for c in out["contracts"]] == ["ULTRA_BOND"]
    assert out["contracts"][0]["lf_net_26w_low"] is True
    assert "error" in get_cftc_positioning(contract="ES")


def test_cftc_positioning_available_false_and_missing(intel_dir):
    out = get_cftc_positioning()
    assert isinstance(out, dict) and "error" in out
    _write(intel_dir, "cftc_positioning.json", cftc_doc(available=False, contracts=[]))
    out = get_cftc_positioning()
    assert out["available"] is False and "note" in out and "contracts" not in out


# ---------------------------------------------------------------- composite watch


def _box(out: dict, bid: str) -> dict:
    return next(b for b in out["boxes"] if b["id"] == bid)


def test_watch_merges_all_three_sources(intel_dir):
    _write_all(intel_dir)
    out = get_long_end_watch()
    assert "error" not in out
    ids = [b["id"] for b in out["boxes"]]
    # context-group indicators are excluded; the three flow boxes are appended
    assert "MORTGAGE30US" not in ids
    assert ids[-3:] == ["AUCTION_STRESS", "REAL_MONEY_SELLING", "SPEC_CAPITULATION"]
    assert len(ids) == 9 + 3
    # axis: 3 checked of 8 scored (DGS30 is null -> unknown); flow: auction yes,
    # real-money no (distribution still running), spec no
    assert out["checked"] == 4
    assert out["total"] == 11 and out["unknown"] == 1
    assert out["valuation_checked"] == 2 and out["valuation_total"] == 4
    assert out["timing_checked"] == 2 and out["timing_total"] == 7
    assert out["read"].startswith("4 of 11 boxes checked; valuation boxes 2/4, timing boxes 2/7")
    assert out["missing"] == []
    assert out["as_of"] == GEN_AUCT  # max generated_at of the three
    assert set(out["provenance"]) == {"long_end_axis", "auction_monitor", "cftc_positioning"}
    assert all(set(p) >= PROV_KEYS for p in out["provenance"].values())


def test_watch_auction_stress_within_window_is_checked(intel_dir):
    _write_all(intel_dir)
    box = _box(get_long_end_watch(), "AUCTION_STRESS")
    assert box["group"] == "timing" and box["checked"] is True
    assert "30-Year auction on 2026-09-25" in box["detail"]
    assert "11d before snapshot" in box["detail"]


def test_watch_auction_stress_older_than_window_is_unchecked(intel_dir):
    old = auction_doc()
    old["summary"]["last_long_end_stress"] = "2026-08-27"
    _write_all(intel_dir, auct=old)
    box = _box(get_long_end_watch(), "AUCTION_STRESS")
    assert box["checked"] is False
    assert "10-Year auction on 2026-08-27" in box["detail"]
    assert "40d before snapshot" in box["detail"]
    assert 40 > AUCTION_STRESS_WINDOW_DAYS


def test_watch_auction_stress_accepts_object_ref_and_none(intel_dir):
    doc = auction_doc()
    doc["summary"]["last_long_end_stress"] = {"term": "20-Year", "auction_date": "2026-10-01"}
    _write_all(intel_dir, auct=doc)
    box = _box(get_long_end_watch(), "AUCTION_STRESS")
    assert box["checked"] is True and "20-Year auction on 2026-10-01" in box["detail"]

    doc["summary"]["last_long_end_stress"] = None
    _write_all(intel_dir, auct=doc)
    box = _box(get_long_end_watch(), "AUCTION_STRESS")
    assert box["checked"] is False and "no long-end auction stress" in box["detail"]


def test_watch_real_money_box_is_inverse_of_distribution_flag(intel_dir):
    _write_all(intel_dir)  # real_money_distribution True -> still selling -> unchecked
    box = _box(get_long_end_watch(), "REAL_MONEY_SELLING")
    assert box["group"] == "timing" and box["checked"] is False
    assert "stopped selling on 1/4 contracts" in box["detail"]
    assert "UST_10Y asset-manager net Δ4w -42,000" in box["detail"]

    doc = cftc_doc()
    doc["summary"]["real_money_distribution"] = False
    doc["summary"]["am_stopped_selling_count"] = 4
    _write_all(intel_dir, cftc=doc)
    box = _box(get_long_end_watch(), "REAL_MONEY_SELLING")
    assert box["checked"] is True and "4/4 contracts" in box["detail"]


def test_watch_spec_capitulation_box(intel_dir):
    _write_all(intel_dir)
    box = _box(get_long_end_watch(), "SPEC_CAPITULATION")
    assert box["group"] == "timing" and box["checked"] is False
    assert "1/4 contracts (ULTRA_BOND)" in box["detail"]

    doc = cftc_doc()
    doc["summary"]["spec_capitulation"] = True
    _write_all(intel_dir, cftc=doc)
    assert _box(get_long_end_watch(), "SPEC_CAPITULATION")["checked"] is True


def test_watch_missing_cftc_degrades_box_by_box(intel_dir):
    _write(intel_dir, "long_end_axis.json", axis_doc())
    _write(intel_dir, "auction_monitor.json", auction_doc())
    out = get_long_end_watch()
    assert "error" not in out
    assert len(out["missing"]) == 1 and out["missing"][0].startswith("cftc_positioning")
    assert _box(out, "REAL_MONEY_SELLING")["checked"] is None
    assert _box(out, "SPEC_CAPITULATION")["checked"] is None
    assert _box(out, "AUCTION_STRESS")["checked"] is True
    assert out["total"] == 9 and out["checked"] == 4 and out["unknown"] == 3
    assert out["provenance"]["cftc_positioning"] is None
    assert "missing: cftc_positioning" in out["read"]
    assert out["as_of"] == GEN_AUCT


def test_watch_axis_available_false_counts_as_missing(intel_dir):
    _write_all(intel_dir, axis=axis_doc(available=False, indicators=[]))
    out = get_long_end_watch()
    assert [b["id"] for b in out["boxes"]] == [
        "AUCTION_STRESS",
        "REAL_MONEY_SELLING",
        "SPEC_CAPITULATION",
    ]
    assert out["missing"] == ["long_end_axis: available=false"]
    assert out["provenance"]["long_end_axis"] is not None  # file existed, so stamped
    assert out["valuation_total"] == 0 and out["timing_total"] == 3


def test_watch_corrupt_file_never_raises(intel_dir):
    _write_all(intel_dir)
    (intel_dir / "auction_monitor.json").write_text("{not json", encoding="utf-8")
    out = get_long_end_watch()
    assert "error" not in out
    assert any(m.startswith("auction_monitor: JSONDecodeError") for m in out["missing"])
    assert _box(out, "AUCTION_STRESS")["checked"] is None
