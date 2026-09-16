"""Pipeline tools: live news-intel refresh + meeting-day ingest + git publish helper.

Every external command runs as a subprocess with cwd=<lab> (the scripts self-resolve
API keys from the repo-root .env when run from there — this module only checks key
NAMES up front, never values). Git runs with cwd=<repo_root> inside _publish only.
"""

from __future__ import annotations

import functools
import os
import subprocess
import sys
import time
from collections.abc import Awaitable, Callable
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import anyio

from fomc_server import _calendar, _paths
from fomc_server._data import load_latest
from fomc_server.tools import error_dict

STEP_TIMEOUT = 300  # collect/score/balance-sheet/fetch
TRUTH_TIMEOUT = 600  # fomc.truth fetches prices
EXPORT_TIMEOUT = 120
GIT_TIMEOUT = 120
PUSH_ATTEMPTS = 3
TAIL_LINES = 3

# Dashboard data dir relative to the LAB root; _publish_path() prefixes the lab dir
# when the lab is nested inside the repo (empty prefix in the flat layout).
PUBLISH_REL = Path("apps") / "fomc-dashboard" / "public" / "data"
PUBLISH_NAME = "jingerzz"
PUBLISH_EMAIL = "21320706+jingerzz@users.noreply.github.com"
PUBLISH_AUTHOR = f"{PUBLISH_NAME} <{PUBLISH_EMAIL}>"

PPLX_KEY_NAMES = ("PPLX_API_KEY_fomc", "PPLX_API_KEY")
FRED_KEY_NAME = "FRED_API_KEY"


# ---------------------------------------------------------------- plumbing


def _publish_path(repo_root: Path) -> str:
    """Path to stage, relative to the git root: "apps/fomc-dashboard/public/data" in
    the flat layout, "fomc-spy-tlt-lab/apps/..." when the lab is a subdirectory."""
    lab = _paths.lab_root_for(repo_root)
    return (lab.relative_to(repo_root) / PUBLISH_REL).as_posix()


def _lab_python(lab: Path) -> tuple[str, str]:
    """Interpreter for lab subprocesses: the lab venv when present, else this one."""
    venv_py = lab / ".venv" / "bin" / "python"
    if venv_py.exists():
        return str(venv_py), "lab_venv"
    return sys.executable, "sys_executable"


def _env_file_key_names(path: Path) -> set[str]:
    """Key NAMES declared in a .env file. Values are never read into results."""
    names: set[str] = set()
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return names
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        names.add(line.split("=", 1)[0].strip())
    return names


def _has_any_key(repo: Path, lab: Path, names: tuple[str, ...]) -> bool:
    """True when any named key is set in the process env or declared in a .env
    (lab-local first, then repo root — mirrors the scripts' own load_api_key)."""
    declared = _env_file_key_names(lab / ".env") | _env_file_key_names(repo / ".env")
    return any(os.environ.get(n) or n in declared for n in names)


def _run_step(
    name: str, argv: list[str], cwd: Path, timeout: int
) -> tuple[dict[str, Any], str]:
    """Run one pipeline step; returns (step report, full stderr)."""
    t0 = time.monotonic()
    note: str | None = None
    stderr = ""
    returncode: int | None = None
    combined = ""
    try:
        proc = subprocess.run(
            argv, cwd=str(cwd), capture_output=True, text=True, timeout=timeout
        )
        returncode = proc.returncode
        stderr = proc.stderr or ""
        combined = (proc.stdout or "") + stderr
    except subprocess.TimeoutExpired:
        note = f"timed out after {timeout}s"
    except OSError as exc:
        note = f"{type(exc).__name__}: {exc}"
    step: dict[str, Any] = {
        "name": name,
        "argv": argv,
        "ok": returncode == 0,
        "returncode": returncode,
        "seconds": round(time.monotonic() - t0, 2),
        "tail": [ln for ln in combined.splitlines() if ln.strip()][-TAIL_LINES:],
    }
    if note:
        step["note"] = note
    return step, stderr


