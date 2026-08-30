"""retrieve_runbook — parallel branch B, RAG-backed.

Queries the FAISS index built over docs/runbook/*.md and returns the top-k
chunks as plain strings. The synthesize node uses them as context for the
diagnosis — they are NOT cited as Evidence (evidence must come from the log).
"""

from __future__ import annotations

from pipeline_watch import rag as rag_mod
from pipeline_watch.state import TriageState

_TOP_K = 2
_MAX_CHUNK_CHARS = 800


def _build_query(state: TriageState) -> str:
    ctx = state["context"]
    lines = [f"Workflow {ctx['workflow_name']} on {ctx['head_branch']}: failed."]
    for job in ctx["failed_jobs"]:
        lines.append(f"Job {job['name']}: {job['logs'][:500]}")
    return "\n".join(lines)


def retrieve_runbook(state: TriageState) -> dict:
    index = rag_mod.get_index()
    chunks = index.query(_build_query(state), k=_TOP_K)
    snippets = [
        (f"[{c.source} — {c.heading}] " + c.body[:_MAX_CHUNK_CHARS])
        for c in chunks
    ]
    return {"runbook_snippets": snippets}
