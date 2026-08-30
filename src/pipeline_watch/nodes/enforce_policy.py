"""enforce_policy — post-patch gate. Can downgrade decision to notify_only.

Runs after `propose_patch` on the autofix path. Uses PolicyGate to check the
patch and any LLM-influenced text; on rejection, mutates state so that:
  - decision                → 'notify_only'
  - policy_gate_passed      → False
  - policy_gate_reason      → the rejection reason
  - proposed_patch          → None  (so downstream open_pr / notify_discord
                                     don't try to act on a rejected patch)
"""

from __future__ import annotations

from pipeline_watch.policy import PolicyGate
from pipeline_watch.state import TriageState


def enforce_policy(state: TriageState) -> dict:
    gate = PolicyGate.from_settings()
    decision = gate.check_patch(state)

    if decision.allowed:
        return {
            "policy_gate_passed": True,
            "policy_gate_reason": decision.reason,
        }

    return {
        "decision": "notify_only",
        "policy_gate_passed": False,
        "policy_gate_reason": decision.reason,
        "proposed_patch": None,
    }


def route_after_enforce(state: TriageState) -> str:
    return state["decision"]