def _latest_snapshot() -> dict[str, Any] | None:
    """Compact regime read from latest.json (phase A reader); None when unreadable."""
    try:
        doc, _ = load_latest()
        return {
            "descriptor": doc.get("inferred_regime"),
            "net_lean": doc.get("net_lean"),
            "conviction": doc.get("conviction"),
            "n_sources": doc.get("n_sources"),
            "new_this_run": doc.get("new_this_run"),
            "generated_at": doc.get("generated_at"),
        }
    except Exception:
        return None


def _delta(before: dict | None, after: dict | None) -> dict[str, Any]:
    net_change = None
    if (
        before is not None
        and after is not None
        and isinstance(before.get("net_lean"), (int, float))
        and isinstance(after.get("net_lean"), (int, float))
    ):
        net_change = round(after["net_lean"] - before["net_lean"], 4)
    return {
        "net_lean_change": net_change,
        "descriptor_changed": bool(
            before is not None
            and after is not None
            and before.get("descriptor") != after.get("descriptor")
        ),
        "new_sources": after.get("new_this_run") if after else None,
    }


def _stated_regime_snapshot() -> dict[str, Any] | None:
    """Last row of the lab's statement-parsed regime timeline; None when unavailable."""
    try:
        from fomc import regime as lab_regime

        timeline = lab_regime.build_timeline()
        if not timeline:
            return None
        last = timeline[-1]
        return {
            "regime": last.get("regime"),
            "action": last.get("action"),
            "date": last.get("date"),
        }
    except Exception:
        return None


def _news_steps(py: str, lab: Path) -> list[dict[str, Any]]:
    """The collect+score pair shared by refresh_intel and ingest_meeting."""
    steps: list[dict[str, Any]] = []
    step, _ = _run_step(
        "collect_regime_intel",
        [py, "scripts/collect_regime_intel.py", "--model", "sonar"],
        lab,
        STEP_TIMEOUT,
    )
    steps.append(step)
    if not step["ok"]:
        return steps
    argv = [py, "scripts/score_regime_intel.py"]
    next_meeting = _calendar.next_fomc(_calendar.today_utc())
    if next_meeting:
        argv += ["--next-fomc", next_meeting]
    step, _ = _run_step("score_regime_intel", argv, lab, STEP_TIMEOUT)
    steps.append(step)
    return steps


# ---------------------------------------------------------------- tools


def refresh_intel(publish: bool = False) -> dict[str, Any]:
    """Run the live regime-intel pipeline now: collect fresh news via Perplexity,
    re-score the weighted evidence (anchored to the next FOMC decision date), and
    refresh the deterministic FRED balance-sheet axis — then report the before/after
    regime read and the delta (net-lean change, descriptor flip, new sources).
    Requires PPLX_API_KEY_fomc in the repo-root .env; balance-sheet step needs
    FRED_API_KEY (its failure is non-fatal). publish=True commits and pushes the
    refreshed dashboard data to origin/main.
    Historical/observational evidence only — not investment advice."""
    try:
        repo = _paths.repo_root()
        lab = _paths.lab_root()
        if not lab.is_dir():
            raise FileNotFoundError(f"lab directory not found: {lab}")
        if not _has_any_key(repo, lab, PPLX_KEY_NAMES):
            return {
                "error": (
                    "No Perplexity key found: none of "
                    f"{'/'.join(PPLX_KEY_NAMES)} is set in the environment or declared "
                    f"in {repo / '.env'} (or {lab / '.env'}). The collect step would "
                    "run empty, so nothing was executed. Add the key and retry."
                )
            }
        py, py_source = _lab_python(lab)
        warnings: list[str] = []
        if not _has_any_key(repo, lab, (FRED_KEY_NAME,)):
            warnings.append(
                "FRED_API_KEY not found — the balance-sheet step will likely produce "
                "nothing (non-fatal)."
            )

        before = _latest_snapshot()
        steps = _news_steps(py, lab)
        fatal = None if all(s["ok"] for s in steps) else f"{steps[-1]['name']} failed"
        if fatal is None:
            # Step c is non-fatal by design: report ok:false and continue.
            step_c, _ = _run_step(
                "collect_balance_sheet",
                [py, "scripts/collect_balance_sheet.py"],
                lab,
                STEP_TIMEOUT,
            )
            steps.append(step_c)
            # Step d is likewise non-fatal: the market-pricing axis degrades to
            # "axis pending" on its own; a failure never blocks the news refresh.
            step_d, _ = _run_step(
                "collect_market_pricing",
                [py, "scripts/collect_market_pricing.py"],
                lab,
                STEP_TIMEOUT,
            )
            steps.append(step_d)
        after = _latest_snapshot()

        result: dict[str, Any] = {
            "python": py,
            "python_source": py_source,
            "steps": steps,
            "before": before,
            "after": after,
            "delta": _delta(before, after),
        }
        if warnings:
            result["warnings"] = warnings
        if fatal:
            result["error"] = fatal
            return result
        if publish:
            result["publish"] = _publish(repo)
        return result
    except Exception as exc:
        return error_dict(exc)


