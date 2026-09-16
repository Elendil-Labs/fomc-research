"""Tests for the market-pricing axis computation (pure logic; no network)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import collect_market_pricing as mp  # noqa: E402


def test_weights_sum_to_one():
    assert round(sum(ind["weight"] for ind in mp.INDICATORS), 6) == 1.0


def test_output_file_name_is_distinct_from_news_bucket():
    # A news bucket named market_pricing already exists; the axis file must not shadow it.
    assert mp.MARKET_PRICING.name == "market_pricing_axis.json"


def test_signal_change_2y_direction_and_dead_zone():
    # DGS2 rising = market pricing tighter policy (+1); dead zone 0.10pp.
    assert mp.signal_change(0.30, up_tightening=True, dead=0.10) == 1
    assert mp.signal_change(-0.30, up_tightening=True, dead=0.10) == -1
    assert mp.signal_change(0.08, up_tightening=True, dead=0.10) == 0
    assert mp.signal_change(-0.10, up_tightening=True, dead=0.10) == 0  # boundary inclusive


def test_signal_spread_curve_slope_thresholds():
    # 10y-2y: deeply inverted -> easing priced (-1); steep -> tightening (+1).
    assert mp.signal_spread(-0.30, hi_thr=0.75, lo_thr=-0.20) == -1
    assert mp.signal_spread(0.90, hi_thr=0.75, lo_thr=-0.20) == 1
    assert mp.signal_spread(0.30, hi_thr=0.75, lo_thr=-0.20) == 0


def test_signal_spread_funds_path_thresholds():
    # 2y - DFF: 2y well below funds = cuts priced (-1); above = hikes priced (+1).
    assert mp.signal_spread(-0.40, hi_thr=0.25, lo_thr=-0.25) == -1
    assert mp.signal_spread(0.40, hi_thr=0.25, lo_thr=-0.25) == 1
    assert mp.signal_spread(0.10, hi_thr=0.25, lo_thr=-0.25) == 0


def test_change_90d_uses_obs_nearest_90_days_back():
    series = [
        ("2026-03-01", 3.50),  # ~90d before latest
        ("2026-04-01", 3.70),
        ("2026-06-01", 3.90),  # latest
    ]
    val, as_of, chg, prior = mp.change_90d(series)
    assert val == 3.90
    assert as_of == "2026-06-01"
    assert round(chg, 6) == 0.40
    assert prior == "2026-03-01"
    assert mp.window_days(as_of, prior) == 92


def test_change_90d_truncated_series_reports_actual_prior_date():
    # Nothing >=90d back: falls back to the earliest obs, and the returned prior date
    # lets the detail string report the ACTUAL window instead of claiming Δ90d.
    series = [("2026-05-15", 3.70), ("2026-06-01", 3.90)]
    val, as_of, chg, prior = mp.change_90d(series)
    assert (val, as_of, prior) == (3.90, "2026-06-01", "2026-05-15")
    assert round(chg, 6) == 0.20
    assert mp.window_days(as_of, prior) == 17  # honest: 17d, not 90d


def test_label_thresholds():
    assert mp.label(-0.5) == "loosening"
    assert mp.label(-0.25) == "loosening"
    assert mp.label(0.0) == "neutral"
    assert mp.label(0.25) == "tightening"
    assert mp.label(0.5) == "tightening"


def test_net_liquidity_converts_rrp_billions_to_millions(monkeypatch):
    # WALCL/WTREGEN in $M; RRPONTSYD in $B — must be scaled x1000 before combining.
    fixtures = {
        # series: two obs 90+ days apart -> change = latest - first
        "WALCL": [("2026-03-01", 6_700_000.0), ("2026-06-01", 6_600_000.0)],  # -100,000 $M
        "WTREGEN": [("2026-03-01", 700_000.0), ("2026-06-01", 750_000.0)],  # +50,000 $M
        "RRPONTSYD": [("2026-03-01", 100.0), ("2026-06-01", 50.0)],  # -50 $B = -50,000 $M
    }
    monkeypatch.setattr(mp, "fetch_series", lambda sid, key, start: fixtures[sid])
    level, as_of, change, prior = mp.net_liquidity_90d("k", "2026-02-01")
    assert as_of == "2026-06-01"
    assert prior == "2026-03-01"
    # level = 6,600,000 - 750,000 - 50*1000 = 5,800,000 $M (~$5.8T)
    assert level == 5_800_000.0
    # change = -100,000 - (+50,000) - (-50,000) = -100,000 $M (draining)
    assert change == -100_000.0
    # A -$100B move sits ON the $100B dead zone -> neutral; beyond it -> tightening.
    assert mp.signal_change(change, up_tightening=False, dead=100_000) == 0
    assert mp.signal_change(change - 1, up_tightening=False, dead=100_000) == 1


def test_evaluate_composite_row_and_partial_failure(monkeypatch):
    """Composite row is computed; failed series degrade to signal 0, never raise."""
    fixtures = {
        "DGS2": [("2026-03-01", 3.50), ("2026-06-01", 3.80)],
        "DGS10": [("2026-03-01", 4.10), ("2026-06-01", 4.20)],
        "DFF": [("2026-03-01", 4.25), ("2026-06-01", 4.25)],
        "WALCL": [("2026-03-01", 6_700_000.0), ("2026-06-01", 6_500_000.0)],
        "WTREGEN": [("2026-03-01", 700_000.0), ("2026-06-01", 700_000.0)],
    }

    def fake_fetch(sid: str, key: str, start: str) -> list[tuple[str, float]]:
        if sid == "RRPONTSYD":
            raise ValueError("no observations for RRPONTSYD")
        return fixtures[sid]

    monkeypatch.setattr(mp, "fetch_series", fake_fetch)
    rows = mp.evaluate("k", "2026-02-01")
    by_id = {r["id"]: r for r in rows}
    assert by_id["DGS2"]["signal"] == 1  # +0.30 > 0.10 dead zone
    assert by_id["T10Y2Y"]["signal"] == 0  # slope +0.40, between thresholds
    assert by_id["DGS2_DFF"]["signal"] == -1  # 2y 0.45 below funds -> cuts priced
    # NET_LIQUIDITY depends on RRPONTSYD, which failed -> graceful unavailable row.
    nl = by_id["NET_LIQUIDITY"]
    assert nl["signal"] == 0 and nl["latest"] is None and nl["detail"] == "unavailable"


def test_aggregate_renormalizes_over_live_rows_only():
    """The review's failure case: DGS2 + DGS2_DFF down (0.6 of weight) must not cap
    the lean at 0.4 when the surviving indicators are unanimous."""
    rows = [
        {"id": "DGS2", "weight": 0.30, "latest": None, "signal": 0},
        {"id": "T10Y2Y", "weight": 0.20, "latest": 0.9, "signal": 1},
        {"id": "DGS2_DFF", "weight": 0.30, "latest": None, "signal": 0},
        {"id": "NET_LIQUIDITY", "weight": 0.20, "latest": 5_800_000.0, "signal": 1},
    ]
    net, coverage = mp.aggregate(rows)
    assert net == 1.0  # unanimous live indicators -> full lean, not 0.4
    assert coverage == 0.4  # but the degradation is visible


def test_aggregate_full_coverage_matches_plain_weighted_sum():
    rows = [
        {"id": "a", "weight": 0.5, "latest": 1.0, "signal": 1},
        {"id": "b", "weight": 0.5, "latest": 1.0, "signal": 0},
    ]
    net, coverage = mp.aggregate(rows)
    assert net == 0.5
    assert coverage == 1.0


def test_write_unavailable_writes_pending_doc(tmp_path, monkeypatch):
    monkeypatch.setattr(mp, "MARKET_PRICING", tmp_path / "market_pricing_axis.json")
    mp.write_unavailable("FRED_API_KEY not set")
    doc = json.loads((tmp_path / "market_pricing_axis.json").read_text(encoding="utf-8"))
    assert doc["available"] is False
    assert doc["label"] == "neutral"
    assert doc["net_lean"] == 0.0
    assert doc["indicators"] == []
