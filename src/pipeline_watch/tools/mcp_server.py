"""MCP server exposing the read-only GitHub tools used by pipeline_watch.

Run with the MCP Inspector for manual testing:

    uv run python -m pipeline_watch.tools.mcp_server

Only *read* tools are exposed. Any write operation (open_pr) is intentionally
kept out of MCP: it must go through PolicyGate + a live GitHub token from the
process environment, not through an external MCP call.
"""

from __future__ import annotations

import os

from mcp.server.mcpserver import MCPServer

from pipeline_watch.tools.github_client import GitHubClient

mcp = MCPServer("pipeline_watch")


def _client() -> GitHubClient:
    mode = os.environ.get("PW_GITHUB_MODE", "fixture")
    if mode == "github":
        return GitHubClient(mode="github", token=os.environ["GITHUB_TOKEN"])
    return GitHubClient(mode="fixture")


@mcp.tool()
def get_workflow_run(repo: str, run_id: str) -> dict:
    """Fetch a single GitHub Actions workflow run.

    Args:
        repo: "owner/name", e.g. "j-rdel/pipeline_watch". Ignored in fixture mode.
        run_id: run identifier. In fixture mode, must match a file in
                fixtures/workflow_runs/{run_id}.json.

    Returns:
        Subset of the GitHub workflow_run payload (id, name, head_branch,
        head_sha, event, status, conclusion, run_started_at, repository,
        jobs_url).
    """

    return _client().get_workflow_run(repo=repo, run_id=run_id).model_dump()


@mcp.tool()
def get_job_logs(repo: str, run_id: str, job_id: int) -> str:
    """Fetch the raw log text for a single job of a workflow run.

    Args:
        repo: "owner/name". Ignored in fixture mode.
        run_id: run identifier (needed for the fixture backend).
        job_id: job identifier.

    Returns:
        Raw log text. May be truncated by the caller downstream.
    """

    return _client().get_job_logs(repo=repo, run_id=run_id, job_id=job_id)


if __name__ == "__main__":
    mcp.run()
