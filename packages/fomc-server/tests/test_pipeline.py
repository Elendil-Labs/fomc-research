"""Pipeline tools with subprocess FULLY MOCKED — no live network, no real git, and
never any git executed against this worktree."""

import json
import subprocess as _subprocess
import sys
from pathlib import Path

import pytest

from fomc_server._paths import ENV_REPO_ROOT
from fomc_server.tools import pipeline

BEFORE_DOC = {
    "generated_at": "2026-07-01T12:00:00+00:00",
    "inferred_regime": "Easing",
    "conviction": "low",
    "net_lean": 0.10,
    "n_sources": 100,
    "new_this_run": 2,
}
AFTER_DOC = {
    "generated_at": "2026-07-02T12:00:00+00:00",
    "inferred_regime": "Potential pivot → tightening",
    "conviction": "medium",
    "net_lean": 0.35,
    "n_sources": 104,
    "new_this_run": 4,
}


def _write_latest(root: Path, doc: dict) -> Path:
    p = root / "fomc-spy-tlt-lab" / "apps" / "fomc-dashboard" / "public" / "data"
    p = p / "regime_intel"
    p.mkdir(parents=True, exist_ok=True)
    (p / "latest.json").write_text(json.dumps(doc), encoding="utf-8")
    return p / "latest.json"


@pytest.fixture
def fake_root(tmp_path, monkeypatch):
    """Sandbox repo root with a lab dir + a 'before' latest.json; PPLX/FRED keys set."""
    (tmp_path / "fomc-spy-tlt-lab").mkdir()
    _write_latest(tmp_path, BEFORE_DOC)
    monkeypatch.setenv(ENV_REPO_ROOT, str(tmp_path))
    monkeypatch.setenv("PPLX_API_KEY_fomc", "test-key-not-real")
    monkeypatch.setenv("FRED_API_KEY", "test-key-not-real")
    return tmp_path


def install_fake_run(monkeypatch, handler):
    """Replace subprocess.run inside the pipeline module; returns the call log."""
    calls: list[dict] = []

    def fake_run(argv, cwd=None, capture_output=True, text=True, timeout=None):
        calls.append({"argv": list(argv), "cwd": cwd, "timeout": timeout})
        rc, out, err = handler(list(argv))
        return _subprocess.CompletedProcess(argv, rc, stdout=out, stderr=err)

    monkeypatch.setattr(pipeline.subprocess, "run", fake_run)
    return calls


# ---------------------------------------------------------------- refresh_intel


def test_refresh_intel_success_delta(fake_root, monkeypatch):
    def handler(argv):
        if any("score_regime_intel.py" in a for a in argv):
            _write_latest(fake_root, AFTER_DOC)
        return 0, "line1\nline2\nline3\nline4\n", ""

    calls = install_fake_run(monkeypatch, handler)
    out = pipeline.refresh_intel()
    assert "error" not in out, out.get("error")
    assert [s["name"] for s in out["steps"]] == [
        "collect_regime_intel",
        "score_regime_intel",
        "collect_balance_sheet",
        "collect_market_pricing",
    ]
    assert all(s["ok"] for s in out["steps"])
    assert all(s["tail"] == ["line2", "line3", "line4"] for s in out["steps"])
    # every step ran in the lab dir, no venv there -> current interpreter
    assert all(c["cwd"] == str(fake_root / "fomc-spy-tlt-lab") for c in calls)
    assert out["python"] == sys.executable and out["python_source"] == "sys_executable"
    # score step got the --next-fomc anchor when the calendar still has one
    score_argv = calls[1]["argv"]
    from fomc_server import _calendar

    nxt = _calendar.next_fomc(_calendar.today_utc())
    if nxt:
        assert score_argv[-2:] == ["--next-fomc", nxt]
    # delta computed from the before/after fixtures
    assert out["before"]["net_lean"] == 0.10 and out["after"]["net_lean"] == 0.35
    assert out["delta"] == {
        "net_lean_change": 0.25,
        "descriptor_changed": True,
        "new_sources": 4,
    }
    assert "publish" not in out  # publish=False default


def test_refresh_intel_missing_pplx_key_runs_nothing(fake_root, monkeypatch):
    monkeypatch.delenv("PPLX_API_KEY_fomc", raising=False)
    monkeypatch.delenv("PPLX_API_KEY", raising=False)
    calls = install_fake_run(monkeypatch, lambda argv: (0, "", ""))
    out = pipeline.refresh_intel()
    assert "error" in out and "PPLX_API_KEY_fomc" in out["error"]
    assert calls == []  # nothing executed


