"""classify_failure — parallel branch A.

Stub: returns a canned Classification. Real impl (task #5) calls Ollama with
structured output constrained to the Classification schema.
"""

from __future__ import annotations

from pipeline_watch.schema import Classification, FailureClass
from pipeline_watch.state import TriageState


def classify_failure(state: TriageState) -> dict:
    ctx = state["context"]
    logs = "\n".join(job["logs"] for job in ctx["failed_jobs"])

    # Placeholder heuristic — real impl uses the LLM.
    if "E501" in logs or "ruff" in logs:
        label = FailureClass.LINT
        reasoning = "Log mentions ruff / E501, classic lint failure."
        confidence = 0.9
    elif "AssertionError" in logs or "FAILED" in logs:
        label = FailureClass.TEST_FAILURE
        reasoning = "Log shows AssertionError or FAILED, treating as test failure."
        confidence = 0.75
    else:
        label = FailureClass.UNKNOWN
        reasoning = "No strong signal detected in stub heuristic."
        confidence = 0.3

    return {
        "classification": Classification(
            label=label,
            confidence=confidence,
            reasoning=reasoning,
        )
    }
