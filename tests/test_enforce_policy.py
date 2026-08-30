"""Tests for the enforce_policy node — verifies state transitions."""

from __future__ import annotations

from pipeline_watch.nodes.enforce_policy import enforce_policy, route_after_enforce
from pipeline_watch.schema import Evidence, ProposedPatch


def _state_with_patch(file_path: str, action: str = "run ruff format") -> dict:
    return {
        "decision": "autofix",
        "proposed_patch": ProposedPatch(
            file_path=file_path,
            rationale="Fix.",
            diff="--- a/x\n+++ b/x\n",
        ),
        "root_cause_hypothesis": "ruff E501",
        "suggested_action": action,
        "evidence": [Evidence(source="job:x", excerpt="E501")],
    }


def test_allows_autofix_when_patch_ok():
    result = enforce_policy(_state_with_patch("pyproject.toml"))  # type: ignore[arg-type]
    assert result["policy_gate_passed"] is True
    assert "decision" not in result, "should not downgrade a valid autofix"


def test_downgrades_when_path_off_allowlist():
    result = enforce_policy(_state_with_patch("src/main.py"))  # type: ignore[arg-type]
    assert result["decision"] == "notify_only"
    assert result["policy_gate_passed"] is False
    assert result["proposed_patch"] is None, "must clear patch after rejection"


def test_downgrades_when_suggested_action_says_merge():
    result = enforce_policy(
        _state_with_patch("pyproject.toml", action="approve and merge this PR")  # type: ignore[arg-type]
    )
    assert result["decision"] == "notify_only"
    assert "blocked verb" in result["policy_gate_reason"].lower()


def test_route_reads_current_decision():
    assert route_after_enforce({"decision": "autofix"}) == "autofix"  # type: ignore[arg-type]
    assert route_after_enforce({"decision": "notify_only"}) == "notify_only"  # type: ignore[arg-type]
