"""JSON report output."""

from __future__ import annotations

import json
from pathlib import Path

from ..models import AnalysisResult, BatchAnalysisResult


class JSONReporter:
    """Export analysis results as JSON."""

    @staticmethod
    def session_to_dict(result: AnalysisResult) -> dict:
        return {
            "session_id": result.session.session_id,
            "framework": result.session.framework.value,
            "model": result.session.model,
            "outcome": result.session.outcome.value,
            "total_tokens": result.session.total_tokens,
            "total_turns": result.session.total_turns,
            "event_count": len(result.session.events),
            "risk_score": round(result.risk_score, 3),
            "summary": result.summary,
            "failure_count": len(result.failures),
            "failures": [
                {
                    "category": f.category.value,
                    "subcategory": f.subcategory.value,
                    "severity": f.severity.value,
                    "description": f.description,
                    "confidence": round(f.confidence, 2),
                    "evidence": f.evidence[:3],
                    "event_indices": f.event_indices[:5],
                }
                for f in result.failures
            ],
            "analyzed_at": result.analyzed_at.isoformat(),
        }

    def batch_to_dict(self, batch: BatchAnalysisResult) -> dict:
        return {
            "total_sessions": batch.total_sessions,
            "failed_sessions": batch.failed_sessions,
            "failure_rate": (
                round(batch.failed_sessions / batch.total_sessions, 3)
                if batch.total_sessions > 0
                else 0
            ),
            "category_counts": batch.category_counts,
            "severity_counts": batch.severity_counts,
            "framework_counts": batch.framework_counts,
            "top_failures": [
                {"subcategory": sub, "count": cnt} for sub, cnt in batch.top_failures
            ],
            "sessions": [self.session_to_dict(r) for r in batch.results],
            "analyzed_at": batch.analyzed_at.isoformat(),
        }

    def write_session(self, result: AnalysisResult, path: str | Path) -> None:
        data = self.session_to_dict(result)
        Path(path).write_text(json.dumps(data, indent=2))

    def write_batch(self, batch: BatchAnalysisResult, path: str | Path) -> None:
        data = self.batch_to_dict(batch)
        Path(path).write_text(json.dumps(data, indent=2))
