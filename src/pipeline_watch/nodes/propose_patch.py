"""propose_patch — only runs on the autofix path.

Stub: emits a canned ruff-format diff. Real impl (task #5) has the LLM
generate a unified diff constrained to files on PW_ALLOWLIST_PATHS.
"""

from __future__ import annotations

from pipeline_watch.schema import ProposedPatch
from pipeline_watch.state import TriageState


def propose_patch(state: TriageState) -> dict:
    patch = ProposedPatch(
        file_path="src/foo.py",
        rationale="Line 12 exceeds ruff line-length limit (108 > 100).",
        diff=(
            "--- a/src/foo.py\n"
            "+++ b/src/foo.py\n"
            "@@ -10,3 +10,4 @@\n"
            " def something():\n"
            "-    result = some_very_long_expression_that_goes_way_past_the_limit(a, b, c)\n"
            "+    result = some_very_long_expression_that_goes_way_past_the_limit(\n"
            "+        a, b, c\n"
            "+    )\n"
        ),
    )
    return {"proposed_patch": patch}
