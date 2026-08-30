"""fetch_run_context — first node of the graph.

Uses `GitHubClient` (either fixture-backed or real HTTP) to load the workflow
run, its jobs, and the logs of every failed job. The MCP server in
`tools/mcp_server.py` wraps the same client so external clients (Claude,
Cursor, the MCP Inspector) can call the tools too.

State inputs:
    run_id (str)       — GitHub Actions run id or fixture id.
    source (str)       — "fixture" | "github".
    repository (str?)  — required when source="github". Falls back to
                         GITHUB_REPO env var. Ignored for fixtures.

State outputs:
    context (RunContext) — denormalized view fed to the rest of the graph.
"""

from __future__ import annotations

import os

from pipeline_watch.state import RunContext, TriageState, WorkflowJob
from pipeline_watch.tools.github_client import GitHubClient, GitHubClientError

_LOG_MAX_CHARS = 20_000


def _build_client(source: str) -> GitHubClient:
    if source == "github":
        token = os.environ.get("GITHUB_TOKEN")
        if not token:
            raise GitHubClientError("source=github requires GITHUB_TOKEN in env")
        return GitHubClient(mode="github", token=token)
    return GitHubClient(mode="fixture")


def fetch_run_context(state: TriageState) -> dict:
    run_id = state.get("run_id", "lint-fixture")
    source = state.get("source", "fixture")
    repo_override = state.get("repository") or os.environ.get("GITHUB_REPO", "")

    client = _build_client(source)
    run = client.get_workflow_run(repo=repo_override, run_id=run_id)
    all_jobs = client.get_jobs(repo=repo_override, run_id=run_id)

    failed_jobs: list[WorkflowJob] = []
    for job in all_jobs:
        if job.conclusion != "failure":
            continue
        logs = client.get_job_logs(repo=repo_override, run_id=run_id, job_id=job.id)
        if len(logs) > _LOG_MAX_CHARS:
            logs = logs[-_LOG_MAX_CHARS:]  # keep the tail — errors live there
        failed_jobs.append(
            WorkflowJob(
                id=job.id,
                name=job.name,
                conclusion=job.conclusion,
                started_at=job.started_at,
                completed_at=job.completed_at,
                logs=logs,
            )
        )

    context: RunContext = {
        "run_id": run_id,
        "workflow_name": run.name,
        "repository": run.repository.full_name,
        "head_sha": run.head_sha,
        "head_branch": run.head_branch,
        "event": run.event,
        "started_at": run.run_started_at,
        "conclusion": run.conclusion,
        "failed_jobs": failed_jobs,
    }
    return {"context": context}
