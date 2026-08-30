"""Smoke tests for schema.py — validate constraints and enum wiring."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from pipeline_watch.schema import (
    Classification,
    Evidence,
    FailureClass,
    FlakinessScore,
    IncidentReport,
    ProposedPatch,
    Severity,
)


def _minimal_report(**overrides) -> IncidentReport:
    defaults = dict(
        run_id="42",
        workflow="ci.yml",
        repository="j-rdel/pipeline_watch",
        started_at=datetime(2026, 1, 1, tzinfo=UTC),
        classification=Classification(
            label=FailureClass.LINT, confidence=0.9, reasoning="ruff E501"
        ),
        flakiness=FlakinessScore(
            score=0.0, similar_failures_7d=0, total_runs_7d=10, is_flaky=False
        ),
        root_cause_hypothesis="line too long in foo.py:12",
        evidence=[Evidence(source="job:lint/logs", excerpt="E501 line too long")],
        suggested_action="run `ruff format` and commit",
        severity=Severity.LOW,
        human_approval_required=False,
        correlation_id="run-42-abcd",
    )
    return IncidentReport(**{**defaults, **overrides})


def test_report_roundtrip():
    report = _minimal_report()
    dumped = report.model_dump_json()
    reloaded = IncidentReport.model_validate_json(dumped)
    assert reloaded == report


def test_evidence_excerpt_capped():
    with pytest.raises(ValidationError):
        Evidence(source="x", excerpt="a" * 401)


def test_classification_confidence_bounds():
    with pytest.raises(ValidationError):
        Classification(label=FailureClass.LINT, confidence=1.5, reasoning="nope")


def test_flakiness_score_bounds():
    with pytest.raises(ValidationError):
        FlakinessScore(score=1.2, similar_failures_7d=0, total_runs_7d=1, is_flaky=False)


def test_report_requires_evidence():
    with pytest.raises(ValidationError):
        _minimal_report(evidence=[])


def test_proposed_patch_diff_capped():
    with pytest.raises(ValidationError):
        ProposedPatch(file_path="a.py", rationale="x", diff="d" * 4001)


def test_report_optional_patch_defaults_none():
    report = _minimal_report()
    assert report.proposed_patch is None
