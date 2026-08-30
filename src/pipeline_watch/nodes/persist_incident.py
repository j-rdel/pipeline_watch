"""persist_incident — assemble the final IncidentReport from the shared state.

Stub: just builds the report and returns it in state. Real impl (task #7)
also writes to SQLite so the flakiness estimator can learn from history.
"""

from __future__ import annotations

from datetime import UTC, datetime

from pipeline_watch.schema import Classification, IncidentReport, Severity
from pipeline_watch.state import TriageState


def persist_incident(state: TriageState) -> dict:
    ctx = state["context"]
    classification: Classification = state["classification"]
    report = IncidentReport(
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
    return {"report": report}
