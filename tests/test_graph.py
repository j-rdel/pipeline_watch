"""End-to-end smoke tests for the LangGraph skeleton.

Every node is a stub, so these tests validate topology (fan-out, fan-in,
conditional routing) and the state contract — not real classification logic.
Scenario switching is done by `run_id` (see fetch_run_context._FIXTURES).
"""

from __future__ import annotations

import pytest

from pipeline_watch.graph import build_graph
from pipeline_watch.schema import FailureClass, IncidentReport


@pytest.fixture
def graph():
    return build_graph()


def test_lint_fixture_routes_to_autofix(graph):
    final = graph.invoke(
        {"run_id": "lint-fixture", "source": "fixture", "correlation_id": "cid-lint"}
    )

    # topology assertions — both parallel branches must have written to state
    assert "classification" in final, "classify_failure did not write to state"
    assert "runbook_snippets" in final, "retrieve_runbook did not write to state"
    assert "flakiness" in final, "estimate_flakiness ran after fan-in"
    assert "decision" in final, "decide_action ran"

    assert final["classification"].label == FailureClass.LINT
    assert final["decision"] == "autofix"
    assert final["policy_gate_passed"] is True
    assert final["proposed_patch"] is not None
    # Both publishers dry-run by default → receipts are None but the branch
    # was exercised (open_pr wrote pr_url=None to state, not skipped).
    assert "pr_url" in final and final["pr_url"] is None
    assert "discord_message_id" not in final

    report = final["report"]
    assert isinstance(report, IncidentReport)
    assert report.human_approval_required is False
    assert report.proposed_patch is not None


def test_test_failure_fixture_routes_to_notify_only(graph):
    final = graph.invoke(
        {"run_id": "test-fixture", "source": "fixture", "correlation_id": "cid-test"}
    )

    assert final["classification"].label == FailureClass.TEST_FAILURE
    assert final["decision"] == "notify_only"
    assert final["policy_gate_passed"] is False
    assert final.get("proposed_patch") is None
    assert final.get("pr_url") is None
    # notify_discord ran and wrote the key; value is None in dry-run.
    assert "discord_message_id" in final
    assert final["discord_message_id"] is None

    report = final["report"]
    assert report.human_approval_required is True
    assert report.proposed_patch is None
    assert report.severity.value == "high"


def test_both_parallel_branches_populate_state(graph):
    """classify_failure writes 'classification', retrieve_runbook writes
    'runbook_snippets'. If either failed silently, the fan-in node would
    still run but the missing key would surface here.
    """

    final = graph.invoke(
        {"run_id": "lint-fixture", "source": "fixture", "correlation_id": "cid-ev"}
    )

    assert final["classification"] is not None
    snippets = final["runbook_snippets"]
    assert snippets and isinstance(snippets, list)

    # Evidence must cite the log at minimum.
    sources = {e.source for e in final["report"].evidence}
    assert any(s.startswith("job:") for s in sources)


def test_correlation_id_flows_end_to_end(graph):
    final = graph.invoke(
        {"run_id": "lint-fixture", "source": "fixture", "correlation_id": "cid-corr"}
    )
    assert final["report"].correlation_id == "cid-corr"
