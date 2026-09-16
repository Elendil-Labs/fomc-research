"""Thin wrapper over `fomc export-truth` so the dashboard data export is also runnable
as a plain script (matching the implementation plan's scripts/ layout).

    python scripts/export_event_truth_json.py [--csv PATH --json PATH --source PATH]

All real logic lives in fomc.export_truth so the CLI command and this script stay in
lockstep.
"""

from __future__ import annotations

import sys

from fomc.export_truth import main

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
