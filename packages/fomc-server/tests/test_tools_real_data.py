"""Every tool against the REAL repo data files (they exist in this worktree)."""

import json

from fomc_server import _paths
from fomc_server.tools.events import get_event_history
from fomc_server.tools.guide import get_fomc_guide
from fomc_server.tools.news import get_checklist, get_daily_log, get_news_evidence
from fomc_server.tools.playbook import get_fomc_calendar, get_playbook
from fomc_server.tools.regime import (
    get_balance_sheet_axis,
    get_market_pricing_axis,
    get_regime_read,
    get_two_axis_state,
)
from fomc_server.tools.stated import get_stated_regime

ALL_TOOLS = (
    get_fomc_guide,
    get_regime_read,
    get_two_axis_state,
    get_balance_sheet_axis,
    get_market_pricing_axis,
    lambda: get_playbook(),
    lambda: get_event_history(),
    lambda: get_news_evidence(),
    lambda: get_daily_log(),
    get_checklist,
    lambda: get_stated_regime(),
    get_fomc_calendar,
)


def test_every_tool_returns_dict_without_error_on_real_data():
    for fn in ALL_TOOLS:
        out = fn()
        assert isinstance(out, dict)
        assert "error" not in out, out.get("error")


def test_regime_read_matches_latest_json():
    latest = json.loads(_paths.latest_json().read_text())
    out = get_regime_read()
    assert isinstance(out["descriptor"], str)
    assert out["descriptor"] == latest["inferred_regime"]
    assert out["stated_regime"] == latest["current_repo_regime"]
    assert out["net_lean"] == latest["net_lean"]
    # stated as-of = last event in the truth table
    truth = json.loads(_paths.truth_json().read_text())
    assert out["stated_regime_as_of"] == truth["events"][-1]["date"]
    prov = out["provenance"]
    assert set(prov) >= {"data_as_of", "retrieved_at", "source", "is_stale"}


def test_two_axis_state_shape():
    out = get_two_axis_state()
    assert out["quadrant"] in {
        "rate-led tightening",
        "full tightening",
        "full easing",
        "bifurcated",
    }
    assert isinstance(out["divergence"], bool)
    assert isinstance(out["why"], str) and out["why"]
    assert "news_axis" in out["provenance"] and "balance_sheet_axis" in out["provenance"]


def test_balance_sheet_axis_indicators():
    out = get_balance_sheet_axis()
    assert out["available"] is True
    assert isinstance(out["indicators"], list) and out["indicators"]
    assert all(i["signal"] in (-1, 0, 1) for i in out["indicators"])


def test_market_pricing_axis_shape():
    # The axis JSON may or may not be committed yet: either a clean pending state
    # (available False + note, never an error) or the full indicator payload.
    out = get_market_pricing_axis()
    assert "error" not in out
    if out["available"]:
        assert isinstance(out["indicators"], list) and out["indicators"]
        assert all(i["signal"] in (-1, 0, 1) for i in out["indicators"])
        assert out["label"] in ("loosening", "neutral", "tightening")
    else:
        assert "note" in out


def test_market_pricing_axis_happy_path_from_tmp_file(tmp_path, monkeypatch):
    intel = tmp_path / "fomc-spy-tlt-lab" / "apps" / "fomc-dashboard" / "public" / "data"
    intel = intel / "regime_intel"
    intel.mkdir(parents=True)
    doc = {
        "generated_at": "2026-07-10T12:00:00+00:00",
        "available": True,
        "net_lean": -0.3,
        "label": "loosening",
        "indicators": [
            {"id": "DGS2", "name": "2y Treasury yield (policy-path momentum)",
             "unit": "%", "weight": 0.30, "latest": 3.55, "signal": -1,
             "detail": "Δ90d -0.25 %", "note": "market repricing easier policy"},
        ],
        "method": "m",
        "source": "FRED API (api.stlouisfed.org)",
    }
    (intel / "market_pricing_axis.json").write_text(json.dumps(doc), encoding="utf-8")
    monkeypatch.setenv(_paths.ENV_REPO_ROOT, str(tmp_path))
    out = get_market_pricing_axis()
    assert out["available"] is True
    assert out["net_lean"] == -0.3 and out["label"] == "loosening"
    assert out["indicators"][0]["id"] == "DGS2"
    assert set(out["provenance"]) >= {"data_as_of", "retrieved_at", "source", "is_stale"}


