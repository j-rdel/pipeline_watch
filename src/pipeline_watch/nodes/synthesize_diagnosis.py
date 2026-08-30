"""synthesize_diagnosis — LLM synthesis of hypothesis + evidence + severity + action.

The LLM output is constrained to a helper `DiagnosisOutput` model; the node
then unpacks it into the top-level TriageState keys the graph expects. This
keeps the LLM's contract narrow and avoids leaking the full IncidentReport
shape into the prompt.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from pipeline_watch import llm as llm_mod
from pipeline_watch.prompts import SYNTHESIZE_SYSTEM
from pipeline_watch.schema import Evidence, Severity
from pipeline_watch.state import TriageState


class DiagnosisOutput(BaseModel):
    root_cause_hypothesis: str = Field(max_length=1000)
    evidence: list[Evidence] = Field(min_length=1)
    severity: Severity
    suggested_action: str = Field(max_length=600)


def _build_user_message(state: TriageState) -> str:
    ctx = state["context"]
    classification = state["classification"]
    snippets = state.get("runbook_snippets", [])
    logs = "\n\n".join(
        f"--- {j['name']} ---\n{j['logs']}" for j in ctx["failed_jobs"]
    )
    lines = [
        f"Classification: {classification.label} (confidence {classification.confidence:.2f})",
        f"Reasoning: {classification.reasoning}",
        "",
        "Runbook snippets:",
        *([f"- {s}" for s in snippets] or ["- (none matched)"]),
        "",
        "Failed job logs:",
        logs,
    ]
    return "\n".join(lines)


def synthesize_diagnosis(state: TriageState) -> dict:
    result: DiagnosisOutput = llm_mod.structured_output(
        DiagnosisOutput,
        system=SYNTHESIZE_SYSTEM,
        user=_build_user_message(state),
    )
    return {
        "root_cause_hypothesis": result.root_cause_hypothesis,
        "evidence": result.evidence,
        "severity": result.severity.value,
        "suggested_action": result.suggested_action,
    }