def test_refresh_intel_key_found_by_name_in_env_file(fake_root, monkeypatch):
    # key only DECLARED in .env (value never parsed into the result)
    monkeypatch.delenv("PPLX_API_KEY_fomc", raising=False)
    monkeypatch.delenv("PPLX_API_KEY", raising=False)
    (fake_root / ".env").write_text("PPLX_API_KEY_fomc=sekrit\n", encoding="utf-8")
    install_fake_run(monkeypatch, lambda argv: (0, "", ""))
    out = pipeline.refresh_intel()
    assert "error" not in out
    assert "sekrit" not in json.dumps(out)


def test_refresh_intel_balance_sheet_failure_non_fatal(fake_root, monkeypatch):
    def handler(argv):
        if any("collect_balance_sheet.py" in a for a in argv):
            return 1, "", "FRED exploded\n"
        return 0, "ok\n", ""

    install_fake_run(monkeypatch, handler)
    out = pipeline.refresh_intel()
    assert "error" not in out  # step c is non-fatal
    steps = {s["name"]: s for s in out["steps"]}
    assert steps["collect_balance_sheet"]["ok"] is False
    assert steps["collect_balance_sheet"]["tail"] == ["FRED exploded"]
    assert steps["collect_regime_intel"]["ok"] and steps["score_regime_intel"]["ok"]
    assert steps["collect_market_pricing"]["ok"]  # still ran after step c failed


def test_refresh_intel_market_pricing_failure_non_fatal(fake_root, monkeypatch):
    def handler(argv):
        if any("collect_market_pricing.py" in a for a in argv):
            return 1, "", "FRED exploded\n"
        return 0, "ok\n", ""

    install_fake_run(monkeypatch, handler)
    out = pipeline.refresh_intel()
    assert "error" not in out  # step d is non-fatal
    steps = {s["name"]: s for s in out["steps"]}
    assert steps["collect_market_pricing"]["ok"] is False
    assert steps["collect_market_pricing"]["tail"] == ["FRED exploded"]
    assert steps["collect_regime_intel"]["ok"] and steps["score_regime_intel"]["ok"]


def test_refresh_intel_collect_failure_is_fatal(fake_root, monkeypatch):
    calls = install_fake_run(monkeypatch, lambda argv: (1, "", "boom\n"))
    out = pipeline.refresh_intel(publish=True)
    assert out["error"] == "collect_regime_intel failed"
    assert [s["name"] for s in out["steps"]] == ["collect_regime_intel"]
    assert len(calls) == 1  # score/balance-sheet/publish never ran
    assert "publish" not in out


def test_refresh_intel_publish_true_invokes_publish(fake_root, monkeypatch):
    install_fake_run(monkeypatch, lambda argv: (0, "", ""))
    sentinel = {"committed": False, "pushed": False, "sha": None, "attempts": 0, "note": "x"}
    seen = {}

    def fake_publish(repo_root):
        seen["repo_root"] = repo_root
        return sentinel

    monkeypatch.setattr(pipeline, "_publish", fake_publish)
    out = pipeline.refresh_intel(publish=True)
    assert out["publish"] is sentinel
    assert seen["repo_root"] == fake_root


# ---------------------------------------------------------------- ingest_meeting


@pytest.fixture
def fake_root_with_venv(fake_root):
    venv_py = fake_root / "fomc-spy-tlt-lab" / ".venv" / "bin" / "python"
    venv_py.parent.mkdir(parents=True)
    venv_py.write_text("#!/bin/sh\n", encoding="utf-8")
    return fake_root


@pytest.fixture
def fixed_stated(monkeypatch):
    monkeypatch.setattr(
        pipeline,
        "_stated_regime_snapshot",
        lambda: {"regime": "Easing", "action": "Hold", "date": "2026-06-17"},
    )


def test_ingest_requires_lab_venv(fake_root, monkeypatch):
    calls = install_fake_run(monkeypatch, lambda argv: (0, "", ""))
    out = pipeline.ingest_meeting()
    assert "error" in out and ".venv" in out["error"]
    assert calls == []


