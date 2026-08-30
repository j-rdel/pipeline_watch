"""open_pr — autofix path terminal side-effect.

Stub: fabricates a fake pr_url. Real impl (task #10) uses the GitHub client
from senai-pr-reviewer to open a PR, but only when PW_DRY_RUN=false.
"""

from __future__ import annotations

from pipeline_watch.state import TriageState


def open_pr(state: TriageState) -> dict:
    ctx = state["context"]
    patch = state.get("proposed_patch")
    if patch is None:
        return {"pr_url": None}
    fake_url = f"https://github.com/{ctx['repository']}/pull/999"
    return {"pr_url": fake_url}
