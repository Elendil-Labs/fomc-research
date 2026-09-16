"""Tests for the dashboard event-truth export (CSV -> typed JSON)."""

from __future__ import annotations

import json

import pytest
from fomc import export_truth

SAMPLE_CSV = (
    "date,chair,regime,action,ff_target,emergency,spy_close,spy_d0,tlt_d0,spy_p10\n"
    "2018-01-31,Yellen,Unknown,Hold,1.25-1.50,False,281.9,0.05,0.59,\n"
    "2020-03-15,Powell,Easing,Cut,0.00-0.25,True,250.0,-1.5,2.3,4.1\n"
)


@pytest.fixture
def source_csv(tmp_path):
    p = tmp_path / "fomc_event_truth.csv"
    p.write_text(SAMPLE_CSV, encoding="utf-8")
    return p


def test_load_events_coerces_types(source_csv):
    columns, events = export_truth.load_events(source_csv)
    assert "date" in columns and "spy_d0" in columns
    assert len(events) == 2
    # strings stay strings
    assert events[0]["chair"] == "Yellen"
    assert events[0]["ff_target"] == "1.25-1.50"
    # numerics become floats
    assert events[0]["spy_close"] == 281.9
    assert events[1]["spy_d0"] == -1.5
    # booleans
    assert events[0]["emergency"] is False
    assert events[1]["emergency"] is True
    # empty numeric cell -> None (missing forward window)
    assert events[0]["spy_p10"] is None
    assert events[1]["spy_p10"] == 4.1


def test_build_document_metadata(source_csv):
    columns, events = export_truth.load_events(source_csv)
    doc = export_truth.build_document(columns, events)
    assert doc["count"] == 2
    assert doc["first_event_date"] == "2018-01-31"
    assert doc["latest_event_date"] == "2020-03-15"
    assert doc["columns"] == columns


def test_run_writes_csv_and_json(tmp_path, source_csv):
    csv_out = tmp_path / "out" / "truth.csv"
    json_out = tmp_path / "out" / "truth.json"
    doc = export_truth.run(csv_out, json_out, source_csv=source_csv)

    assert csv_out.read_text() == SAMPLE_CSV  # verbatim copy
    loaded = json.loads(json_out.read_text())
    assert loaded["count"] == 2
    assert loaded == doc


def test_missing_source_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        export_truth.load_events(tmp_path / "nope.csv")