def ingest_meeting(publish: bool = False, refresh_news: bool = True) -> dict[str, Any]:
    """Meeting-day ingest: fetch the newest FOMC statement from federalreserve.gov,
    rebuild the SPY/TLT event-truth table (prices included), re-export the dashboard
    JSON, and (by default) re-run the news pipeline so the evidence window re-anchors
    to the new meeting. Reports the statement-parsed stated regime before and after,
    and surfaces the hardened parser's STALE ALARM (exit code 2) prominently instead
    of failing — outputs are still written in that case. publish=True commits and
    pushes the refreshed dashboard data to origin/main. Requires the lab's own venv
    (the repo-root .venv created by `uv sync`).
    Historical/observational evidence only — not investment advice."""
    try:
        repo = _paths.repo_root()
        lab = _paths.lab_root()
        venv_py = lab / ".venv" / "bin" / "python"
        if not venv_py.exists():
            return {
                "error": (
                    f"lab venv interpreter not found at {venv_py} — the fomc CLI "
                    "(fetch/truth/export_truth) needs the lab's own environment. "
                    "Create it with `uv sync` at the repo root, then retry."
                )
            }
        py = str(venv_py)

        stated_before = _stated_regime_snapshot()
        steps: list[dict[str, Any]] = []
        parser_alarm: dict[str, Any] | None = None
        fatal: str | None = None

        since = (date.today() - timedelta(days=90)).isoformat()
        step, _ = _run_step(
            "fetch_statements",
            [py, "-m", "fomc.fetch", "--types", "statement", "--since", since],
            lab,
            STEP_TIMEOUT,
        )
        steps.append(step)
        if not step["ok"]:
            fatal = "fomc.fetch failed"

        if fatal is None:
            step, stderr = _run_step("truth", [py, "-m", "fomc.truth"], lab, TRUTH_TIMEOUT)
            if step["returncode"] == 2:
                # Exit code 2 = the hardened parser's STALE ALARM: the NEWEST statement
                # did not parse. Outputs were still written — NOT fatal, but the stated
                # regime is frozen at the previous meeting until the parser is fixed.
                step["ok"] = True
                step["alarm"] = True
                parser_alarm = {
                    "triggered": True,
                    "meaning": (
                        "The newest FOMC statement on disk failed to parse; the "
                        "stated regime is FROZEN at the prior meeting and may be "
                        "stale. Truth outputs were still written."
                    ),
                    "alarm_text": stderr.strip(),
                }
            steps.append(step)
            if not step["ok"]:
                fatal = "fomc.truth failed"

        if fatal is None:
            step, _ = _run_step(
                "export_truth", [py, "-m", "fomc.export_truth"], lab, EXPORT_TIMEOUT
            )
            steps.append(step)
            if not step["ok"]:
                fatal = "fomc.export_truth failed"

        news_refresh: dict[str, Any] | None = None
        if fatal is None and refresh_news:
            if not _has_any_key(repo, lab, PPLX_KEY_NAMES):
                news_refresh = {
                    "skipped": True,
                    "reason": f"no {'/'.join(PPLX_KEY_NAMES)} available",
                }
            else:
                # The scoring window re-anchors to the new meeting automatically.
                news_steps = _news_steps(py, lab)
                steps.extend(news_steps)
                news_refresh = {
                    "skipped": False,
                    "ok": all(s["ok"] for s in news_steps),
                }

        stated_after = _stated_regime_snapshot()
        result: dict[str, Any] = {
            "python": py,
            "python_source": "lab_venv",
            "steps": steps,
            "stated_regime_before": stated_before,
            "stated_regime_after": stated_after,
            "parser_alarm": parser_alarm,
            "news_refresh": news_refresh,
        }
        if fatal:
            result["error"] = fatal
            return result
        if publish:
            result["publish"] = _publish(repo)
        return result
    except Exception as exc:
        return error_dict(exc)


