"""retrieve_runbook — parallel branch B.

Stub: returns canned snippets. Real impl (task #6) does FAISS retrieval over
docs/runbook/*.md using fastembed embeddings.
"""

from __future__ import annotations

from pipeline_watch.state import TriageState


def retrieve_runbook(state: TriageState) -> dict:
    ctx = state["context"]
    logs = "\n".join(job["logs"] for job in ctx["failed_jobs"])

    if "E501" in logs or "ruff" in logs:
        snippets = [
            "Lint failures (ruff): allowed autofix — run `ruff format` "
            "and commit. Do NOT touch business logic.",
        ]
    elif "AssertionError" in logs:
        snippets = [
            "Test failures: never autofix. Post a diagnosis with the failing "
            "test name and the exception traceback so the author can react.",
        ]
    else:
        snippets = ["No matching runbook entry for this failure signature."]

    return {"runbook_snippets": snippets}
