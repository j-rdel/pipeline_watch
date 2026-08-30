"""Unit tests for memory.py — signature parsing + IncidentStore CRUD."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from pipeline_watch.memory import IncidentStore, signature_from_logs

# ------------------------------------------------------- signatures --


def test_signature_ruff_lint():
    assert signature_from_logs("src/foo.py:12:81: E501 Line too long") == "ruff:E501"


def test_signature_pytest_assertion():
    logs = "tests/test_x.py::test_y FAILED\nAssertionError: 1 != 2"
    assert signature_from_logs(logs) == "pytest:AssertionError"


def test_signature_python_error():
    assert signature_from_logs("TypeError: expected str, got int") == "py:TypeError"


def test_signature_http_5xx():
    assert signature_from_logs("HTTP 503 upstream unavailable") == "http:HTTP 503"


def test_signature_timeout():
    assert signature_from_logs("read timeout after 30s") == "timeout:read timeout"


def test_signature_unknown_returns_sentinel():
    assert signature_from_logs("everything green") == "unknown"


def test_signature_first_match_wins():
    # ruff pattern comes first in the ordered list
    logs = "AssertionError happened but also E501 in the same log"
    assert signature_from_logs(logs) == "ruff:E501"


# --------------------------------------------------------- store ---


def _fresh(tmp_path: Path) -> IncidentStore:
    return IncidentStore(db_path=tmp_path / "db.sqlite")


def test_record_and_count_similar(tmp_path: Path):
    s = _fresh(tmp_path)
    for _ in range(3):
        s.record(
            run_id="r", workflow="ci", job_name="lint",
            error_signature="ruff:E501", outcome="autofix", decision="autofix",
        )
    assert s.count_similar("ruff:E501") == 3
    assert s.count_similar("ruff:F401") == 0


def test_count_similar_respects_7_day_window(tmp_path: Path):
    s = _fresh(tmp_path)
    old = datetime.now(UTC) - timedelta(days=10)
    s.record(
        run_id="r", workflow="ci", job_name="lint",
        error_signature="sig", outcome="autofix", decision="autofix",
        when=old,
    )
    s.record(
        run_id="r", workflow="ci", job_name="lint",
        error_signature="sig", outcome="autofix", decision="autofix",
    )
    assert s.count_similar("sig", within_days=7) == 1


def test_count_runs_per_workflow(tmp_path: Path):
    s = _fresh(tmp_path)
    for wf in ["ci", "ci", "release"]:
        s.record(
            run_id="r", workflow=wf, job_name="j",
            error_signature="x", outcome="autofix", decision="autofix",
        )
    assert s.count_runs("ci") == 2
    assert s.count_runs("release") == 1


def test_recent_signatures_grouped_and_ranked(tmp_path: Path):
    s = _fresh(tmp_path)
    for _ in range(3):
        s.record(run_id="r", workflow="ci", job_name="j",
                 error_signature="ruff:E501", outcome="autofix", decision="autofix")
    for _ in range(1):
        s.record(run_id="r", workflow="ci", job_name="j",
                 error_signature="pytest:AssertionError",
                 outcome="notify_only", decision="notify_only")
    top = s.recent_signatures(limit=5)
    assert top[0]["error_signature"] == "ruff:E501"
    assert top[0]["n"] == 3
