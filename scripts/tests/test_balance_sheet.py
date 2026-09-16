"""Tests for the balance-sheet axis computation (pure logic; no network)."""

from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import collect_balance_sheet as bs  # noqa: E402


def test_change_90d_uses_obs_nearest_90_days_back():
    series = [
        ("2026-03-01", 100.0),  # ~90d before latest
        ("2026-04-01", 110.0),
        ("2026-06-01", 130.0),  # latest
    ]
    val, as_of, chg = bs.change_90d(series)
    assert val == 130.0
    assert as_of == "2026-06-01"
    # latest minus the obs at/just-before (latest - 90d) = 2026-03-03 -> uses 2026-03-01 (100)
    assert chg == 30.0


def test_signal_change_direction_and_dead_zone():
    # up_tightening=False (e.g. Fed assets): shrinking -> tightening (+1)
    assert bs.signal_change(-30000, up_tightening=False, dead=20000) == 1
    assert bs.signal_change(30000, up_tightening=False, dead=20000) == -1
    assert bs.signal_change(5000, up_tightening=False, dead=20000) == 0  # within dead zone
    # up_tightening=True (e.g. 10y yield): rising -> tightening (+1)
    assert bs.signal_change(0.30, up_tightening=True, dead=0.15) == 1
    assert bs.signal_change(-0.30, up_tightening=True, dead=0.15) == -1


def test_label_thresholds():
    assert bs.label(-0.5) == "loosening"
    assert bs.label(0.0) == "neutral"
    assert bs.label(0.5) == "tightening"


def test_weights_sum_to_one():
    assert round(sum(ind["weight"] for ind in bs.INDICATORS), 6) == 1.0
