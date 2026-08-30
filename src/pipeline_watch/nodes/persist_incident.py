"""persist_incident — assemble the final IncidentReport and record it in memory.

Records one row per FAILED job so the flakiness estimator can key on signature.
If the same run had two failed jobs with different signatures, both count for
their respective signature groups.
"""

from __future__ import annotations

from datetime import UTC, datetime

from pipeline_watch import memory as memory_mod
from pipeline_watch.schema import Classification, IncidentReport, Severity
from pipeline_watch.state import TriageState


def persist_incident(state: TriageState) -> dict:
    ctx = state["context"]
    classification: Classification = state["classification"]
    decision = state["decision"]

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
        human_approval_required=(decision == "notify_only"),
        correlation_id=state.get("correlation_id", ctx["run_id"]),
    )

    store = memory_mod.get_store()
    for job in ctx["failed_jobs"]:
        signature = memory_mod.signature_from_logs(job["logs"])
        store.record(
            run_id=ctx["run_id"],
            workflow=ctx["workflow_name"],
            job_name=job["name"],
            error_signature=signature,
            outcome=decision,
            decision=decision,
        )

    return {"report": report}
