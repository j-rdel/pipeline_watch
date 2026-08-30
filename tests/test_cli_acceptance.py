"""Acceptance test — runs the CLI as a real subprocess against a fixture.

Full stack: CLI → LangGraph → Ollama → fastembed → SQLite → publishers.

Slow (~60-120s depending on the model). Marked integration; run with:
  uv run pytest -m integration tests/test_cli_acceptance.py

Contract:
- exit code 0 for a well-known fixture
- stdout ends with a valid IncidentReport JSON
- correlation_id follows the `run-<id>-<uuid8>` shape
"""

from __future__ import annotations

import json
import os
import subprocess

import pytest


@pytest.mark.integration
def test_cli_lint_fixture_returns_valid_incident_report():
    result = subprocess.run(
        ["uv", "run", "pipeline_watch", "triage", "--run-id", "lint-fixture"],
        capture_output=True,
        text=True,
        timeout=240,
        env={**os.environ, "PW_LOG_LEVEL": "WARNING"},
    )
    assert result.returncode == 0, f"stderr:\n{result.stderr}"

    # The final JSON object dumped to stdout is the report. Slice from the
    # first '{' at column 0 to the end.
    lines = result.stdout.splitlines()
    json_start = next(
        i for i, ln in enumerate(lines) if ln.startswith("{")
    )
    report = json.loads("\n".join(lines[json_start:]))

    assert report["run_id"] == "lint-fixture"
    assert report["workflow"] == "ci.yml"
    assert "classification" in report and "flakiness" in report
    assert report["correlation_id"].startswith("run-lint-fixture-")
