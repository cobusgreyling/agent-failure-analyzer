"""
PDF report output.

Generates a standalone PDF by rendering the HTML report through
weasyprint. Requires: pip install agent-failure-analyzer[pdf]
"""

from __future__ import annotations

from pathlib import Path

from ..models import AnalysisResult, BatchAnalysisResult
from .html_report import HTMLReporter


class PDFReporter:
    """Export analysis results as a PDF file."""

    def __init__(self) -> None:
        self._html = HTMLReporter()

    def _render_pdf(self, html_content: str) -> bytes:
        """Convert HTML string to PDF bytes."""
        try:
            from weasyprint import HTML
        except ImportError:
            raise ImportError(
                "weasyprint is required for PDF export. "
                "Install with: pip install agent-failure-analyzer[pdf]"
            )
        return HTML(string=html_content).write_pdf()

    def write_batch(
        self, batch: BatchAnalysisResult, path: str | Path
    ) -> None:
        """Write batch results as a PDF file."""
        html = self._html.batch_to_html(batch)
        pdf_bytes = self._render_pdf(html)
        Path(path).write_bytes(pdf_bytes)

    def write_session(
        self, result: AnalysisResult, path: str | Path
    ) -> None:
        """Write a single session result as a PDF file."""
        html = self._html.session_to_html(result)
        pdf_bytes = self._render_pdf(html)
        Path(path).write_bytes(pdf_bytes)