def test_ingest_success_full_sequence(fake_root_with_venv, fixed_stated, monkeypatch):
    calls = install_fake_run(monkeypatch, lambda argv: (0, "done\n", ""))
    out = pipeline.ingest_meeting()
    assert "error" not in out, out.get("error")
    names = [s["name"] for s in out["steps"]]
    assert names == [
        "fetch_statements",
        "truth",
        "export_truth",
        "collect_regime_intel",  # refresh_news=True default, PPLX key set
        "score_regime_intel",
    ]
    assert out["parser_alarm"] is None
    assert out["news_refresh"] == {"skipped": False, "ok": True}
    assert out["python_source"] == "lab_venv"
    venv_py = str(fake_root_with_venv / "fomc-spy-tlt-lab" / ".venv" / "bin" / "python")
    assert out["python"] == venv_py
    # fetch/truth/export run as `-m fomc.*` under the LAB VENV interpreter
    assert calls[0]["argv"][:4] == [venv_py, "-m", "fomc.fetch", "--types"]
    assert "--since" in calls[0]["argv"]
    assert calls[1]["argv"] == [venv_py, "-m", "fomc.truth"]
    assert calls[1]["timeout"] == 600
    assert calls[2]["argv"] == [venv_py, "-m", "fomc.export_truth"]
    assert calls[2]["timeout"] == 120
    assert out["stated_regime_before"]["regime"] == "Easing"
    assert out["stated_regime_after"]["regime"] == "Easing"


def test_ingest_parser_alarm_not_fatal(fake_root_with_venv, fixed_stated, monkeypatch):
    alarm_text = "ALARM: newest statement 2026-07-29 did not parse — regime frozen"

    def handler(argv):
        if argv[-1] == "fomc.truth":
            return 2, "wrote outputs anyway\n", alarm_text + "\n"
        return 0, "ok\n", ""

    install_fake_run(monkeypatch, handler)
    out = pipeline.ingest_meeting(refresh_news=False)
    assert "error" not in out  # exit code 2 is NOT fatal
    alarm = out["parser_alarm"]
    assert alarm["triggered"] is True
    assert alarm["alarm_text"] == alarm_text
    assert "FROZEN" in alarm["meaning"]
    truth_step = next(s for s in out["steps"] if s["name"] == "truth")
    assert truth_step["ok"] is True and truth_step["alarm"] is True
    assert truth_step["returncode"] == 2
    # subsequent steps still ran
    assert [s["name"] for s in out["steps"]] == ["fetch_statements", "truth", "export_truth"]


def test_ingest_skips_news_without_key(fake_root_with_venv, fixed_stated, monkeypatch):
    monkeypatch.delenv("PPLX_API_KEY_fomc", raising=False)
    monkeypatch.delenv("PPLX_API_KEY", raising=False)
    install_fake_run(monkeypatch, lambda argv: (0, "", ""))
    out = pipeline.ingest_meeting()
    assert "error" not in out
    assert out["news_refresh"]["skipped"] is True
    assert [s["name"] for s in out["steps"]] == ["fetch_statements", "truth", "export_truth"]


def test_ingest_fetch_failure_is_fatal(fake_root_with_venv, fixed_stated, monkeypatch):
    calls = install_fake_run(monkeypatch, lambda argv: (127, "", "no such module\n"))
    out = pipeline.ingest_meeting(publish=True)
    assert out["error"] == "fomc.fetch failed"
    assert len(calls) == 1
    assert "publish" not in out


# ---------------------------------------------------------------- _publish (mocked git)

# _publish() is handed a bare tmp_path (no fomc-spy-tlt-lab/ subdir), i.e. the flat
# fomc-research layout, so the staged path has no lab prefix.
DATA_PATH = "apps/fomc-dashboard/public/data"
AUTHOR = "jingerzz <21320706+jingerzz@users.noreply.github.com>"


def test_publish_nothing_staged(tmp_path, monkeypatch):
    def handler(argv):
        # add ok; `diff --cached --quiet` rc 0 == no staged changes
        return 0, "", ""

    calls = install_fake_run(monkeypatch, handler)
    out = pipeline._publish(tmp_path)
    assert out == {
        "committed": False,
        "pushed": False,
        "sha": None,
        "attempts": 0,
        "note": "no data changes",
    }
    assert [c["argv"] for c in calls] == [
        ["git", "add", "--", DATA_PATH],
        ["git", "diff", "--cached", "--quiet", "--", DATA_PATH],
    ]
    assert all(c["cwd"] == str(tmp_path) for c in calls)


