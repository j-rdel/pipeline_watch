"""Long-term memory: SQLite table of past triage runs.

Two responsibilities:
  1. persist each IncidentReport as a row (called by persist_incident node)
  2. answer "how often did we see the same signature in the last N days?"
     (called by estimate_flakiness node)

An "error signature" is the first strong error token we can extract from the
failing job logs — e.g. `ruff:E501`, `pytest:AssertionError`,
`http:503`. Same signature = "same failure" for flakiness purposes. This is
intentionally coarse: better a few false positives on flakiness than to miss
a repeating flake by keying on the full traceback.
"""

from __future__ import annotations

import re
import sqlite3
from contextlib import closing
from datetime import UTC, datetime, timedelta
from pathlib import Path

_DEFAULT_DB_PATH = Path(__file__).resolve().parents[2] / ".cache" / "incidents.sqlite"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS incidents (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id            TEXT NOT NULL,
    workflow          TEXT NOT NULL,
    job_name          TEXT NOT NULL,
    error_signature   TEXT NOT NULL,
    timestamp         TEXT NOT NULL,      -- ISO 8601 UTC
    outcome           TEXT NOT NULL,      -- 'autofix' | 'notify_only'
    decision          TEXT NOT NULL       -- copy of the state.decision at persist time
);

CREATE INDEX IF NOT EXISTS ix_incidents_signature_ts
    ON incidents (error_signature, timestamp);
CREATE INDEX IF NOT EXISTS ix_incidents_workflow_ts
    ON incidents (workflow, timestamp);
"""


# ------------------------------------------------------ signature parsing --

# Ordered: first match wins. Broad enough to cover our runbook categories.
_SIGNATURE_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("ruff", re.compile(r"\b([EFW]\d{3,4})\b")),                       # E501, F401
    ("pytest", re.compile(r"\b(AssertionError|Fixture\w*Error)\b")),
    ("py", re.compile(r"\b([A-Z][a-zA-Z]+Error)\b")),                  # TypeError etc.
    ("http", re.compile(r"\b(HTTP\s?\d{3}|5\d{2}|4\d{2}\b)")),         # HTTP 503, 500
    ("build", re.compile(r"\b(ModuleNotFoundError|ImportError|BuildError)\b")),
    ("timeout", re.compile(r"\b(TimeoutError|read timeout|Timed out)\b", re.IGNORECASE)),
]


def signature_from_logs(logs: str) -> str:
    """Best-effort extraction of a stable failure signature.

    Returns 'unknown' if no pattern matches. Signature format is `family:token`
    (e.g. 'ruff:E501', 'pytest:AssertionError', 'http:503').
    """

    for family, pattern in _SIGNATURE_PATTERNS:
        m = pattern.search(logs)
        if m:
            return f"{family}:{m.group(1).strip()}"
    return "unknown"


# ------------------------------------------------------------ persistence --


class IncidentStore:
    """Thin sqlite3 wrapper. All calls are synchronous (SQLite is fast enough)."""

    def __init__(self, db_path: Path = _DEFAULT_DB_PATH) -> None:
        self.db_path = db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as con:
            con.executescript(_SCHEMA)
            con.commit()

    def _connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.db_path)
        con.row_factory = sqlite3.Row
        return con

    # ----- writes --------------------------------------------------------

    def record(
        self,
        *,
        run_id: str,
        workflow: str,
        job_name: str,
        error_signature: str,
        outcome: str,
        decision: str,
        when: datetime | None = None,
    ) -> None:
        ts = (when or datetime.now(UTC)).isoformat()
        with closing(self._connect()) as con:
            con.execute(
                "INSERT INTO incidents "
                "(run_id, workflow, job_name, error_signature, timestamp, outcome, decision) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (run_id, workflow, job_name, error_signature, ts, outcome, decision),
            )
            con.commit()

    # ----- reads ---------------------------------------------------------

    def count_similar(self, error_signature: str, within_days: int = 7) -> int:
        """Rows with the same signature in the last `within_days` days."""

        cutoff = (datetime.now(UTC) - timedelta(days=within_days)).isoformat()
        with closing(self._connect()) as con:
            row = con.execute(
                "SELECT COUNT(*) AS n FROM incidents "
                "WHERE error_signature = ? AND timestamp >= ?",
                (error_signature, cutoff),
            ).fetchone()
        return int(row["n"])

    def count_runs(self, workflow: str, within_days: int = 7) -> int:
        cutoff = (datetime.now(UTC) - timedelta(days=within_days)).isoformat()
        with closing(self._connect()) as con:
            row = con.execute(
                "SELECT COUNT(*) AS n FROM incidents "
                "WHERE workflow = ? AND timestamp >= ?",
                (workflow, cutoff),
            ).fetchone()
        return int(row["n"])

    def recent_signatures(self, limit: int = 10) -> list[dict]:
        """Used by the /reports/weekly endpoint the n8n flow will hit."""

        with closing(self._connect()) as con:
            rows = con.execute(
                "SELECT error_signature, COUNT(*) AS n, MAX(timestamp) AS last_seen "
                "FROM incidents "
                "WHERE timestamp >= date('now', '-7 days') "
                "GROUP BY error_signature "
                "ORDER BY n DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]


_singleton: IncidentStore | None = None


def get_store() -> IncidentStore:
    global _singleton
    if _singleton is None:
        _singleton = IncidentStore()
    return _singleton


def reset_singleton() -> None:
    """Used by tests."""

    global _singleton
    _singleton = None
