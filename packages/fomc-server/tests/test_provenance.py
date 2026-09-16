"""Provenance stamp: staleness threshold, mtime fallback, relative source path."""

from datetime import datetime, timedelta, timezone

from fomc_server import _paths
from fomc_server._provenance import STALE_AFTER_HOURS, stamp


def test_fresh_generated_at_not_stale(tmp_path):
    f = tmp_path / "x.json"
    f.write_text("{}")
    now = datetime.now(timezone.utc)
    s = stamp(f, now.isoformat())
    assert s["is_stale"] is False
    assert s["data_as_of"] is not None
    assert s["retrieved_at"] is not None


def test_old_generated_at_is_stale(tmp_path):
    f = tmp_path / "x.json"
    f.write_text("{}")
    old = datetime.now(timezone.utc) - timedelta(hours=STALE_AFTER_HOURS + 1)
    assert stamp(f, old.isoformat())["is_stale"] is True


def test_boundary_just_under_36h_not_stale(tmp_path):
    f = tmp_path / "x.json"
    f.write_text("{}")
    almost = datetime.now(timezone.utc) - timedelta(hours=STALE_AFTER_HOURS - 1)
    assert stamp(f, almost.isoformat())["is_stale"] is False


def test_mtime_fallback_when_no_generated_at(tmp_path):
    f = tmp_path / "x.json"
    f.write_text("{}")  # freshly written -> mtime now -> not stale
    s = stamp(f)
    assert s["is_stale"] is False
    assert s["data_as_of"] is not None


def test_missing_file_is_stale_with_null_as_of(tmp_path):
    s = stamp(tmp_path / "nope.json")
    assert s["is_stale"] is True
    assert s["data_as_of"] is None


def test_source_is_repo_relative_for_real_data():
    s = stamp(_paths.latest_json())
    assert not s["source"].startswith("/")
    assert s["source"].endswith("regime_intel/latest.json")