def test_publish_success_exact_argv(tmp_path, monkeypatch):
    def handler(argv):
        if argv[1:4] == ["diff", "--cached", "--quiet"]:
            return 1, "", ""  # staged changes present
        if argv[1] == "rev-parse":
            return 0, "abc123\n", ""
        return 0, "", ""

    calls = install_fake_run(monkeypatch, handler)
    out = pipeline._publish(tmp_path)
    assert out["committed"] is True and out["pushed"] is True
    assert out["sha"] == "abc123" and out["attempts"] == 1

    argvs = [c["argv"] for c in calls]
    assert argvs[0] == ["git", "add", "--", DATA_PATH]
    commit = argvs[2]
    email = AUTHOR.split("<")[1][:-1]
    assert commit[:5] == ["git", "-c", "user.name=jingerzz", "-c", f"user.email={email}"]
    assert commit[5:8] == ["commit", "--author", AUTHOR]
    assert commit[8] == "-m"
    msg = commit[9]
    assert msg.startswith("Refresh FOMC dashboard data (")
    assert msg.endswith(") [fomc-intel MCP]")
    assert argvs[3] == ["git", "fetch", "origin"]
    assert argvs[4] == ["git", "rebase", "origin/main"]
    assert argvs[5] == ["git", "push", "origin", "HEAD:main"]
    assert argvs[6] == ["git", "rev-parse", "HEAD"]
    assert len(argvs) == 7


def test_publish_rebase_retry_second_push_succeeds(tmp_path, monkeypatch):
    push_attempts = {"n": 0}

    def handler(argv):
        if argv[1:4] == ["diff", "--cached", "--quiet"]:
            return 1, "", ""
        if argv[1] == "push":
            push_attempts["n"] += 1
            if push_attempts["n"] == 1:
                return 1, "", "rejected: non-fast-forward\n"
            return 0, "", ""
        if argv[1] == "rev-parse":
            return 0, "def456\n", ""
        return 0, "", ""

    calls = install_fake_run(monkeypatch, handler)
    out = pipeline._publish(tmp_path)
    assert out["committed"] is True
    assert out["pushed"] is True
    assert out["attempts"] == 2
    assert out["sha"] == "def456"
    tail = [c["argv"][1] for c in calls][3:]  # after add/diff/commit
    assert tail == ["fetch", "rebase", "push", "fetch", "rebase", "push", "rev-parse"]


def test_publish_all_pushes_fail(tmp_path, monkeypatch):
    def handler(argv):
        if argv[1:4] == ["diff", "--cached", "--quiet"]:
            return 1, "", ""
        if argv[1] == "push":
            return 1, "", "rejected\n"
        if argv[1] == "rev-parse":
            return 0, "ffff\n", ""
        return 0, "", ""

    install_fake_run(monkeypatch, handler)
    out = pipeline._publish(tmp_path)
    assert out["committed"] is True and out["pushed"] is False
    assert out["attempts"] == 3
    assert "push rejected" in out["note"]


# ---------------------------------------------------------------- event-loop offload (F1)


def test_to_thread_preserves_name_doc_and_signature():
    import inspect

    wrapped = pipeline.to_thread(pipeline.refresh_intel)
    assert wrapped.__name__ == "refresh_intel"
    assert wrapped.__doc__ == pipeline.refresh_intel.__doc__
    # FastMCP builds the tool schema from the signature; it must survive wrapping.
    assert list(inspect.signature(wrapped).parameters) == ["publish"]
    assert inspect.iscoroutinefunction(wrapped)


def test_to_thread_keeps_event_loop_responsive_during_blocking_call():
    """Regression for the 2026-07-11 Desktop hang: a blocking pipeline tool must not
    freeze the event loop (the SDK calls sync tools inline; the wrapper offloads)."""
    import time as _time

    import anyio

    def blocking_tool(publish: bool = False) -> dict:
        _time.sleep(0.4)  # stands in for a 121s refresh_intel
        return {"ok": True, "publish": publish}

    async def main() -> tuple[dict, int]:
        beats = 0
        done = anyio.Event()

        async def heartbeat() -> None:
            nonlocal beats
            while not done.is_set():
                await anyio.sleep(0.02)
                if not done.is_set():
                    beats += 1  # only counts while the tool is still running

        result: dict = {}
        async with anyio.create_task_group() as tg:
            tg.start_soon(heartbeat)
            result = await pipeline.to_thread(blocking_tool)(publish=True)
            done.set()
        return result, beats

    result, beats = anyio.run(main)
    assert result == {"ok": True, "publish": True}
    # A loop blocked by the tool would record ~0 beats until it finished.
    assert beats >= 5
