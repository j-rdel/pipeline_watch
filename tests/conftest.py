"""Global pytest fixtures.

Every unit test gets a fake LLM by default so the graph never hits Ollama.
Integration tests marked with @pytest.mark.integration disable this fixture
and hit the real model. Run them with:  pytest -m integration
"""

from __future__ import annotations

from typing import Any

import pytest

from pipeline_watch import llm as llm_mod
from pipeline_watch.nodes.synthesize_diagnosis import DiagnosisOutput
from pipeline_watch.schema import (
    Classification,
    Evidence,
    FailureClass,
    ProposedPatch,
    Severity,
)


def _fake_structured_output(schema, *, system: str, user: str):  # noqa: ANN001
    """Return a canned instance for each schema type our nodes ask for.

    The exact content is chosen so scenario-based tests still pass:
    - lint-fixture logs contain "E501" → classify returns LINT
    - test-fixture logs contain "AssertionError" → classify returns TEST_FAILURE
    """

    if schema is Classification:
        if "AssertionError" in user or "FAILED" in user:
            return Classification(
                label=FailureClass.TEST_FAILURE,
                confidence=0.85,
                reasoning="Log shows AssertionError from pytest.",
            )
        return Classification(
            label=FailureClass.LINT,
            confidence=0.9,
            reasoning="Log mentions ruff E501 line-length violation.",
        )
    if schema is DiagnosisOutput:
        if "test-failure" in user.lower():
            return DiagnosisOutput(
                root_cause_hypothesis="Regression in apply_discounts stacking two coupons.",
                evidence=[
                    Evidence(
                        source="job:test/logs",
                        excerpt="AssertionError: assert 90 == 80",
                    )
                ],
                severity=Severity.HIGH,
                suggested_action="Revert discount stacking change in pricing.py.",
            )
        return DiagnosisOutput(
            root_cause_hypothesis="ruff E501 line-length violation in foo.py:12.",
            evidence=[
                Evidence(
                    source="job:lint/logs",
                    excerpt="src/pipeline_watch/foo.py:12:81: E501 Line too long (108 > 100)",
                    line_hint=12,
                )
            ],
            severity=Severity.LOW,
            suggested_action="Run `ruff format` on foo.py and commit.",
        )
    if schema is ProposedPatch:
        return ProposedPatch(
            file_path="src/pipeline_watch/foo.py",
            rationale="Fix ruff E501 by wrapping the long expression.",
            diff=(
                "--- a/src/pipeline_watch/foo.py\n"
                "+++ b/src/pipeline_watch/foo.py\n"
                "@@ -10,3 +10,4 @@\n"
                " def something():\n"
                "-    result = some_very_long(a, b, c, d, e, f)\n"
                "+    result = some_very_long(\n"
                "+        a, b, c, d, e, f\n"
                "+    )\n"
            ),
        )
    raise TypeError(f"unhandled schema in fake LLM: {schema.__name__}")


@pytest.fixture(autouse=True)
def _stub_llm(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> Any:
    """Autouse: install fake LLM unless the test is marked @pytest.mark.integration."""

    if request.node.get_closest_marker("integration"):
        yield
        return
    monkeypatch.setattr(llm_mod, "structured_output", _fake_structured_output)
    yield


def pytest_configure(config):
    config.addinivalue_line("markers", "integration: hits real Ollama; skipped by default")
