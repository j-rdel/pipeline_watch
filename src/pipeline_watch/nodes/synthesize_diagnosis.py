"""synthesize_diagnosis — LLM synthesis over classification + runbook.

Stub: assembles a diagnosis from the previous nodes' state. Real impl (task
#5) sends context to Ollama with structured output for the fields it writes.
"""

from __future__ import annotations

from pipeline_watch.schema import Evidence, FailureClass, Severity
from pipeline_watch.state import TriageState


def synthesize_diagnosis(state: TriageState) -> dict:
    classification = state["classification"]
    snippets = state.get("runbook_snippets", [])
    ctx = state["context"]
    log_excerpt = ctx["failed_jobs"][0]["logs"][:400]

    if classification.label == FailureClass.LINT:
        severity = Severity.LOW
        hypothesis = "Lint violation reported by ruff. Deterministic fix available."
        action = "Autofix via `ruff format` and open PR for review."
    elif classification.label == FailureClass.TEST_FAILURE:
        severity = Severity.HIGH
        hypothesis = "Test failure detected — likely a real regression."
        action = "No autofix. Notify author with failing test excerpt."
    else:
        severity = Severity.MEDIUM
        hypothesis = "Failure not conclusively classified. Investigate manually."
        action = "Post diagnosis to Discord and let a human triage."

    evidence = [
        Evidence(
            source=f"job:{ctx['failed_jobs'][0]['name']}/logs",
            excerpt=log_excerpt,
            line_hint=1,
        )
    ]
    if snippets:
        evidence.append(
            Evidence(
                source="runbook",
                excerpt=snippets[0][:400],
            )
        )

    return {
        "root_cause_hypothesis": hypothesis,
        "evidence": evidence,
        "severity": severity.value,
        "suggested_action": action,
    }
