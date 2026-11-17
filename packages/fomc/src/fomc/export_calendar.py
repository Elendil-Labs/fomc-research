"""Export the FOMC meeting calendar into the static dashboard's `public/data`.

The schedule itself lives in `fomc.calendar` (the single source of truth); this step
only serialises it so the browser app can fetch it at runtime instead of carrying its
own copy of the dates. Offline and deterministic apart from the timestamps, so the
refresh workflow can run it on every pass.

Usage:
    fomc export-calendar
    fomc export-calendar --json apps/fomc-dashboard/public/data/fomc_calendar.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from fomc.calendar import calendar_document
from fomc.event_study import OUT_DIR

REPO = OUT_DIR.parents[2]  # fomc-spy-tlt-lab/ (or the repo root in the flat layout)
DASHBOARD_DATA = REPO / "apps" / "fomc-dashboard" / "public" / "data"
DEFAULT_JSON = DASHBOARD_DATA / "fomc_calendar.json"


def run(json_out: Path) -> dict:
    doc = calendar_document()
    json_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")

    cov = doc["provenance"]["coverage"]
    print(
        f"Exported {len(doc['meetings'])} meetings "
        f"({cov['n_decisions']} decisions, {cov['n_strategy_meetings']} strategy) "
        f"through {cov['last_decision']}"
    )
    print(f"  JSON: {json_out}")
    if doc["provenance"]["schedule_warning"]:
        print(f"  WARNING: {doc['provenance']['schedule_warning']}")
    return doc


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Export the FOMC meeting calendar for the dashboard")
    p.add_argument("--json", type=Path, default=DEFAULT_JSON,
                   help="destination JSON (default: dashboard public/data)")
    args = p.parse_args(argv)
    run(args.json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
