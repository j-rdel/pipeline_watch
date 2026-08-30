"""notify_discord — notify-only path terminal side-effect.

Stub: fabricates a message id. Real impl (task #10) posts to a Discord
webhook (dry-run default).
"""

from __future__ import annotations

from pipeline_watch.state import TriageState


def notify_discord(state: TriageState) -> dict:
    return {"discord_message_id": "stub-msg-0001"}
