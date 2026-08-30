"""notify_discord — notify-only path terminal side-effect.

Delegates to DiscordPublisher which honours PW_DRY_RUN + DISCORD_WEBHOOK_URL.
State receipt: `discord_message_id` = 'sent' on real POST, None otherwise.

Note the report may not yet be assembled here (that happens in
persist_incident). We build a *provisional* report from state so the
publisher can render the embed. persist_incident then produces the
canonical report saved to memory.
"""

from __future__ import annotations

from datetime import UTC, datetime

from pipeline_watch.publishers.discord import DiscordPublisher
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


def notify_discord(state: TriageState) -> dict:
    publisher = DiscordPublisher()
    result = publisher.publish(_provisional_report(state))
    return {"discord_message_id": result}
