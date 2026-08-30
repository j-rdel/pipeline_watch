"""RAG integration test — builds the real index over docs/runbook/ and
queries it. Downloads the fastembed model on first run (~90 MB). Skipped
by default; run with:  uv run pytest -m integration
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pipeline_watch.rag import RunbookIndex

pytestmark = pytest.mark.integration


def test_real_runbook_query_ranks_lint_topic_first_for_ruff_input(tmp_path: Path):
    ix = RunbookIndex(
        runbook_dir=Path(__file__).resolve().parents[1] / "docs" / "runbook",
        index_path=tmp_path / "runbook.faiss",
    ).load_or_build()

    results = ix.query("ruff reported E501 line too long in foo.py", k=3)

    assert results, "no results returned"
    top = results[0]
    assert top.source == "lint.md", f"expected lint.md at rank 1, got {top.source}"


def test_real_runbook_query_ranks_test_topic_first_for_assertion(tmp_path: Path):
    ix = RunbookIndex(
        runbook_dir=Path(__file__).resolve().parents[1] / "docs" / "runbook",
        index_path=tmp_path / "runbook.faiss",
    ).load_or_build()

    results = ix.query(
        "pytest failed with AssertionError in tests/test_pricing.py", k=3
    )
    top = results[0]
    assert top.source == "test_failures.md", (
        f"expected test_failures.md at rank 1, got {top.source}"
    )
