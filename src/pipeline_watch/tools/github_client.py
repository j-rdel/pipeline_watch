"""GitHub REST client for reading workflow runs, jobs and job logs.

Two backends, selected by the `mode` constructor arg:

- **"github"**: real HTTP calls against api.github.com, authenticated by
  the token passed in. Uses tenacity for retry-with-jittered-backoff on 5xx
  and network errors; individual calls have a 10 s timeout.

- **"fixture"**: reads from `fixtures/workflow_runs/{run_id}.json`,
  `fixtures/workflow_runs/{run_id}_jobs.json`, and
  `fixtures/logs/{run_id}_{job_id}.log`. Same Pydantic parsing path as the
  real backend, so bugs in the schema surface either way.

Only *read* operations live here. Write operations (open_pr) go through a
separate module that is gated by the PolicyGate (task #8/#10).
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import httpx
from pydantic import BaseModel, Field
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

_GITHUB_API = "https://api.github.com"
_TIMEOUT_SECONDS = 10.0
_FIXTURES_ROOT = Path(__file__).resolve().parents[3] / "fixtures"


class GitHubClientError(RuntimeError):
    """Raised when the client cannot serve a request (misconfiguration, bad payload)."""


class _Repository(BaseModel):
    full_name: str


class WorkflowRun(BaseModel):
    """Subset of GitHub's workflow_run payload that the agent actually consumes."""

    id: int
    name: str
    head_branch: str
    head_sha: str
    event: str
    status: str
    conclusion: str
    run_started_at: str
    repository: _Repository
    jobs_url: str


class Job(BaseModel):
    id: int
    name: str
    conclusion: str
    status: str
    started_at: str
    completed_at: str | None = None


class _JobsPayload(BaseModel):
    total_count: int
    jobs: list[Job] = Field(default_factory=list)


class GitHubClient:
    """Thin, typed wrapper over the GitHub REST API — or fixture files."""

    def __init__(
        self,
        mode: Literal["github", "fixture"] = "fixture",
        token: str | None = None,
        fixtures_root: Path | None = None,
    ) -> None:
        self.mode = mode
        self._token = token
        self._fixtures_root = fixtures_root or _FIXTURES_ROOT
        if mode == "github" and not token:
            raise GitHubClientError("github mode requires a token")

    # ---------------------------------------------------------------- public --

    def get_workflow_run(self, repo: str, run_id: str) -> WorkflowRun:
        if self.mode == "fixture":
            return self._read_fixture_workflow_run(run_id)
        return self._fetch_workflow_run(repo, run_id)

    def get_jobs(self, repo: str, run_id: str) -> list[Job]:
        if self.mode == "fixture":
            return self._read_fixture_jobs(run_id)
        return self._fetch_jobs(repo, run_id)

    def get_job_logs(self, repo: str, run_id: str, job_id: int) -> str:
        if self.mode == "fixture":
            return self._read_fixture_logs(run_id, job_id)
        return self._fetch_job_logs(repo, job_id)

    # -------------------------------------------------------------- fixtures --

    def _read_fixture_workflow_run(self, run_id: str) -> WorkflowRun:
        path = self._fixtures_root / "workflow_runs" / f"{run_id}.json"
        if not path.exists():
            raise GitHubClientError(f"fixture not found: {path}")
        return WorkflowRun.model_validate_json(path.read_text(encoding="utf-8"))

    def _read_fixture_jobs(self, run_id: str) -> list[Job]:
        path = self._fixtures_root / "workflow_runs" / f"{run_id}_jobs.json"
        if not path.exists():
            raise GitHubClientError(f"fixture not found: {path}")
        payload = _JobsPayload.model_validate_json(path.read_text(encoding="utf-8"))
        return payload.jobs

    def _read_fixture_logs(self, run_id: str, job_id: int) -> str:
        path = self._fixtures_root / "logs" / f"{run_id}_{job_id}.log"
        if not path.exists():
            raise GitHubClientError(f"fixture not found: {path}")
        return path.read_text(encoding="utf-8")

    # ------------------------------------------------------------------ real --

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential_jitter(initial=0.5, max=4.0),
        retry=retry_if_exception_type((httpx.TransportError, httpx.HTTPStatusError)),
        reraise=True,
    )
    def _fetch_workflow_run(self, repo: str, run_id: str) -> WorkflowRun:
        url = f"{_GITHUB_API}/repos/{repo}/actions/runs/{run_id}"
        with httpx.Client(timeout=_TIMEOUT_SECONDS, headers=self._headers()) as client:
            resp = client.get(url)
            resp.raise_for_status()
            return WorkflowRun.model_validate(resp.json())

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential_jitter(initial=0.5, max=4.0),
        retry=retry_if_exception_type((httpx.TransportError, httpx.HTTPStatusError)),
        reraise=True,
    )
    def _fetch_jobs(self, repo: str, run_id: str) -> list[Job]:
        url = f"{_GITHUB_API}/repos/{repo}/actions/runs/{run_id}/jobs"
        with httpx.Client(timeout=_TIMEOUT_SECONDS, headers=self._headers()) as client:
            resp = client.get(url)
            resp.raise_for_status()
            return _JobsPayload.model_validate(resp.json()).jobs

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential_jitter(initial=0.5, max=4.0),
        retry=retry_if_exception_type((httpx.TransportError, httpx.HTTPStatusError)),
        reraise=True,
    )
    def _fetch_job_logs(self, repo: str, job_id: int) -> str:
        url = f"{_GITHUB_API}/repos/{repo}/actions/jobs/{job_id}/logs"
        with httpx.Client(
            timeout=_TIMEOUT_SECONDS,
            headers=self._headers(),
            follow_redirects=True,
        ) as client:
            resp = client.get(url)
            resp.raise_for_status()
            return resp.text

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }


__all__ = [
    "GitHubClient",
    "GitHubClientError",
    "Job",
    "WorkflowRun",
]
