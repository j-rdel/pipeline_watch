"""fetch_run_context — first node of the graph.

Stub: returns a canned RunContext keyed by run_id. Two fixtures baked in:
  - "lint-fixture"  → ruff E501 failure
  - "test-fixture"  → pytest AssertionError failure
Anything else falls back to the lint fixture.

Real impl (task #4) will call the MCP tool `get_workflow_run` / `get_job_logs`
against GitHub API, with fixture fallback and retry.
"""

from __future__ import annotations

from pipeline_watch.state import RunContext, TriageState, WorkflowJob

_FIXTURES: dict[str, tuple[str, str]] = {
    "lint-fixture": (
        "lint",
        "ruff check .\nsrc/foo.py:12:81: E501 Line too long (108 > 100)\nFound 1 error.",
    ),
    "test-fixture": (
        "test",
        "tests/test_foo.py::test_bar FAILED\nAssertionError: 1 != 2",
    ),
}


def fetch_run_context(state: TriageState) -> dict:
    run_id = state.get("run_id", "lint-fixture")
    job_name, logs = _FIXTURES.get(run_id, _FIXTURES["lint-fixture"])
    job: WorkflowJob = {
        "id": 1,
        "name": job_name,
        "conclusion": "failure",
        "started_at": "2026-08-29T10:00:00Z",
        "completed_at": "2026-08-29T10:00:12Z",
        "logs": logs,
    }
    context: RunContext = {
        "run_id": run_id,
        "workflow_name": "ci.yml",
        "repository": "j-rdel/pipeline_watch",
        "head_sha": "deadbeef",
        "head_branch": "feature/x",
        "event": "pull_request",
        "started_at": "2026-08-29T10:00:00Z",
        "conclusion": "failure",
        "failed_jobs": [job],
    }
    return {"context": context}
