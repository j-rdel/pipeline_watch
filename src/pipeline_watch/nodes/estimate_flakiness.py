"""estimate_flakiness — fan-in node, deterministic.

Reads history from the SQLite incident store and computes a score:

    score = similar_failures_7d / max(total_runs_7d, 1)

A failure is flagged flaky when both conditions hold:
    - score > 0.4
    - similar_failures_7d >= 2   (single flake is not enough evidence)

The current run is NOT counted — the estimator looks only at PRIOR history.
Persistence of the current incident happens later in persist_incident, so
"same signature seen 2 times before + this one" reads as similar=2, total=3
after this run is persisted; but at estimate time we see similar=2, total=2.
"""

from __future__ import annotations

from pipeline_watch import memory as memory_mod
from pipeline_watch.schema import FlakinessScore
from pipeline_watch.state import TriageState

_SCORE_THRESHOLD = 0.4
_MIN_FAILURES = 2


def _combined_logs(state: TriageState) -> str:
    return "\n".join(job["logs"] for job in state["context"]["failed_jobs"])


def estimate_flakiness(state: TriageState) -> dict:
    ctx = state["context"]
    signature = memory_mod.signature_from_logs(_combined_logs(state))
    store = memory_mod.get_store()

    similar = store.count_similar(error_signature=signature)
    total = store.count_runs(workflow=ctx["workflow_name"])

    score = similar / total if total > 0 else 0.0
    is_flaky = score > _SCORE_THRESHOLD and similar >= _MIN_FAILURES

    return {
        "flakiness": FlakinessScore(
            score=score,
            similar_failures_7d=similar,
            total_runs_7d=total,
            is_flaky=is_flaky,
        )
    }
