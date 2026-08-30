"""LangGraph shared state for the triage flow.

The state is a plain TypedDict — LangGraph will merge partial updates node by
node. Optional fields start as None; nodes downstream must handle that.

Reducers (Annotated[..., add_messages] etc.) are intentionally NOT used here:
each node writes distinct keys, so simple last-write-wins merging is enough.
For the parallel branch (classify + retrieve_runbook), the two nodes write
different keys (`classification` vs `runbook_snippets`) so there is no race.
"""

from __future__ import annotations

from typing import TypedDict

from pipeline_watch.schema import (
    Classification,
    Evidence,
    FlakinessScore,
    IncidentReport,
    ProposedPatch,
)


class WorkflowJob(TypedDict):
    """Denormalized subset of the GitHub Actions Job payload we care about."""

    id: int
    name: str
    conclusion: str  # "failure" | "success" | "cancelled" | "skipped"
    started_at: str
    completed_at: str | None
    logs: str  # raw log text, may be truncated upstream


class RunContext(TypedDict):
    """Fetched once at the start of the flow by fetch_run_context."""

    run_id: str
    workflow_name: str
    repository: str
    head_sha: str
    head_branch: str
    event: str  # "push" | "pull_request" | ...
    started_at: str
    conclusion: str
    failed_jobs: list[WorkflowJob]


class TriageState(TypedDict, total=False):
    """Shared state threaded through every LangGraph node.

    `total=False` because most nodes populate only a subset. The final
    aggregator (persist_incident) is the only one that reads everything.
    """

    # --- inputs ---
    run_id: str
    source: str  # "fixture" | "github"
    correlation_id: str

    # --- filled by fetch_run_context ---
    context: RunContext

    # --- filled by classify_failure (LLM, parallel branch A) ---
    classification: Classification

    # --- filled by retrieve_runbook (RAG, parallel branch B) ---
    runbook_snippets: list[str]

    # --- filled by estimate_flakiness (deterministic + memory) ---
    flakiness: FlakinessScore

    # --- filled by synthesize_diagnosis (LLM) ---
    root_cause_hypothesis: str
    evidence: list[Evidence]
    severity: str
    suggested_action: str

    # --- filled by propose_patch (LLM, only on autofix path) ---
    proposed_patch: ProposedPatch | None

    # --- decision + policy audit trail ---
    decision: str  # "autofix" | "notify_only"
    policy_gate_passed: bool
    policy_gate_reason: str

    # --- final artifact ---
    report: IncidentReport

    # --- side-effect receipts (dry-run captures the payload without sending) ---
    pr_url: str | None
    discord_message_id: str | None
