"""propose_patch — LLM-generated patch, only on the autofix path.

The graph only routes here when decide_action returned "autofix", but this
node still short-circuits when the LLM reports rationale='not-mechanical' —
that is treated as "no patch to apply" and downstream open_pr will skip.
"""

from __future__ import annotations

from pipeline_watch import llm as llm_mod
from pipeline_watch.prompts import PROPOSE_PATCH_SYSTEM
from pipeline_watch.schema import ProposedPatch
from pipeline_watch.state import TriageState


def _build_user_message(state: TriageState) -> str:
    ctx = state["context"]
    classification = state["classification"]
    lines = [
        f"Classification: {classification.label}",
        "",
        "Failed job logs:",
    ]
    for job in ctx["failed_jobs"]:
        lines.append(f"\n--- {job['name']} ---")
        lines.append(job["logs"])
    return "\n".join(lines)


def propose_patch(state: TriageState) -> dict:
    try:
        patch: ProposedPatch = llm_mod.structured_output(
            ProposedPatch,
            system=PROPOSE_PATCH_SYSTEM,
            user=_build_user_message(state),
        )
    except Exception:
        # LLM failed to produce a valid patch — that's fine, autofix is
        # opportunistic. Downstream open_pr handles None by skipping.
        return {"proposed_patch": None}
    if patch.rationale.strip().lower() == "not-mechanical" or not patch.diff.strip():
        return {"proposed_patch": None}
    return {"proposed_patch": patch}
