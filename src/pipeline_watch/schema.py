"""Pydantic schemas used across the pipeline_watch agent.

These are the *contract* types: they describe what nodes exchange, what the
LLM must return via structured output, and what the CLI/API surface to the
outside world. Keep them small and stable — they are the boundary.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class FailureClass(StrEnum):
    LINT = "lint"
    TEST_FAILURE = "test-failure"
    TEST_FLAKY = "test-flaky"
    BUILD = "build"
    DEPLOY = "deploy"
    EXTERNAL_DEP = "external-dep"
    CONFIG = "config"
    UNKNOWN = "unknown"


class Severity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Evidence(BaseModel):
    """A single citation from the CI log or metadata that supports the diagnosis.

    Every claim in the report should be backed by at least one Evidence entry;
    that's the mechanism that lets a reviewer audit the LLM's conclusion.
    """

    source: str = Field(
        description="Origin of the evidence, e.g. 'job:test/logs' or 'metadata:duration'.",
    )
    excerpt: str = Field(
        description="Verbatim snippet from the log, truncated to <= 400 chars.",
        max_length=400,
    )
    line_hint: int | None = Field(
        default=None,
        description="1-based line number in the source, if available.",
    )


class Classification(BaseModel):
    """Output of the classify_failure LLM node."""

    label: FailureClass
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str = Field(
        description="Short justification, one to three sentences.",
        max_length=600,
    )


class FlakinessScore(BaseModel):
    """Output of the estimate_flakiness deterministic node."""

    score: float = Field(ge=0.0, le=1.0, description="failures_with_same_signature / runs_last_7d")
    similar_failures_7d: int = Field(ge=0)
    total_runs_7d: int = Field(ge=0)
    is_flaky: bool = Field(description="True when score > 0.4 AND similar_failures_7d >= 2.")


class ProposedPatch(BaseModel):
    """A minimal patch proposal the LLM emits when autofix looks safe.

    The PolicyGate is the last line of defense: even if this model is populated,
    the PR is only opened when every touched path is on PW_ALLOWLIST_PATHS.
    """

    file_path: str = Field(description="Path relative to repo root.")
    rationale: str = Field(max_length=400)
    diff: str = Field(description="Unified diff snippet to apply.", max_length=4000)


class IncidentReport(BaseModel):
    """Top-level output of a triage run — persisted and posted to Discord.

    This is the *single* structured artifact the agent produces per run_id.
    The Discord post is a rendering of this; the SQLite row is a serialization
    of this; the PR body (if opened) links back to this.
    """

    run_id: str
    workflow: str
    repository: str
    started_at: datetime
    finished_at: datetime | None = None

    classification: Classification
    flakiness: FlakinessScore
    root_cause_hypothesis: str = Field(max_length=1000)
    evidence: list[Evidence] = Field(default_factory=list, min_length=1)

    suggested_action: str = Field(max_length=600)
    severity: Severity
    proposed_patch: ProposedPatch | None = None
    human_approval_required: bool = Field(
        description="True when the flow decided not to autofix — either policy-blocked "
        "or LLM confidence too low.",
    )

    correlation_id: str = Field(
        description="Same value used in structlog run_id and OTel trace_id.",
    )
