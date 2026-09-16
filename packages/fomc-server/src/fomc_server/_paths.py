"""Path resolution for the fomc-intel server.

The repo root is found by walking up from this file until we hit a directory that
contains BOTH `packages/` and `data/`. Override with the FOMC_INTEL_REPO_ROOT
environment variable — read at call time, so tests can repoint the server at a
sandbox directory.

Two layouts are supported:

  * flat (this repo, `fomc-research`): the lab IS the repo root, so `lab_root()`
    == `repo_root()` and the dashboard data lives at
    `<repo>/apps/fomc-dashboard/public/data`.
  * nested (the original monorepo, or the synthetic test layouts): the lab lives in a
    `fomc-spy-tlt-lab/` subdirectory of the repo root. `lab_root()` picks that
    subdirectory whenever it exists.
"""

from __future__ import annotations

import os
from pathlib import Path

ENV_REPO_ROOT = "FOMC_INTEL_REPO_ROOT"
NESTED_LAB_DIRNAME = "fomc-spy-tlt-lab"


def repo_root() -> Path:
    """Resolve the repo root (env override wins)."""
    env = os.environ.get(ENV_REPO_ROOT)
    if env:
        return Path(env).expanduser()
    current = Path(__file__).resolve().parent
    for _ in range(16):
        if (current / "packages").is_dir() and (current / "data").is_dir():
            return current
        if current == current.parent:
            break
        current = current.parent
    raise FileNotFoundError(
        "Could not locate the repo root (a directory containing both packages/ and "
        f"data/) walking up from {Path(__file__).resolve()}. "
        f"Set {ENV_REPO_ROOT} to override."
    )


def lab_root_for(repo: Path) -> Path:
    """The lab directory for a given repo root: nested subdir if present, else the root."""
    nested = repo / NESTED_LAB_DIRNAME
    return nested if nested.is_dir() else repo


def lab_root() -> Path:
    return lab_root_for(repo_root())


def dashboard_data_dir() -> Path:
    return lab_root() / "apps" / "fomc-dashboard" / "public" / "data"


def regime_intel_dir() -> Path:
    return dashboard_data_dir() / "regime_intel"


def latest_json() -> Path:
    return regime_intel_dir() / "latest.json"


def balance_sheet_json() -> Path:
    return regime_intel_dir() / "balance_sheet.json"


def market_pricing_axis_json() -> Path:
    return regime_intel_dir() / "market_pricing_axis.json"


def history_json() -> Path:
    return regime_intel_dir() / "history.json"


def truth_json() -> Path:
    return dashboard_data_dir() / "fomc_event_truth.json"
