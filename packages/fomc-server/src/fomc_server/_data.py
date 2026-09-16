"""JSON document readers. Each returns (document, provenance) and RAISES on failure —
tool wrappers catch and convert to {"error": ...} dicts (tools never raise).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fomc_server import _paths
from fomc_server._provenance import stamp

Doc = dict[str, Any]
Stamped = tuple[Doc, dict[str, Any]]


def _read(path: Path) -> Stamped:
    if not path.exists():
        raise FileNotFoundError(f"data file not found: {path}")
    doc = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(doc, dict):
        raise ValueError(f"expected a JSON object in {path}, got {type(doc).__name__}")
    return doc, stamp(path, doc.get("generated_at"))


def load_latest() -> Stamped:
    """RegimeIntelDocument (news vote-share axis)."""
    return _read(_paths.latest_json())


def load_balance_sheet() -> Stamped:
    """Deterministic FRED balance-sheet axis document."""
    return _read(_paths.balance_sheet_json())


def load_market_pricing() -> Stamped:
    """Deterministic FRED market-pricing axis document."""
    return _read(_paths.market_pricing_axis_json())


def load_history() -> Stamped:
    """Daily log of net_lean / inferred regime points."""
    return _read(_paths.history_json())


def load_truth() -> Stamped:
    """Per-event SPY/TLT source-truth table."""
    return _read(_paths.truth_json())


def truth_events(doc: Doc) -> list[Doc]:
    events = doc.get("events")
    if not isinstance(events, list):
        raise ValueError("fomc_event_truth.json has no 'events' list")
    return events
