"""classify_failure — LLM node, parallel branch A.

Feeds the failing job logs to Ollama with structured output constrained to
Classification. The heuristic stub from the skeleton phase is gone.
"""

from __future__ import annotations

from pipeline_watch import llm as llm_mod
from pipeline_watch.prompts import CLASSIFY_SYSTEM
from pipeline_watch.schema import Classification
from pipeline_watch.state import TriageState


def _build_user_message(state: TriageState) -> str:
    ctx = state["context"]
    lines = [
        f"Repository: {ctx['repository']}",
        f"Workflow: {ctx['workflow_name']}",
        f"Branch: {ctx['head_branch']}",
        f"Event: {ctx['event']}",
        "",
        "Failed job logs:",
    ]
    for job in ctx["failed_jobs"]:
        lines.append(f"\n--- {job['name']} ---")
        lines.append(job["logs"])
    return "\n".join(lines)


def classify_failure(state: TriageState) -> dict:
    result: Classification = llm_mod.structured_output(
        Classification,
        system=CLASSIFY_SYSTEM,
        user=_build_user_message(state),
    )
    return {"classification": result}
