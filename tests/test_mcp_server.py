"""Smoke tests for the MCP server tools.

We don't spin up the MCP transport — that's for the Inspector. We only
invoke the underlying tool callables to make sure the wiring is intact and
they return serializable payloads.
"""

from __future__ import annotations

import json

import pytest

from pipeline_watch.tools import mcp_server as srv


@pytest.mark.asyncio
async def test_mcp_registers_expected_tools():
    tools = await srv.mcp.list_tools()
    names = {t.name for t in tools}
    assert {"get_workflow_run", "get_job_logs"}.issubset(names)


def _text(result) -> str:
    return "\n".join(block.text for block in result.content if hasattr(block, "text"))


@pytest.mark.asyncio
async def test_get_workflow_run_tool_returns_expected_payload():
    result = await srv.mcp.call_tool(
        "get_workflow_run",
        arguments={"repo": "ignored", "run_id": "lint-fixture"},
    )
    payload = json.loads(_text(result))
    assert payload["id"] == 987654321
    assert payload["repository"]["full_name"] == "j-rdel/pipeline_watch"


@pytest.mark.asyncio
async def test_get_job_logs_tool_returns_text():
    result = await srv.mcp.call_tool(
        "get_job_logs",
        arguments={"repo": "ignored", "run_id": "lint-fixture", "job_id": 5001},
    )
    assert "E501 Line too long" in _text(result)
