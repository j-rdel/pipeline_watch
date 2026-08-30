"""Tests for DiscordPublisher and GitHubPRPublisher."""

from __future__ import annotations

from datetime import UTC, datetime

import httpx
import pytest
import respx

from pipeline_watch.publishers.discord import DiscordPublisher
from pipeline_watch.publishers.github_pr import GitHubPRPublisher
from pipeline_watch.schema import (
    Classification,
    Evidence,
    FailureClass,
    FlakinessScore,
    IncidentReport,
    ProposedPatch,
    Severity,
)


def _report(**overrides) -> IncidentReport:
    defaults = dict(
        run_id="42",
        workflow="ci.yml",
        repository="j-rdel/pipeline_watch",
        started_at=datetime(2026, 1, 1, tzinfo=UTC),
        classification=Classification(
            label=FailureClass.LINT, confidence=0.9, reasoning="E501"
        ),
        flakiness=FlakinessScore(
            score=0.0, similar_failures_7d=0, total_runs_7d=1, is_flaky=False
        ),
        root_cause_hypothesis="line too long",
        evidence=[Evidence(source="job:lint", excerpt="E501")],
        suggested_action="run ruff format",
        severity=Severity.LOW,
        proposed_patch=ProposedPatch(
            file_path=".github/workflows/ci.yml",
            rationale="whitespace",
            diff="--- a/x\n+++ b/x\n",
        ),
        human_approval_required=False,
        correlation_id="cid-1",
    )
    defaults.update(overrides)
    return IncidentReport(**defaults)


# ------------------------------------------------------------- discord --


def test_discord_dry_run_returns_none_and_does_not_call_http():
    pub = DiscordPublisher(webhook_url="", dry_run=True)
    assert pub.publish(_report()) is None


def test_discord_no_webhook_falls_back_to_dry_run():
    pub = DiscordPublisher(webhook_url="", dry_run=False)
    assert pub.publish(_report()) is None


@respx.mock
def test_discord_real_mode_posts_to_webhook():
    route = respx.post("https://discord.example/webhook/xyz").mock(
        return_value=httpx.Response(204)
    )
    pub = DiscordPublisher(webhook_url="https://discord.example/webhook/xyz", dry_run=False)
    assert pub.publish(_report()) == "sent"
    assert route.called
    body = route.calls.last.request.content.decode()
    assert "correlation_id=cid-1" in body
    assert "j-rdel/pipeline_watch" in body


@respx.mock
def test_discord_retries_on_5xx_then_succeeds():
    route = respx.post("https://discord.example/webhook/xyz").mock(
        side_effect=[httpx.Response(503), httpx.Response(204)]
    )
    pub = DiscordPublisher(webhook_url="https://discord.example/webhook/xyz", dry_run=False)
    assert pub.publish(_report()) == "sent"
    assert route.call_count == 2


@respx.mock
def test_discord_raises_after_max_attempts():
    respx.post("https://discord.example/webhook/xyz").mock(
        return_value=httpx.Response(500)
    )
    pub = DiscordPublisher(webhook_url="https://discord.example/webhook/xyz", dry_run=False)
    with pytest.raises(httpx.HTTPStatusError):
        pub.publish(_report())


def test_discord_embed_reflects_severity_color():
    pub = DiscordPublisher(webhook_url="x", dry_run=True)
    payload = pub._build_payload(_report(severity=Severity.CRITICAL))  # noqa: SLF001
    assert payload["embeds"][0]["color"] == 0xE74C3C


def test_discord_embed_titles_differ_by_approval_required():
    pub = DiscordPublisher(webhook_url="x", dry_run=True)
    autofix = pub._build_payload(_report(human_approval_required=False))  # noqa: SLF001
    notify = pub._build_payload(_report(human_approval_required=True))  # noqa: SLF001
    assert "Autofix" in autofix["embeds"][0]["title"]
    assert "human review" in notify["embeds"][0]["title"]


# ------------------------------------------------------ github pr --


def test_github_pr_returns_none_in_dry_run_and_never_posts(respx_mock):
    # Any HTTP call would be an unexpected side effect; respx will error.
    pub = GitHubPRPublisher(dry_run=True)
    assert pub.open_pr(_report()) is None


def test_github_pr_returns_none_when_patch_missing():
    pub = GitHubPRPublisher(dry_run=True)
    assert pub.open_pr(_report(proposed_patch=None)) is None


def test_github_pr_payload_includes_diff_and_correlation():
    pub = GitHubPRPublisher(dry_run=True)
    payload = pub._build_payload(_report())  # noqa: SLF001
    assert "cid-1" in payload["body"]
    assert ".github/workflows/ci.yml" in payload["file_path"]
    assert "```diff" in payload["body"]