# ---------------------------------------------------------------- publish


def _publish(repo_root: Path) -> dict[str, Any]:
    """Stage ONLY the dashboard data dir, commit as jingerzz, then fetch/rebase/push
    to origin/main with up to 3 attempts. Never raises."""

    def git(*args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *args],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            timeout=GIT_TIMEOUT,
        )

    failed = {"committed": False, "pushed": False, "sha": None, "attempts": 0}
    try:
        publish_path = _publish_path(repo_root)
        add = git("add", "--", publish_path)
        if add.returncode != 0:
            return {**failed, "note": f"git add failed: {(add.stderr or '').strip()}"}
        staged = git("diff", "--cached", "--quiet", "--", publish_path)
        if staged.returncode == 0:
            return {**failed, "note": "no data changes"}

        msg = (
            f"Refresh FOMC dashboard data "
            f"({datetime.now(timezone.utc).date().isoformat()}) [fomc-intel MCP]"
        )
        commit = git(
            "-c",
            f"user.name={PUBLISH_NAME}",
            "-c",
            f"user.email={PUBLISH_EMAIL}",
            "commit",
            "--author",
            PUBLISH_AUTHOR,
            "-m",
            msg,
        )
        if commit.returncode != 0:
            detail = (commit.stderr or commit.stdout or "").strip()
            return {**failed, "note": f"git commit failed: {detail}"}

        pushed = False
        attempts = 0
        notes: list[str] = []
        for attempt in range(1, PUSH_ATTEMPTS + 1):
            attempts = attempt
            fetch = git("fetch", "origin")
            if fetch.returncode != 0:
                notes.append(f"attempt {attempt}: fetch failed")
                continue
            rebase = git("rebase", "origin/main")
            if rebase.returncode != 0:
                git("rebase", "--abort")
                notes.append(f"attempt {attempt}: rebase failed")
                continue
            push = git("push", "origin", "HEAD:main")
            if push.returncode == 0:
                pushed = True
                break
            notes.append(
                f"attempt {attempt}: push rejected: {(push.stderr or '').strip()[:200]}"
            )
        sha_proc = git("rev-parse", "HEAD")
        sha = (sha_proc.stdout or "").strip() or None
        note = "pushed to origin/main" if pushed else ("; ".join(notes) or "push failed")
        return {"committed": True, "pushed": pushed, "sha": sha, "attempts": attempts, "note": note}
    except Exception as exc:
        return {**failed, "note": f"{type(exc).__name__}: {exc}"}


def to_thread(fn: Callable[..., dict[str, Any]]) -> Callable[..., Awaitable[dict[str, Any]]]:
    """Async registration wrapper: run a blocking pipeline tool in a worker thread.

    The MCP SDK calls SYNC tool functions directly on the event loop, so a
    multi-minute refresh_intel froze the whole server — no ping replies, no
    concurrent tool calls — which degraded a live Claude Desktop session
    (2026-07-11 bug report, Finding 1). functools.wraps preserves the name,
    docstring, and signature, so the registered MCP schema is unchanged; only
    the execution moves off-loop.
    """

    @functools.wraps(fn)
    async def runner(**kwargs: Any) -> dict[str, Any]:
        return await anyio.to_thread.run_sync(functools.partial(fn, **kwargs))

    return runner


def register(mcp: Any) -> None:
    mcp.tool()(to_thread(refresh_intel))
    mcp.tool()(to_thread(ingest_meeting))
