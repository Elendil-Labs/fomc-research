"""Tests for the long-end bottom watch (pure logic; no network)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import collect_long_end as le  # noqa: E402


def _daily(values: list[float]) -> list[tuple[str, float]]:
    """Synthetic daily series; dates only need to be increasing."""
    def day(i: int) -> str:
        return f"2026-09-{i + 1:02d}" if i < 30 else f"2026-10-{i - 29:02d}"
    return [(day(i), v) for i, v in enumerate(values)]


def _flat(level: float, n: int = 25) -> list[tuple[str, float]]:
    return _daily([level] * n)


def test_output_file_and_analogs():
    assert le.LONG_END.name == "long_end_axis.json"
    assert le.ANALOGS["2023-10-19"] == {"DFII10": 2.52, "ACMTP10": 0.45, "MOVE": 130}
    assert le.ANALOGS["2022-10-24"]["ACMTP10"] == -0.10


def test_level_rules_thresholds_and_boundaries():
    assert le.check_level(2.52, 2.52) is True  # boundary inclusive
    assert le.check_level(2.51, 2.52) is False
    assert le.check_level(0.45, 0.45) is True
    assert le.check_level(130, 130) is True
    assert le.check_level(129.9, 130) is False


def test_change_rule_breakeven_not_running():
    assert le.check_change(0.05, 0.05) is True  # boundary inclusive
    assert le.check_change(0.06, 0.05) is False
    assert le.check_change(-0.20, 0.05) is True
    assert le.check_change(None, 0.05) is None


def test_change_n_uses_observation_offset():
    s = _daily([1.0, 1.1, 1.2, 1.3, 1.4])
    assert le.change_n(s, 2) == round(1.4 - 1.2, 4)
    assert le.change_n(s, 4) == round(1.4 - 1.0, 4)
    assert le.change_n(s, 5) is None  # window too short


def test_two_year_stall_checked_when_front_end_off_highs_and_long_end_at_highs():
    dgs2 = _daily([5.01] * 20 + [4.89])  # 0.12pp below its 20d max
    dgs30 = _daily([5.55] * 20 + [5.60])  # at its 20d max
    dist, checked, detail = le.two_year_stall(dgs2, dgs30)
    assert dist == round(4.89 - 5.01, 4)
    assert checked is True
    assert "2y 4.89 is 0.12pp below its 20d max 5.01" in detail
    assert "30y 5.60 is 0.00pp below its 20d max 5.60" in detail


def test_two_year_stall_boundaries():
    # 2y exactly 0.05 below max -> counts; 30y exactly 0.05 below max -> still "at highs".
    dgs2 = _daily([5.00] * 20 + [4.95])
    dgs30 = _daily([5.60] * 20 + [5.55])
    assert le.two_year_stall(dgs2, dgs30)[1] is True
    # 2y only 0.04 off -> not stalled.
    assert le.two_year_stall(_daily([5.00] * 20 + [4.96]), dgs30)[1] is False
    # 30y 0.06 off its highs -> long end not making highs.
    assert le.two_year_stall(dgs2, _daily([5.60] * 20 + [5.54]))[1] is False


def test_two_year_stall_only_looks_back_20_observations():
    # A 5.30 print 25 days ago must not count as the 20d max.
    dgs2 = _daily([5.30] + [5.00] * 20 + [4.90])
    dgs30 = _flat(5.60, 22)
    dist, checked, _ = le.two_year_stall(dgs2, dgs30)
    assert dist == round(4.90 - 5.00, 4)
    assert checked is True


def test_build_indicators_groups_rules_and_context(monkeypatch):
    series = {
        "DFII10": _daily([2.80] * 20 + [2.90]),
        "ACMTP10": _flat(0.85),
        "T10YIE": _daily([2.30] * 20 + [2.40]),  # +0.10 in 20d -> inflation running
        "MOVE": _flat(110),
        "DGS2": _daily([5.01] * 20 + [4.89]),
        "DGS5": _flat(5.00),
        "DGS10": _flat(5.20),
        "DGS30": _daily([5.55] * 20 + [5.60]),
        "MORTGAGE30US": [("2026-09-04", 6.9), ("2026-09-11", 6.9), ("2026-09-18", 7.0),
                         ("2026-09-25", 7.1), ("2026-10-02", 7.2)],
    }
    rows = le.build_indicators(series)
    by_id = {r["id"]: r for r in rows}
    assert [r["id"] for r in rows] == [i["id"] for i in le.INDICATORS]
    assert by_id["DFII10"]["checked"] is True and by_id["DFII10"]["latest"] == 2.90
    assert by_id["ACMTP10"]["checked"] is True
    assert by_id["T10YIE"]["checked"] is False and by_id["T10YIE"]["change_20d"] == 0.10
    assert by_id["MOVE"]["checked"] is False
    assert by_id["TWO_YEAR_STALL"]["checked"] is True
    assert by_id["TWO_YEAR_STALL"]["latest"] == round(4.89 - 5.01, 4)
    # Context rows: never checked, spreads computed on matching dates.
    for cid in ("DGS10", "DGS30", "T10Y2Y", "FIVE_THIRTY", "MORTGAGE30US"):
        assert by_id[cid]["checked"] is None and by_id[cid]["group"] == "context"
    assert by_id["T10Y2Y"]["latest"] == round(5.20 - 4.89, 4)
    assert by_id["FIVE_THIRTY"]["latest"] == round(5.60 - 5.00, 4)
    assert by_id["MORTGAGE30US"]["change_20d"] == round(7.2 - 6.9, 4)  # 4 weekly obs back

    s = le.summarize(rows)
    assert s == {"checked": 3, "total": 5, "valuation_checked": 2, "valuation_total": 3,
                 "timing_checked": 1, "timing_total": 2,
                 "read": "2 of 3 valuation boxes and 1 of 2 timing boxes checked; "
                         "bottoms have needed the timing boxes."}


def test_single_series_failure_marks_indicator_unavailable_and_keeps_going():
    series = {
        "DFII10": _flat(2.90), "ACMTP10": None, "T10YIE": _flat(2.3), "MOVE": None,
        "DGS2": _flat(4.89), "DGS5": _flat(5.0), "DGS10": _flat(5.2), "DGS30": _flat(5.6),
        "MORTGAGE30US": None,
    }
    rows = le.build_indicators(series)
    by_id = {r["id"]: r for r in rows}
    for cid in ("ACMTP10", "MOVE", "MORTGAGE30US"):
        assert by_id[cid]["checked"] is None
        assert by_id[cid]["latest"] is None
        assert by_id[cid]["note"] == "unavailable"
    assert by_id["DFII10"]["checked"] is True
    s = le.summarize(rows)
    assert s["valuation_checked"] == 2 and s["timing_checked"] == 0
    assert s["read"].endswith("(2 boxes unavailable)")


def test_stall_unavailable_when_dgs2_missing():
    series = {k: _flat(1.0) for k in le.FRED_SERIES}
    series["DGS2"] = None
    by_id = {r["id"]: r for r in le.build_indicators(series)}
    assert by_id["TWO_YEAR_STALL"]["checked"] is None
    assert by_id["T10Y2Y"]["checked"] is None and by_id["T10Y2Y"]["latest"] is None


def test_parse_acm_reads_ddmonyyyy_dates_and_tp10_column(monkeypatch):
    rows = [
        {0: "DATE", 1: "ACMY01", 20: "ACMTP10"},
        {0: "24-Oct-2022", 1: 4.0, 20: -0.109},
        {0: "19-Oct-2023", 1: 5.0, 20: 0.449},
        {0: "02-Oct-2026", 1: 4.5, 20: 0.914},
        {0: "garbage", 20: 1.0},
    ]
    monkeypatch.setattr(le, "read_sheet", lambda data, sheet: rows)
    out = le.parse_acm(b"stand-in", "2023-01-01")
    assert out == [("2023-10-19", 0.449), ("2026-10-02", 0.914)]


def test_write_unavailable_writes_pending_doc(tmp_path, monkeypatch):
    monkeypatch.setattr(le, "LONG_END", tmp_path / "long_end_axis.json")
    le.write_unavailable("FRED_API_KEY not set")
    doc = json.loads((tmp_path / "long_end_axis.json").read_text(encoding="utf-8"))
    assert doc["available"] is False
    assert doc["reason"] == "FRED_API_KEY not set"
    assert doc["indicators"] == []
    assert doc["summary"]["checked"] == 0
    assert "2023-10-19" in doc["analogs"]


# ---------------------------------------------------------------- BIFF reader
