"""FastAPI surface for external orchestrators (n8n, cron, ChatOps).

Only read-only endpoints for now. The heavy lifting (triage) stays in the
CLI — the API is a thin adapter over the persisted memory so tools like
n8n can build reports and dashboards without linking against Python code.

Endpoints:
    GET /health            → { "status": "ok" }
    GET /reports/weekly    → aggregated top failure signatures (7 days)
"""

from __future__ import annotations

from fastapi import FastAPI
from pydantic import BaseModel

from pipeline_watch import memory as memory_mod


class SignatureCount(BaseModel):
    error_signature: str
    n: int
    last_seen: str


class WeeklyReport(BaseModel):
    top_signatures: list[SignatureCount]
    total_runs_7d: int


app = FastAPI(title="pipeline_watch", version="0.1.0")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/reports/weekly", response_model=WeeklyReport)
def weekly_report(limit: int = 10) -> WeeklyReport:
    store = memory_mod.get_store()
    rows = store.recent_signatures(limit=limit)
    total = sum(r["n"] for r in rows)
    return WeeklyReport(
        top_signatures=[SignatureCount(**r) for r in rows],
        total_runs_7d=total,
    )
