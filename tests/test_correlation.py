"""Tests for the correlation module."""

from agent_failure_analyzer.correlation import CorrelationReport, correlate
from agent_failure_analyzer.models import (
    AgentFramework,
    AgentSession,
    AnalysisResult,
    BatchAnalysisResult,
    FailureInstance,
    SessionOutcome,
)
from agent_failure_analyzer.taxonomy import (
    FailureCategory,
    FailureSubcategory,
    Severity,
)


def _make_result(session_id, framework, failures):
    """Helper to build an AnalysisResult with given failures."""
    session = AgentSession(
        session_id=session_id,
        framework=framework,
        outcome=SessionOutcome.FAILURE,
    )
    return AnalysisResult(
        session=session,
        failures=failures,
        risk_score=0.5,
    )


def _make_failure(subcat, severity=Severity.MEDIUM):
    cat = {
        FailureSubcategory.IDENTICAL_ACTION_LOOP: FailureCategory.LOOP_REPETITION,
        FailureSubcategory.FABRICATED_FILE_PATH: FailureCategory.HALLUCINATION,
        FailureSubcategory.INVALID_TOOL_ARGS: FailureCategory.TOOL_MISUSE,
        FailureSubcategory.CONTEXT_WINDOW_EXCEEDED: FailureCategory.CONTEXT_OVERFLOW,
    }.get(subcat, FailureCategory.UNKNOWN)
    return FailureInstance(
        category=cat,
        subcategory=subcat,
        severity=severity,
        description="test failure",
        confidence=0.8,
    )


class TestCorrelate:
    def test_empty_batch(self):
        batch = BatchAnalysisResult(results=[], total_sessions=0)
        report = correlate(batch)
        assert isinstance(report, CorrelationReport)
        assert len(report.patterns) == 0

    def test_recurring_failure_detected(self):
        """Failures appearing in 30%+ of sessions should be flagged."""
        loop_failure = _make_failure(FailureSubcategory.IDENTICAL_ACTION_LOOP)
        results = [
            _make_result(f"s{i}", AgentFramework.GENERIC, [loop_failure])
            for i in range(5)
        ]
        batch = BatchAnalysisResult(results=results, total_sessions=5)
        report = correlate(batch)
        recurring = [p for p in report.patterns if p.pattern_type == "recurring_failure"]
        assert len(recurring) >= 1
        assert "identical_action_loop" in recurring[0].description

    def test_co_occurring_failures(self):
        """Failures that appear together should be detected."""
        f1 = _make_failure(FailureSubcategory.FABRICATED_FILE_PATH)
        f2 = _make_failure(FailureSubcategory.INVALID_TOOL_ARGS)
        results = [
            _make_result(f"s{i}", AgentFramework.GENERIC, [f1, f2])
            for i in range(4)
        ]
        batch = BatchAnalysisResult(results=results, total_sessions=4)
        report = correlate(batch)
        assert report.co_occurrence_matrix

    def test_single_session_no_patterns(self):
        f1 = _make_failure(FailureSubcategory.FABRICATED_FILE_PATH)
        results = [_make_result("s0", AgentFramework.GENERIC, [f1])]
        batch = BatchAnalysisResult(results=results, total_sessions=1)
        report = correlate(batch)
        # With only 1 session, no recurring patterns
        recurring = [p for p in report.patterns if p.pattern_type == "recurring_failure"]
        assert len(recurring) == 0
