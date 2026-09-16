"""Export the FOMC event-truth table into the static dashboard's `public/data`.

Reads the canonical `data/fomc/analysis/fomc_event_truth.csv` (built by `fomc truth`)
and emits two artifacts the static Vite/React dashboard consumes at runtime:

  * a verbatim CSV copy            (human-downloadable, audit trail)
  * a typed JSON document          (the app fetches this; numbers parsed, null-safe)

This step is intentionally offline: it never fetches prices. Run `fomc truth` first
when you want the underlying numbers refreshed; `export-truth` only re-shapes whatever
is already in the canonical CSV. That keeps CI fast and the JSON byte-for-byte
reproducible from the committed CSV.

Usage:
    fomc export-truth
    fomc export-truth --csv apps/fomc-dashboard/public/data/fomc_event_truth.csv \
                      --json apps/fomc-dashboard/public/data/fomc_event_truth.json
"""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path

from fomc.event_study import OUT_DIR

REPO = OUT_DIR.parents[2]  # repo root (data/fomc/analysis -> ../../..)
DASHBOARD_DATA = REPO / "apps" / "fomc-dashboard" / "public" / "data"

SOURCE_CSV = OUT_DIR / "fomc_event_truth.csv"

# Columns that should be parsed as floats (everything return/price related). Anything
# not listed here and not `emergency` stays a string. Missing cells -> JSON null.
_STRING_COLS = {"date", "chair", "regime", "action", "ff_target"}
_BOOL_COLS = {"emergency"}


def _coerce(col: str, raw: str) -> object:
    raw = (raw or "").strip()
    if col in _STRING_COLS:
        return raw
    if col in _BOOL_COLS:
        return raw.lower() in ("true", "1", "yes")
    if raw == "":
        return None
    try:
        return float(raw)
    except ValueError:
        return raw


def load_events(source_csv: Path) -> tuple[list[str], list[dict]]:
    if not source_csv.exists():
        raise FileNotFoundError(
            f"{source_csv} not found — run `fomc truth` first to build the event-truth table."
        )
    with source_csv.open(newline="") as f:
        reader = csv.DictReader(f)
        columns = list(reader.fieldnames or [])
        events = [{c: _coerce(c, row.get(c, "")) for c in columns} for row in reader]
    return columns, events


def build_document(columns: list[str], events: list[dict]) -> dict:
    dates = [e["date"] for e in events if e.get("date")]
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": str(SOURCE_CSV.relative_to(REPO)),
        "count": len(events),
        "first_event_date": min(dates) if dates else None,
        "latest_event_date": max(dates) if dates else None,
        "columns": columns,
        "events": events,
    }


def run(csv_out: Path, json_out: Path, source_csv: Path = SOURCE_CSV) -> dict:
    columns, events = load_events(source_csv)
    doc = build_document(columns, events)

    csv_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.parent.mkdir(parents=True, exist_ok=True)
    csv_out.write_bytes(source_csv.read_bytes())
    json_out.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")

    span = f"{doc['first_event_date']} → {doc['latest_event_date']}"
    print(f"Exported {doc['count']} events ({span})")
    print(f"  CSV : {csv_out}")
    print(f"  JSON: {json_out}")
    return doc


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Export FOMC event-truth CSV+JSON for the dashboard")
    p.add_argument("--csv", type=Path, default=DASHBOARD_DATA / "fomc_event_truth.csv",
                   help="destination CSV (default: dashboard public/data)")
    p.add_argument("--json", type=Path, default=DASHBOARD_DATA / "fomc_event_truth.json",
                   help="destination JSON (default: dashboard public/data)")
    p.add_argument("--source", type=Path, default=SOURCE_CSV,
                   help="source canonical CSV (default: data/fomc/analysis/fomc_event_truth.csv)")
    args = p.parse_args(argv)
    run(args.csv, args.json, args.source)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