def test_playbook_easing_has_events_and_blackout():
    out = get_playbook()
    assert out["conditioning"]["stated_regime"] == "Easing"
    assert out["conditioning"]["n_events"] > 0
    assert out["stats"]["spy"]["d0"]["n"] > 0
    assert out["stats"]["tlt"]["d0"]["n"] > 0
    nf = out["next_fomc"]
    if nf and nf["date"] == "2026-07-29":
        assert nf["blackout_start"] == "2026-07-18"
        assert nf["blackout_end"] == "2026-07-30"
    # per-action counts cover the whole conditioned set
    assert sum(out["conditioning"]["action_counts"].values()) >= out["conditioning"]["n_events"]


def test_playbook_action_filter_and_validation():
    all_n = get_playbook()["conditioning"]["n_events"]
    per_action = [get_playbook(a)["conditioning"]["n_events"] for a in ("Hike", "Hold", "Cut")]
    assert sum(per_action) == all_n
    assert "error" in get_playbook("Ease")


def test_event_history_filters():
    everything = get_event_history()
    assert everything["n"] > 0
    easing = get_event_history(regime="Easing")
    assert 0 < easing["n"] <= everything["n"]
    assert all(e["regime"] == "Easing" for e in easing["events"])
    cuts = get_event_history(action="Cut")
    assert all(e["action"] == "Cut" for e in cuts["events"])
    warsh = get_event_history(chair="Warsh")
    assert all(e["chair"] == "Warsh" for e in warsh["events"])
    green = get_event_history(color="green")
    assert all(
        e["spy_d0"] >= 0 and e["tlt_d0"] >= 0 and e["color"] == "green" for e in green["events"]
    )
    ranged = get_event_history(since="2020-01-01", until="2020-12-31")
    assert all(e["date"].startswith("2020") for e in ranged["events"])
    assert "error" in get_event_history(color="purple")
    limited = get_event_history(limit=3)
    assert limited["n"] == 3 and limited["truncated"] is True
    # limit keeps the MOST RECENT events
    assert limited["events"][-1]["date"] == everything["events"][-1]["date"]


def test_news_evidence_filters_and_order():
    out = get_news_evidence(limit=10)
    assert 0 < len(out["sources"]) <= 10
    dates = [s["published_at"] or "" for s in out["sources"]]
    assert dates == sorted(dates, reverse=True)  # newest first
    for s in out["sources"]:
        assert set(s) >= {"url", "tier", "claim_type", "event_key"}
        assert s["tier"] in ("fed", "official", "news")
    infl = get_news_evidence(bucket="inflation")
    assert all(s["bucket"] == "inflation" for s in infl["sources"])
    tight = get_news_evidence(direction="tightening")
    assert all(s["direction"] == "tightening" for s in tight["sources"])
    assert "error" in get_news_evidence(bucket="weather")


def test_daily_log_newest_first():
    out = get_daily_log(limit=5)
    dates = [p["date"] for p in out["points"]]
    assert dates == sorted(dates, reverse=True)
    assert len(dates) <= 5


def test_checklist_carries_honesty_note():
    out = get_checklist()
    assert isinstance(out["checklist"], list) and out["checklist"]
    # spytlt_confirms is now computed from the trailing SPY/TLT price trend at refresh
    # time (with an unknown fallback) — the note must say so, not claim it stays unknown.
    assert "spytlt_confirms" in out["honesty_note"]
    assert "SPY/TLT price trend" in out["honesty_note"]
    assert "stays 'unknown'" not in out["honesty_note"]
