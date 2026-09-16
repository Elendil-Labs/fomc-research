"""Provenance stamps for every data-bearing fomc-intel response.

One implementation, used by every reader: {data_as_of, retrieved_at, source, is_stale}.
`is_stale` is True when the underlying data is older than STALE_AFTER_HOURS (36h).
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

STALE_AFTER_HOURS = 36.0


def _parse_iso(ts: str | None) -> datetime | None:
    """Tolerant ISO-8601 parse; naive timestamps are assumed UTC."""
    if not ts:
        return None
    try:
        dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def stamp(source: Path, data_as_of: str | None = None) -> dict[str, Any]:
    """Build the provenance dict for a response derived from `source`.

    `data_as_of` is the document's own generated_at when it has one; otherwise the
    file mtime is used. `source` is reported relative to the repo root when possible.
    """
    now = datetime.now(timezone.utc)
    as_of = _parse_iso(data_as_of)
    if as_of is None:
        try:
            as_of = datetime.fromtimestamp(source.stat().st_mtime, tz=timezone.utc)
        except OSError:
            as_of = None
    is_stale = as_of is None or (now - as_of).total_seconds() > STALE_AFTER_HOURS * 3600
    rel: str
    try:
        from fomc_server import _paths

        rel = str(source.resolve().relative_to(_paths.repo_root().resolve()))
    except Exception:
        rel = str(source)
    return {
        "data_as_of": as_of.isoformat() if as_of else None,
        "retrieved_at": now.isoformat(),
        "source": rel,
        "is_stale": is_stale,
    }
