"""GitHubClient tests: fixture backend, real backend mocked via respx, retries."""

from __future__ import annotations

import httpx
import pytest
import respx

from pipeline_watch.tools.github_client import (
    GitHubClient,
    GitHubClientError,
    Job,
    WorkflowRun,
)

# ---------------------------------------------------------------- fixture --


def test_fixture_get_workflow_run_parses_pydantic():
    client = GitHubClient(mode="fixture")
    run = client.get_workflow_run(repo="ignored", run_id="lint-fixture")
    assert isinstance(run, WorkflowRun)
    assert run.id == 987654321
    assert run.repository.full_name == "j-rdel/pipeline_watch"


def test_fixture_get_jobs_returns_list_of_pydantic_jobs():
    client = GitHubClient(mode="fixture")
    jobs = client.get_jobs(repo="ignored", run_id="lint-fixture")
    assert len(jobs) == 2
    assert all(isinstance(j, Job) for j in jobs)
    assert {j.name for j in jobs} == {"lint", "test"}


def test_fixture_get_job_logs_returns_text():
    client = GitHubClient(mode="fixture")
    logs = client.get_job_logs(repo="ignored", run_id="lint-fixture", job_id=5001)
    assert "E501 Line too long" in logs


def test_fixture_missing_run_raises():
    client = GitHubClient(mode="fixture")
    with pytest.raises(GitHubClientError):
        client.get_workflow_run(repo="ignored", run_id="does-not-exist")


# ------------------------------------------------------------------ real --


def test_github_mode_requires_token():
    with pytest.raises(GitHubClientError):
        GitHubClient(mode="github")


@respx.mock
def test_github_mode_fetches_workflow_run():
    respx.get(
        "https://api.github.com/repos/j-rdel/pipeline_watch/actions/runs/42"
    ).mock(
        return_value=httpx.Response(
            200,
            json={
                "id": 42,
                "name": "ci.yml",
                "head_branch": "main",
                "head_sha": "abc",
                "event": "push",
                "status": "completed",
                "conclusion": "failure",
                "run_started_at": "2026-08-29T10:00:00Z",
                "repository": {"full_name": "j-rdel/pipeline_watch"},
                "jobs_url": "x",
            },
        )
    )

    client = GitHubClient(mode="github", token="ghp_fake")
    run = client.get_workflow_run(repo="j-rdel/pipeline_watch", run_id="42")
    assert run.id == 42


@respx.mock
def test_github_mode_retries_on_5xx_then_succeeds():
    route = respx.get(
        "https://api.github.com/repos/j-rdel/pipeline_watch/actions/runs/42"
    ).mock(
        side_effect=[
            httpx.Response(503),
            httpx.Response(
                200,
                json={
                    "id": 42,
                    "name": "ci.yml",
                    "head_branch": "main",
                    "head_sha": "abc",
                    "event": "push",
                    "status": "completed",
                    "conclusion": "failure",
                    "run_started_at": "2026-08-29T10:00:00Z",
                    "repository": {"full_name": "j-rdel/pipeline_watch"},
                    "jobs_url": "x",
                },
            ),
        ]
    )

    client = GitHubClient(mode="github", token="ghp_fake")
    run = client.get_workflow_run(repo="j-rdel/pipeline_watch", run_id="42")
    assert run.id == 42
    assert route.call_count == 2


@respx.mock
def test_github_mode_gives_up_after_max_attempts():
    respx.get(
        "https://api.github.com/repos/j-rdel/pipeline_watch/actions/runs/42"
    ).mock(return_value=httpx.Response(500))

    client = GitHubClient(mode="github", token="ghp_fake")
    with pytest.raises(httpx.HTTPStatusError):
        client.get_workflow_run(repo="j-rdel/pipeline_watch", run_id="42")
