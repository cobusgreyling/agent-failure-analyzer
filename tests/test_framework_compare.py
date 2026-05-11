"""Tests for the framework_compare module."""

from io import StringIO

from rich.console import Console

from agent_failure_analyzer.framework_compare import (
    ComparisonReport,
    compare_frameworks,
    print_comparison,
)
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


def _make_result(session_id, framework, risk=0.5, failure_count=2, tokens=1000):
    failures = [
        FailureInstance(
            category=FailureCategory.TOOL_MISUSE,
            subcategory=FailureSubcategory.INVALID_TOOL_ARGS,
            severity=Severity.MEDIUM,
            description=f"failure {i}",
            confidence=0.8,
        )
        for i in range(failure_count)
    ]
    session = AgentSession(
        session_id=session_id,
        framework=framework,
        outcome=SessionOutcome.FAILURE if failure_count > 0 else SessionOutcome.SUCCESS,
        total_tokens=tokens,
    )
    return AnalysisResult(session=session, failures=failures, risk_score=risk)


class TestCompareFrameworks:
    def test_empty_batch(self):
        batch = BatchAnalysisResult(results=[], total_sessions=0)
        report = compare_frameworks(batch)
        assert isinstance(report, ComparisonReport)
        assert len(report.frameworks) == 0

    def test_single_framework(self):
        results = [
            _make_result("s1", AgentFramework.CLAUDE_CODE, risk=0.4),
            _make_result("s2", AgentFramework.CLAUDE_CODE, risk=0.6),
        ]
        batch = BatchAnalysisResult(results=results, total_sessions=2)
        report = compare_frameworks(batch)
        assert len(report.frameworks) == 1
        fw = report.frameworks[0]
        assert fw.name == "claude_code"
        assert fw.session_count == 2
        assert fw.avg_risk == 0.5

    def test_multiple_frameworks(self):
        results = [
            _make_result("s1", AgentFramework.CLAUDE_CODE, risk=0.3, failure_count=1),
            _make_result("s2", AgentFramework.LANGCHAIN, risk=0.7, failure_count=5),
        ]
        batch = BatchAnalysisResult(results=results, total_sessions=2)
        report = compare_frameworks(batch)
        assert len(report.frameworks) == 2
        # Sorted by avg risk, so best first
        assert report.best_framework == "claude_code"
        assert report.worst_framework == "langchain"

    def test_avg_tokens(self):
        results = [
            _make_result("s1", AgentFramework.GENERIC, tokens=2000),
            _make_result("s2", AgentFramework.GENERIC, tokens=4000),
        ]
        batch = BatchAnalysisResult(results=results, total_sessions=2)
        report = compare_frameworks(batch)
        assert report.frameworks[0].avg_tokens == 3000


class TestPrintComparison:
    def test_prints_without_error(self):
        results = [
            _make_result("s1", AgentFramework.CLAUDE_CODE, risk=0.3),
            _make_result("s2", AgentFramework.LANGCHAIN, risk=0.7),
        ]
        batch = BatchAnalysisResult(results=results, total_sessions=2)
        report = compare_frameworks(batch)
        buf = StringIO()
        console = Console(file=buf, force_terminal=True, width=120)
        print_comparison(report, console)
        output = buf.getvalue()
        assert "Framework Comparison" in output
        assert "Best" in output

    def test_prints_empty(self):
        report = ComparisonReport()
        buf = StringIO()
        console = Console(file=buf, force_terminal=True, width=100)
        print_comparison(report, console)
        output = buf.getvalue()
        assert "No framework data" in output
