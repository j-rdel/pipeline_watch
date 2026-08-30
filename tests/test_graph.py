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
    assert final["pr_url"] is not None
    assert final.get("discord_message_id") is None

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
    assert final["discord_message_id"] == "stub-msg-0001"

    report = final["report"]
    assert report.human_approval_required is True
    assert report.proposed_patch is None
    assert report.severity.value == "high"


def test_report_evidence_comes_from_both_parallel_branches(graph):
    final = graph.invoke(
        {"run_id": "lint-fixture", "source": "fixture", "correlation_id": "cid-ev"}
    )
    report = final["report"]
    sources = {e.source for e in report.evidence}
    assert any(s.startswith("job:") for s in sources)
    assert "runbook" in sources


def test_correlation_id_flows_end_to_end(graph):
    final = graph.invoke(
        {"run_id": "lint-fixture", "source": "fixture", "correlation_id": "cid-corr"}
    )
    assert final["report"].correlation_id == "cid-corr"
