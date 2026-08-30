"""Global pytest fixtures.

Every unit test gets a fake LLM AND a fake RAG index by default so the graph
never hits Ollama or downloads the fastembed model. Integration tests marked
with @pytest.mark.integration disable both stubs and use the real deps.

Run integration tests with:  uv run pytest -m integration
"""

from __future__ import annotations

from typing import Any

import pytest

from pipeline_watch import llm as llm_mod
from pipeline_watch import memory as memory_mod
from pipeline_watch import rag as rag_mod
from pipeline_watch.memory import IncidentStore
from pipeline_watch.nodes.synthesize_diagnosis import DiagnosisOutput
from pipeline_watch.rag import Chunk
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
        # Path chosen to sit inside the default PolicyGate allowlist so
        # unit tests exercise the happy autofix path. Adversarial tests
        # override this fake to return a rejected path.
        return ProposedPatch(
            file_path=".github/workflows/ci.yml",
            rationale="Fix trailing whitespace flagged by ruff on the CI workflow.",
            diff=(
                "--- a/.github/workflows/ci.yml\n"
                "+++ b/.github/workflows/ci.yml\n"
                "@@ -3 +3 @@\n"
                "-  runs-on: ubuntu-latest \n"
                "+  runs-on: ubuntu-latest\n"
            ),
        )
    raise TypeError(f"unhandled schema in fake LLM: {schema.__name__}")


class _FakeRunbookIndex:
    """Returns canned chunks based on keyword hits — no embedder, no FAISS."""

    def query(self, text: str, k: int = 3) -> list[Chunk]:
        low = text.lower()
        if "ruff" in low or "e501" in low or "f401" in low:
            return [
                Chunk(
                    source="lint.md",
                    title="Lint failures",
                    heading="Policy",
                    body="Autofix allowed. Never touch business logic. Allowlist paths only.",
                )
            ][:k]
        if "assertionerror" in low or "failed" in low:
            return [
                Chunk(
                    source="test_failures.md",
                    title="Test failures",
                    heading="Policy",
                    body="Never autofix. Always notify PR author.",
                )
            ][:k]
        return [
            Chunk(
                source="external_deps.md",
                title="External dependency failures",
                heading="Policy",
                body="Never autofix code. Notify and consider retry/timeout tuning.",
            )
        ][:k]


@pytest.fixture(autouse=True)
def _stub_llm(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> Any:
    """Autouse: install fake LLM unless the test is marked @pytest.mark.integration."""

    if request.node.get_closest_marker("integration"):
        yield
        return
    monkeypatch.setattr(llm_mod, "structured_output", _fake_structured_output)
    yield


@pytest.fixture(autouse=True)
def _stub_rag(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> Any:
    """Autouse: install fake runbook index unless marked @pytest.mark.integration."""

    if request.node.get_closest_marker("integration"):
        yield
        return
    monkeypatch.setattr(rag_mod, "get_index", lambda: _FakeRunbookIndex())
    yield


@pytest.fixture(autouse=True)
def _isolated_memory(tmp_path, monkeypatch: pytest.MonkeyPatch) -> Any:
    """Give every test a fresh SQLite so history from other tests can't leak in."""

    store = IncidentStore(db_path=tmp_path / "incidents.sqlite")
    monkeypatch.setattr(memory_mod, "get_store", lambda: store)
    yield store


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "integration: hits real Ollama / downloads fastembed; skipped by default"
    )
