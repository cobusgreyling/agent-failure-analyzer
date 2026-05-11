"""Tests for cost waste estimation."""

from agent_failure_analyzer.analyzers.engine import AnalysisEngine
from agent_failure_analyzer.cost import CostEstimate, estimate_waste
from pathlib import Path

SAMPLE_DIR = Path(__file__).parent.parent / "sample_logs"


class TestCostEstimate:
    def test_session_with_failures(self):
        engine = AnalysisEngine()
        results = engine.analyze_file(
            SAMPLE_DIR / "claude_code_context_overflow.jsonl"
        )
        est = estimate_waste(results[0])
        assert isinstance(est, CostEstimate)
        assert est.total_tokens >= 0
        assert est.wasted_tokens >= 0
        assert 0.0 <= est.waste_ratio <= 1.0

    def test_session_without_failures(self):
        engine = AnalysisEngine()
        results = engine.analyze_file(
            SAMPLE_DIR / "claude_code_real_world_anonymized.jsonl"
        )
        # This session may or may not have failures
        est = estimate_waste(results[0])
        assert isinstance(est, CostEstimate)
        assert est.estimated_total_cost_usd >= 0

    def test_cost_with_known_model(self):
        engine = AnalysisEngine()
        results = engine.analyze_file(
            SAMPLE_DIR / "claude_code_context_overflow.jsonl"
        )
        est = estimate_waste(results[0])
        # claude-sonnet-4-6 should be recognized
        assert est.model is not None
