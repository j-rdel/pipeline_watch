"""decide_action — deterministic router that computes the branch decision.

Writes `decision`, `policy_gate_passed`, and `policy_gate_reason` to state so
the downstream conditional edge just reads `decision`. The real PolicyGate
(task #8) will replace this with allowlist + adversarial-input checks.
"""

from __future__ import annotations

from pipeline_watch.schema import FailureClass
from pipeline_watch.state import TriageState


def decide_action(state: TriageState) -> dict:
    classification = state["classification"]
    flakiness = state["flakiness"]

    if flakiness.is_flaky:
        return {
            "decision": "notify_only",
            "policy_gate_passed": False,
            "policy_gate_reason": (
                f"Flaky signature (score={flakiness.score:.2f}, "
                f"similar={flakiness.similar_failures_7d} in 7d) — do not autofix."
            ),
        }

    autofix_allowed = {FailureClass.LINT}
    if (
        classification.label in autofix_allowed
        and classification.confidence >= 0.8
    ):
        return {
            "decision": "autofix",
            "policy_gate_passed": True,
            "policy_gate_reason": (
                f"Class {classification.label} in autofix allowlist and "
                f"confidence {classification.confidence:.2f} >= 0.8."
            ),
        }

    return {
        "decision": "notify_only",
        "policy_gate_passed": False,
        "policy_gate_reason": (
            f"Class {classification.label} not in autofix allowlist "
            f"(or confidence {classification.confidence:.2f} < 0.8)."
        ),
    }


def route_after_decide(state: TriageState) -> str:
    return state["decision"]
