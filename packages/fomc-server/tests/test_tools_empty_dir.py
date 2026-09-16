"""Error-dict path: every tool still returns a dict (never raises) when the server
is pointed at an empty repo root via FOMC_INTEL_REPO_ROOT."""

import pytest

from fomc_server._paths import ENV_REPO_ROOT
from fomc_server.tools.corpus import diff_statements, search_fed_corpus
from fomc_server.tools.events import get_event_history
from fomc_server.tools.guide import get_fomc_guide
from fomc_server.tools.news import get_checklist, get_daily_log, get_news_evidence
from fomc_server.tools.pipeline import ingest_meeting, refresh_intel
from fomc_server.tools.playbook import get_fomc_calendar, get_playbook
from fomc_server.tools.regime import (
    get_balance_sheet_axis,
    get_market_pricing_axis,
    get_regime_read,
    get_two_axis_state,
)
from fomc_server.tools.stated import get_stated_regime

DATA_TOOLS = (
    get_regime_read,
    get_two_axis_state,
    get_balance_sheet_axis,
    lambda: get_playbook(),
    lambda: get_event_history(),
    lambda: get_news_evidence(),
    lambda: get_daily_log(),
    get_checklist,
    # phase B — corpus dirs missing under an empty root
    lambda: search_fed_corpus("target range"),
    lambda: diff_statements(),
)


@pytest.fixture
def empty_root(tmp_path, monkeypatch):
    monkeypatch.setenv(ENV_REPO_ROOT, str(tmp_path))
    return tmp_path


def test_data_tools_return_error_dicts(empty_root):
    for fn in DATA_TOOLS:
        out = fn()
        assert isinstance(out, dict)
        assert "error" in out and isinstance(out["error"], str)


def test_market_pricing_axis_reports_pending_not_error(empty_root):
    # Missing axis JSON is an expected state (collector never run), not a failure.
    out = get_market_pricing_axis()
    assert isinstance(out, dict)
    assert "error" not in out
    assert out["available"] is False and "note" in out


def test_static_and_lab_tools_still_return_dicts(empty_root):
    # guide is static; calendar degrades to has_truth_data=None + warning;
    # stated regime reads the lab corpus (independent of the data root).
    guide = get_fomc_guide()
    assert isinstance(guide, dict) and "error" not in guide
    cal = get_fomc_calendar()
    assert isinstance(cal, dict) and "error" not in cal
    assert cal["warnings"]
    assert all(m["has_truth_data"] is None for m in cal["meetings"])
    stated = get_stated_regime("2026-07-01")
    assert isinstance(stated, dict)


def test_bad_date_returns_error_dict():
    assert "error" in get_stated_regime("not-a-date")


def test_pipeline_tools_error_before_any_subprocess(empty_root):
    # refresh_intel: lab dir missing under the empty root -> error dict, no subprocess.
    out = refresh_intel()
    assert isinstance(out, dict) and "error" in out
    assert "steps" not in out  # nothing was executed
    # ingest_meeting: lab venv missing -> error dict, no subprocess.
    out = ingest_meeting()
    assert isinstance(out, dict) and "error" in out
    assert ".venv" in out["error"]
