"""estimate_flakiness — fan-in point, deterministic.

Stub: returns hardcoded FlakinessScore. Real impl (task #7) queries SQLite
for failures with the same error_signature over the last 7 days.
"""

from __future__ import annotations

from pipeline_watch.schema import FlakinessScore
from pipeline_watch.state import TriageState


def estimate_flakiness(state: TriageState) -> dict:
    # Placeholder: no history yet, assume not flaky.
    score = FlakinessScore(
        score=0.0,
        similar_failures_7d=0,
        total_runs_7d=1,
        is_flaky=False,
    )
    return {"flakiness": score}
