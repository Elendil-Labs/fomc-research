"""Server boot: all 16 tools registered with FastMCP, disclaimers present, and an
in-process client smoke over the MCP wire protocol."""

import asyncio
import json

from mcp.shared.memory import create_connected_server_and_client_session as client_session

from fomc_server import server as srv
from fomc_server.tools import NO_ADVICE

EXPECTED_TOOLS = {
    "get_fomc_guide",
    "get_regime_read",
    "get_two_axis_state",
    "get_balance_sheet_axis",
    "get_market_pricing_axis",
    "get_playbook",
    "get_event_history",
    "get_news_evidence",
    "get_daily_log",
    "get_checklist",
    "get_stated_regime",
    "get_fomc_calendar",
    # phase B
    "search_fed_corpus",
    "diff_statements",
    "refresh_intel",
    "ingest_meeting",
}


def test_all_16_tools_registered():
    tools = asyncio.run(srv.mcp.list_tools())
    assert {t.name for t in tools} == EXPECTED_TOOLS
    assert len(tools) == 16


def test_every_tool_description_ends_with_no_advice():
    tools = asyncio.run(srv.mcp.list_tools())
    for t in tools:
        assert (t.description or "").strip().endswith(NO_ADVICE), t.name


def test_in_process_client_smoke():
    async def smoke():
        async with client_session(srv.mcp._mcp_server) as client:
            listed = await client.list_tools()
            assert {t.name for t in listed.tools} == EXPECTED_TOOLS
            result = await client.call_tool("get_regime_read", {})
            assert not result.isError
            payload = json.loads(result.content[0].text)
            assert "descriptor" in payload and "provenance" in payload

    asyncio.run(smoke())


def test_main_help_exits_zero(capsys):
    try:
        srv.main(["--help"])
    except SystemExit as e:
        assert e.code == 0
    out = capsys.readouterr().out
    assert "--transport" in out and "stdio" in out and "http" in out


def test_pipeline_tools_are_registered_async():
    """The two subprocess-running tools must be async (worker-thread offload) so a
    multi-minute refresh cannot freeze the server's event loop (F1, 2026-07-11)."""
    for name in ("refresh_intel", "ingest_meeting"):
        tool = srv.mcp._tool_manager.get_tool(name)
        assert tool is not None, name
        assert tool.is_async, f"{name} must be registered as an async (offloaded) tool"
