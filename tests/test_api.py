"""FastAPI endpoints — smoke tests via TestClient."""

from __future__ import annotations

from fastapi.testclient import TestClient

from pipeline_watch.api import app


def test_health_returns_ok():
    with TestClient(app) as client:
        r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_weekly_report_empty_store(_isolated_memory):
    with TestClient(app) as client:
        r = client.get("/reports/weekly")
    assert r.status_code == 200
    payload = r.json()
    assert payload["top_signatures"] == []
    assert payload["total_runs_7d"] == 0


def test_weekly_report_aggregates_signatures(_isolated_memory):
    store = _isolated_memory
    for sig, times in [("ruff:E501", 3), ("pytest:AssertionError", 2), ("http:503", 4)]:
        for _ in range(times):
            store.record(
                run_id="r", workflow="ci", job_name="j",
                error_signature=sig, outcome="notify_only", decision="notify_only",
            )
    with TestClient(app) as client:
        r = client.get("/reports/weekly?limit=5")
    assert r.status_code == 200
    payload = r.json()
    top = {s["error_signature"]: s["n"] for s in payload["top_signatures"]}
    assert top == {"ruff:E501": 3, "pytest:AssertionError": 2, "http:503": 4}
    assert payload["total_runs_7d"] == 9
