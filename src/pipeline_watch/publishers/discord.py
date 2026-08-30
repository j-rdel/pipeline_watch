"""Discord publisher — turns an IncidentReport into a webhook embed message.

Behaviour matrix:
- PW_DRY_RUN=true (default) or no DISCORD_WEBHOOK_URL → build payload, log it,
  return None (nothing sent).
- PW_DRY_RUN=false AND webhook set → POST the payload, return the string
  'sent' on 2xx. Any 4xx/5xx bubbles up via tenacity retry then httpx error.

Payload format is intentionally a Discord *embed* (not raw content) so the
severity color, fields, and footer render nicely in the channel.
"""

from __future__ import annotations

import os

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from pipeline_watch.config import settings
from pipeline_watch.observability import get_logger
from pipeline_watch.schema import IncidentReport, Severity

_TIMEOUT_SECONDS = 8.0
_SEVERITY_COLOR = {
    Severity.LOW: 0x2ECC71,      # green
    Severity.MEDIUM: 0xF1C40F,   # yellow
    Severity.HIGH: 0xE67E22,     # orange
    Severity.CRITICAL: 0xE74C3C, # red
}


class DiscordPublisher:
    def __init__(self, webhook_url: str | None = None, dry_run: bool | None = None) -> None:
        self.webhook_url = webhook_url if webhook_url is not None else os.environ.get(
            "DISCORD_WEBHOOK_URL", ""
        )
        self.dry_run = settings.pw_dry_run if dry_run is None else dry_run
        self._log = get_logger("pipeline_watch.publishers.discord")

    def _build_payload(self, report: IncidentReport) -> dict:
        if report.human_approval_required:
            title_prefix = "CI failure — human review needed"
        else:
            title_prefix = "Autofix PR proposed"

        cls_value = (
            f"{report.classification.label} "
            f"(conf {report.classification.confidence:.2f})"
        )
        flake_value = (
            f"score={report.flakiness.score:.2f} "
            f"({report.flakiness.similar_failures_7d} similar / "
            f"{report.flakiness.total_runs_7d} runs 7d)"
        )
        fields = [
            {"name": "Classification", "value": cls_value, "inline": True},
            {"name": "Severity", "value": report.severity.value, "inline": True},
            {"name": "Flakiness", "value": flake_value, "inline": False},
            {
                "name": "Hypothesis",
                "value": report.root_cause_hypothesis[:1000],
                "inline": False,
            },
            {
                "name": "Suggested action",
                "value": report.suggested_action[:600],
                "inline": False,
            },
        ]
        if report.proposed_patch:
            fields.append(
                {
                    "name": "Proposed patch",
                    "value": (
                        f"file: `{report.proposed_patch.file_path}`\n"
                        f"{report.proposed_patch.rationale[:300]}"
                    ),
                    "inline": False,
                }
            )

        footer_text = (
            f"correlation_id={report.correlation_id} · run_id={report.run_id}"
        )
        return {
            "embeds": [
                {
                    "title": f"{title_prefix} — {report.workflow} @ {report.repository}",
                    "color": _SEVERITY_COLOR.get(report.severity, 0x95A5A6),
                    "fields": fields,
                    "footer": {"text": footer_text},
                }
            ]
        }

    def publish(self, report: IncidentReport) -> str | None:
        payload = self._build_payload(report)

        if self.dry_run or not self.webhook_url:
            self._log.info(
                "discord.publish.dry_run",
                webhook_configured=bool(self.webhook_url),
                dry_run=self.dry_run,
                embed_title=payload["embeds"][0]["title"],
            )
            return None

        self._log.info("discord.publish.send", embed_title=payload["embeds"][0]["title"])
        _post(self.webhook_url, payload)
        return "sent"


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential_jitter(initial=0.5, max=4.0),
    retry=retry_if_exception_type((httpx.TransportError, httpx.HTTPStatusError)),
    reraise=True,
)
def _post(webhook_url: str, payload: dict) -> None:
    with httpx.Client(timeout=_TIMEOUT_SECONDS) as client:
        resp = client.post(webhook_url, json=payload)
        resp.raise_for_status()
