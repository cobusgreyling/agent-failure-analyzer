"""Tests for the heatmap module."""

from datetime import datetime

from agent_failure_analyzer.heatmap import (
    HeatmapData,
    build_heatmap,
    heatmap_to_text,
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


def _make_result(session_id, start_time, failure_count=1):
    failures = [
        FailureInstance(
            category=FailureCategory.TOOL_MISUSE,
            subcategory=FailureSubcategory.INVALID_TOOL_ARGS,
            severity=Severity.MEDIUM,
            description="test",
            confidence=0.8,
        )
        for _ in range(failure_count)
    ]
    session = AgentSession(
        session_id=session_id,
        framework=AgentFramework.GENERIC,
        start_time=start_time,
        outcome=SessionOutcome.FAILURE,
    )
    return AnalysisResult(session=session, failures=failures, risk_score=0.5)


class TestBuildHeatmap:
    def test_empty_batch(self):
        batch = BatchAnalysisResult(results=[], total_sessions=0)
        data = build_heatmap(batch)
        assert isinstance(data, HeatmapData)
        assert data.total == 0

    def test_single_session(self):
        # Wednesday at 14:00
        ts = datetime(2026, 5, 6, 14, 0)  # Wednesday
        result = _make_result("s1", ts, failure_count=3)
        batch = BatchAnalysisResult(results=[result], total_sessions=1)
        data = build_heatmap(batch)
        assert data.total == 3
        assert data.grid[ts.weekday()][14] == 3

    def test_peak_detection(self):
        # Two sessions: one with 1 failure, another with 5
        ts1 = datetime(2026, 5, 5, 10, 0)  # Monday 10am
        ts2 = datetime(2026, 5, 6, 15, 0)  # Wednesday 3pm
        r1 = _make_result("s1", ts1, failure_count=1)
        r2 = _make_result("s2", ts2, failure_count=5)
        batch = BatchAnalysisResult(results=[r1, r2], total_sessions=2)
        data = build_heatmap(batch)
        assert data.peak_hour == 15
        assert data.peak_day == "Wed"

    def test_no_failures_session_skipped(self):
        session = AgentSession(
            session_id="s1",
            framework=AgentFramework.GENERIC,
            start_time=datetime(2026, 5, 5, 10, 0),
            outcome=SessionOutcome.SUCCESS,
        )
        result = AnalysisResult(session=session, failures=[], risk_score=0.0)
        batch = BatchAnalysisResult(results=[result], total_sessions=1)
        data = build_heatmap(batch)
        assert data.total == 0


class TestHeatmapToText:
    def test_empty_heatmap(self):
        data = HeatmapData()
        text = heatmap_to_text(data)
        assert "No timestamped failures" in text

    def test_non_empty_heatmap(self):
        data = HeatmapData(total=5)
        data.grid[0][10] = 3  # Monday 10am — must be < max so intensity stays in range
        data.grid[2][14] = 5  # Wednesday 2pm
        data.peak_day = "Wed"
        data.peak_hour = 14
        text = heatmap_to_text(data)
        assert "Mon" in text
        assert "Total: 5" in text
