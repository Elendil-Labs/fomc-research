"""get_stated_regime — statement-parsed regime via the lab's fomc.regime primitive."""

from __future__ import annotations

from datetime import date as _date
from typing import Any

from fomc_server._provenance import stamp
from fomc_server.tools import error_dict


def get_stated_regime(date: str | None = None) -> dict[str, Any]:
    """The Fed's STATED policy regime on a given ISO date (default: today), parsed
    directly from FOMC statement text: the regime label (Easing/Tightening), the rate
    action at the most recent meeting on/before that date, and the target range —
    plus the full statement-parser audit. If the newest statement on disk failed to
    parse, an ALARM field explains that the stated regime is frozen and may be stale.
    Historical/observational evidence only — not investment advice."""
    try:
        from fomc import regime as lab_regime

        query_date = _date.fromisoformat(date) if date else _date.today()
        timeline = lab_regime.build_timeline()
        result = lab_regime.regime_on(query_date, timeline)
        audit = lab_regime.audit_statements()
        resp: dict[str, Any] = {
            "query_date": query_date.isoformat(),
            **result,
            "audit": audit,
            # data_as_of = corpus dir mtime (statements are event-driven, not daily)
            "provenance": stamp(lab_regime.STMT_DIR),
        }
        if audit.get("stale"):
            resp["ALARM"] = lab_regime.format_alarm(audit)
        return resp
    except Exception as exc:
        return error_dict(exc)


def register(mcp: Any) -> None:
    mcp.tool()(get_stated_regime)
