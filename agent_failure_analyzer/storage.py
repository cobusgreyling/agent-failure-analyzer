"""
SQLite storage for persisting analysis results and tracking trends.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from .models import AnalysisResult, BatchAnalysisResult
from .reports.json_report import JSONReporter

DEFAULT_DB_PATH = Path.home() / ".afa" / "history.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS analysis_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    framework TEXT,
    model TEXT,
    outcome TEXT,
    risk_score REAL,
    failure_count INTEGER,
    total_tokens INTEGER,
    total_turns INTEGER,
    event_count INTEGER,
    category_summary TEXT,
    severity_summary TEXT,
    failures_json TEXT,
    source_file TEXT,
    analyzed_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_analyzed_at ON analysis_runs(analyzed_at);
CREATE INDEX IF NOT EXISTS idx_session_id ON analysis_runs(session_id);
CREATE INDEX IF NOT EXISTS idx_framework ON analysis_runs(framework);
"""


class AnalysisStore:
    """Persist and query analysis results in SQLite."""

    def __init__(self, db_path: Path | str | None = None) -> None:
        self.db_path = Path(db_path) if db_path else DEFAULT_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: sqlite3.Connection | None = None
        self._ensure_schema()

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path))
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def _ensure_schema(self) -> None:
        conn = self._get_conn()
        conn.executescript(_SCHEMA)
        conn.commit()

    def save_result(self, result: AnalysisResult) -> None:
        """Save a single analysis result."""
        reporter = JSONReporter()
        session = result.session
        failures_json = json.dumps([
            {
                "category": f.category.value,
                "subcategory": f.subcategory.value,
                "severity": f.severity.value,
                "description": f.description,
                "confidence": f.confidence,
            }
            for f in result.failures
        ])

        from collections import Counter
        cat_counts = Counter(f.category.value for f in result.failures)
        sev_counts = Counter(f.severity.value for f in result.failures)

        conn = self._get_conn()
        conn.execute(
            """INSERT INTO analysis_runs
               (session_id, framework, model, outcome, risk_score,
                failure_count, total_tokens, total_turns, event_count,
                category_summary, severity_summary, failures_json,
                source_file, analyzed_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                session.session_id,
                session.framework.value,
                session.model,
                session.outcome.value,
                result.risk_score,
                len(result.failures),
                session.total_tokens,
                session.total_turns,
                len(session.events),
                json.dumps(dict(cat_counts)),
                json.dumps(dict(sev_counts)),
                failures_json,
                session.metadata.get("source_file", ""),
                result.analyzed_at.isoformat(),
            ),
        )
        conn.commit()

    def save_batch(self, batch: BatchAnalysisResult) -> None:
        """Save all results from a batch analysis."""
        for result in batch.results:
            self.save_result(result)

    def get_trend(self, days: int = 30) -> list[dict]:
        """Get daily failure counts for the last N days."""
        conn = self._get_conn()
        cursor = conn.execute(
            """SELECT
                date(analyzed_at) as day,
                count(*) as total_sessions,
                sum(case when failure_count > 0 then 1 else 0 end) as failed_sessions,
                sum(failure_count) as total_failures,
                avg(risk_score) as avg_risk
               FROM analysis_runs
               WHERE analyzed_at >= date('now', ?)
               GROUP BY date(analyzed_at)
               ORDER BY day""",
            (f"-{days} days",),
        )
        return [dict(row) for row in cursor.fetchall()]

    def get_top_failures(self, days: int = 30, limit: int = 10) -> list[dict]:
        """Get top failure subcategories over the last N days."""
        conn = self._get_conn()
        cursor = conn.execute(
            """SELECT failures_json, analyzed_at
               FROM analysis_runs
               WHERE analyzed_at >= date('now', ?)""",
            (f"-{days} days",),
        )

        from collections import Counter
        subcat_counts: Counter[str] = Counter()
        for row in cursor.fetchall():
            failures = json.loads(row["failures_json"])
            for f in failures:
                subcat_counts[f["subcategory"]] += 1

        return [
            {"subcategory": sub, "count": cnt}
            for sub, cnt in subcat_counts.most_common(limit)
        ]

    def get_framework_stats(self, days: int = 30) -> list[dict]:
        """Get per-framework stats over the last N days."""
        conn = self._get_conn()
        cursor = conn.execute(
            """SELECT
                framework,
                count(*) as sessions,
                sum(case when failure_count > 0 then 1 else 0 end) as failed,
                avg(risk_score) as avg_risk
               FROM analysis_runs
               WHERE analyzed_at >= date('now', ?)
               GROUP BY framework
               ORDER BY sessions DESC""",
            (f"-{days} days",),
        )
        return [dict(row) for row in cursor.fetchall()]

    def get_total_runs(self) -> int:
        """Get total number of stored analysis runs."""
        conn = self._get_conn()
        cursor = conn.execute("SELECT count(*) as cnt FROM analysis_runs")
        return cursor.fetchone()["cnt"]

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None
