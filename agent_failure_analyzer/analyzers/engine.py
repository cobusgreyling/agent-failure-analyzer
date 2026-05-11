"""
Analysis engine — orchestrates parsing + classification + aggregation.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from pathlib import Path

from ..models import (
    AgentSession,
    AnalysisResult,
    BatchAnalysisResult,
    SessionOutcome,
)
from ..parsers.registry import ParserRegistry, get_parser
from .classifier import FailureClassifier


class AnalysisEngine:
    """Main entry point for analyzing agent sessions."""

    def __init__(self, parser: ParserRegistry | None = None) -> None:
        self.parser = parser or get_parser()
        self.classifier = FailureClassifier()

    def analyze_session(self, session: AgentSession) -> AnalysisResult:
        """Classify failures in a single session."""
        failures = self.classifier.classify(session)

        # Calculate risk score (0-1) based on severity distribution
        severity_weights = {
            "critical": 1.0,
            "high": 0.7,
            "medium": 0.4,
            "low": 0.15,
            "info": 0.05,
        }
        if failures:
            weighted = sum(severity_weights.get(f.severity.value, 0) for f in failures)
            risk_score = min(1.0, weighted / max(len(failures), 1) * min(len(failures) / 3, 1.0))
        else:
            risk_score = 0.0

        # Generate summary
        if not failures:
            summary = "No failures detected."
        else:
            categories = Counter(f.category.value for f in failures)
            top = categories.most_common(3)
            parts = [f"{cat} ({cnt})" for cat, cnt in top]
            summary = f"{len(failures)} failure(s) detected: {', '.join(parts)}"

        return AnalysisResult(
            session=session,
            failures=failures,
            summary=summary,
            risk_score=risk_score,
        )

    def analyze_file(self, path: str | Path) -> list[AnalysisResult]:
        """Parse and analyze a log file."""
        sessions = self.parser.parse(Path(path))
        return [self.analyze_session(s) for s in sessions]

    def analyze_directory(self, directory: str | Path) -> BatchAnalysisResult:
        """Parse and analyze all logs in a directory."""
        sessions = self.parser.parse_directory(Path(directory))
        results = [self.analyze_session(s) for s in sessions]
        return self._aggregate(results)

    def analyze_sessions(self, sessions: list[AgentSession]) -> BatchAnalysisResult:
        """Analyze a list of already-parsed sessions."""
        results = [self.analyze_session(s) for s in sessions]
        return self._aggregate(results)

    @staticmethod
    def _aggregate(results: list[AnalysisResult]) -> BatchAnalysisResult:
        """Aggregate individual results into a batch summary."""
        category_counts: Counter[str] = Counter()
        severity_counts: Counter[str] = Counter()
        framework_counts: Counter[str] = Counter()
        subcategory_counts: Counter[str] = Counter()

        failed_sessions = 0

        for r in results:
            framework_counts[r.session.framework.value] += 1
            if r.session.outcome in (SessionOutcome.FAILURE, SessionOutcome.ABANDONED):
                failed_sessions += 1

            for f in r.failures:
                category_counts[f.category.value] += 1
                severity_counts[f.severity.value] += 1
                subcategory_counts[f.subcategory.value] += 1

        top_failures = subcategory_counts.most_common(10)

        return BatchAnalysisResult(
            results=results,
            total_sessions=len(results),
            failed_sessions=failed_sessions,
            category_counts=dict(category_counts),
            severity_counts=dict(severity_counts),
            framework_counts=dict(framework_counts),
            top_failures=top_failures,
        )
