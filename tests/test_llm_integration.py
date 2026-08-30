"""Integration tests hitting the real Ollama endpoint.

Skipped by default. Run with:  uv run pytest -m integration
Ollama must be reachable at OLLAMA_HOST (default http://localhost:11434) with
the configured model pulled.
"""

from __future__ import annotations

import httpx
import pytest

from pipeline_watch.config import settings
from pipeline_watch.llm import structured_output
from pipeline_watch.prompts import CLASSIFY_SYSTEM
from pipeline_watch.schema import Classification, FailureClass


def _ollama_reachable() -> bool:
    try:
        r = httpx.get(f"{settings.ollama_host}/api/tags", timeout=2.0)
        return r.status_code == 200
    except httpx.HTTPError:
        return False


pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not _ollama_reachable(), reason="Ollama not reachable"),
]


def test_classify_lint_log_produces_lint_label():
    result = structured_output(
        Classification,
        system=CLASSIFY_SYSTEM,
        user=(
            "Repository: j-rdel/pipeline_watch\n"
            "Workflow: ci.yml\nBranch: feat/x\n\n"
            "Failed job logs:\n\n--- lint ---\n"
            "uv run ruff check .\n"
            "src/foo.py:12:81: E501 Line too long (108 > 100)\n"
            "Found 1 error.\nError: Process completed with exit code 1."
        ),
    )
    assert isinstance(result, Classification)
    assert result.label == FailureClass.LINT
    assert 0.0 <= result.confidence <= 1.0
