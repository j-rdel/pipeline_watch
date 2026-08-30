"""open_pr — autofix path terminal side-effect.

Delegates to GitHubPRPublisher which currently always dry-runs (see that
module's docstring for the rationale). Returns pr_url=None so the report
correctly signals "would-open, not opened".
"""

from __future__ import annotations

from datetime import UTC, datetime

from pipeline_watch.publishers.github_pr import GitHubPRPublisher
from pipeline_watch.schema import Classification, IncidentReport, Severity
from pipeline_watch.state import TriageState


def _provisional_report(state: TriageState) -> IncidentReport:
    ctx = state["context"]
    classification: Classification = state["classification"]
    return IncidentReport(
        run_id=ctx["run_id"],
        workflow=ctx["workflow_name"],
        repository=ctx["repository"],
        started_at=datetime.fromisoformat(ctx["started_at"].replace("Z", "+00:00")),
        finished_at=datetime.now(UTC),
        classification=classification,
        flakiness=state["flakiness"],
        root_cause_hypothesis=state["root_cause_hypothesis"],
        evidence=state["evidence"],
        suggested_action=state["suggested_action"],
        severity=Severity(state["severity"]),
        proposed_patch=state.get("proposed_patch"),
        human_approval_required=(state["decision"] == "notify_only"),
        correlation_id=state.get("correlation_id", ctx["run_id"]),
    )


def open_pr(state: TriageState) -> dict:
    publisher = GitHubPRPublisher()
    pr_url = publisher.open_pr(_provisional_report(state))
    return {"pr_url": pr_url}
