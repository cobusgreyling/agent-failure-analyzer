"""Tests for the failure classifier."""

from pathlib import Path

from agent_failure_analyzer.analyzers.classifier import FailureClassifier
from agent_failure_analyzer.analyzers.engine import AnalysisEngine
from agent_failure_analyzer.taxonomy import FailureCategory, FailureSubcategory

SAMPLE_DIR = Path(__file__).parent.parent / "sample_logs"


class TestClassifier:
    def setup_method(self):
        self.engine = AnalysisEngine()
        self.classifier = FailureClassifier()

    def test_detect_context_overflow(self):
        results = self.engine.analyze_file(
            SAMPLE_DIR / "claude_code_context_overflow.jsonl"
        )
        assert len(results) == 1
        failures = results[0].failures
        categories = {f.category for f in failures}
        assert FailureCategory.CONTEXT_OVERFLOW in categories

    def test_detect_tool_loop(self):
        results = self.engine.analyze_file(
            SAMPLE_DIR / "claude_code_tool_loop.jsonl"
        )
        assert len(results) == 1
        failures = results[0].failures
        categories = {f.category for f in failures}
        # Should detect loops and/or tool misuse
        assert (
            FailureCategory.LOOP_REPETITION in categories
            or FailureCategory.TOOL_MISUSE in categories
        )

    def test_detect_error_cascade(self):
        results = self.engine.analyze_file(
            SAMPLE_DIR / "langchain_error_cascade.json"
        )
        assert len(results) == 1
        failures = results[0].failures
        categories = {f.category for f in failures}
        assert (
            FailureCategory.ERROR_CASCADE in categories
            or FailureCategory.RESOURCE_EXHAUSTION in categories
        )

    def test_detect_hallucination(self):
        results = self.engine.analyze_file(
            SAMPLE_DIR / "crewai_hallucination.json"
        )
        assert len(results) == 1
        failures = results[0].failures
        categories = {f.category for f in failures}
        assert FailureCategory.HALLUCINATION in categories

    def test_risk_score_range(self):
        results = self.engine.analyze_file(
            SAMPLE_DIR / "claude_code_context_overflow.jsonl"
        )
        assert 0.0 <= results[0].risk_score <= 1.0

    def test_batch_analysis(self):
        batch = self.engine.analyze_directory(SAMPLE_DIR)
        assert batch.total_sessions >= 4
        assert batch.category_counts  # Should have some failures
        assert batch.severity_counts


class TestEngine:
    def test_analyze_directory_aggregation(self):
        engine = AnalysisEngine()
        batch = engine.analyze_directory(SAMPLE_DIR)
        assert batch.total_sessions >= 4
        assert batch.top_failures  # Should rank failure types
        assert isinstance(batch.framework_counts, dict)
        assert len(batch.framework_counts) >= 2  # Multiple frameworks
