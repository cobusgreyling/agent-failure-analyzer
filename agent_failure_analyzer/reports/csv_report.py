"""CSV report output."""

from __future__ import annotations

import csv
import io
from pathlib import Path

from ..models import AnalysisResult, BatchAnalysisResult


class CSVReporter:
    """Export analysis results as CSV."""

    HEADERS = [
        "session_id",
        "framework",
        "model",
        "outcome",
        "risk_score",
        "total_tokens",
        "category",
        "subcategory",
        "severity",
        "confidence",
        "description",
    ]

    def result_to_rows(self, result: AnalysisResult) -> list[list[str]]:
        """Convert a single result to CSV rows (one row per failure)."""
        session = result.session
        if not result.failures:
            return [[
                session.session_id,
                session.framework.value,
                session.model or "",
                session.outcome.value,
                f"{result.risk_score:.3f}",
                str(session.total_tokens or ""),
                "",
                "",
                "",
                "",
                "No failures detected",
            ]]

        rows = []
        for f in result.failures:
            rows.append([
                session.session_id,
                session.framework.value,
                session.model or "",
                session.outcome.value,
                f"{result.risk_score:.3f}",
                str(session.total_tokens or ""),
                f.category.value,
                f.subcategory.value,
                f.severity.value,
                f"{f.confidence:.2f}",
                f.description,
            ])
        return rows

    def batch_to_csv(self, batch: BatchAnalysisResult) -> str:
        """Convert a batch result to CSV string."""
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(self.HEADERS)
        for result in batch.results:
            writer.writerows(self.result_to_rows(result))
        return output.getvalue()

    def write_batch(self, batch: BatchAnalysisResult, path: str | Path) -> None:
        """Write batch results to a CSV file."""
        Path(path).write_text(self.batch_to_csv(batch))

    def write_session(self, result: AnalysisResult, path: str | Path) -> None:
        """Write a single session result to a CSV file."""
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(self.HEADERS)
        writer.writerows(self.result_to_rows(result))
        Path(path).write_text(output.getvalue())
