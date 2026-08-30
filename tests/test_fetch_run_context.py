"""Tests for the fetch_run_context node using the real GitHubClient (fixture backend)."""

from __future__ import annotations

import pytest

from pipeline_watch.nodes.fetch_run_context import fetch_run_context
from pipeline_watch.tools.github_client import GitHubClientError


def test_fetch_run_context_lint_fixture_returns_only_failed_jobs():
    state = {"run_id": "lint-fixture", "source": "fixture", "correlation_id": "c"}
    result = fetch_run_context(state)  # type: ignore[arg-type]
    ctx = result["context"]

    assert ctx["run_id"] == "lint-fixture"
    assert ctx["repository"] == "j-rdel/pipeline_watch"
    assert ctx["conclusion"] == "failure"
    assert len(ctx["failed_jobs"]) == 1, "must skip jobs that succeeded"
    assert ctx["failed_jobs"][0]["name"] == "lint"
    assert "E501" in ctx["failed_jobs"][0]["logs"]


def test_fetch_run_context_test_fixture_returns_failed_test_job():
    state = {"run_id": "test-fixture", "source": "fixture", "correlation_id": "c"}
    result = fetch_run_context(state)  # type: ignore[arg-type]
    failed = result["context"]["failed_jobs"]
    assert len(failed) == 1
    assert failed[0]["name"] == "test"
    assert "AssertionError" in failed[0]["logs"]


def test_fetch_run_context_github_source_without_token_errors():
    state = {"run_id": "42", "source": "github", "correlation_id": "c"}
    with pytest.raises(GitHubClientError):
        fetch_run_context(state)  # type: ignore[arg-type]


def test_fetch_run_context_unknown_fixture_errors():
    state = {"run_id": "unknown", "source": "fixture", "correlation_id": "c"}
    with pytest.raises(GitHubClientError):
        fetch_run_context(state)  # type: ignore[arg-type]
