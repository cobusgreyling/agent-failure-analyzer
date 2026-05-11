"""Tests for SQLite storage."""

from pathlib import Path

from agent_failure_analyzer.analyzers.engine import AnalysisEngine
from agent_failure_analyzer.storage import AnalysisStore

SAMPLE_DIR = Path(__file__).parent.parent / "sample_logs"


class TestStorage:
    def setup_method(self, tmp_path=None):
        self.db_path = Path("/tmp/afa_test.db")
        if self.db_path.exists():
            self.db_path.unlink()
        self.store = AnalysisStore(self.db_path)
        self.engine = AnalysisEngine()

    def teardown_method(self):
        self.store.close()
        if self.db_path.exists():
            self.db_path.unlink()

    def test_save_and_count(self):
        results = self.engine.analyze_file(
            SAMPLE_DIR / "claude_code_context_overflow.jsonl"
        )
        for r in results:
            self.store.save_result(r)
        assert self.store.get_total_runs() == 1

    def test_save_batch(self):
        batch = self.engine.analyze_directory(SAMPLE_DIR)
        self.store.save_batch(batch)
        assert self.store.get_total_runs() >= 4

    def test_trend_returns_data(self):
        batch = self.engine.analyze_directory(SAMPLE_DIR)
        self.store.save_batch(batch)
        trend = self.store.get_trend(30)
        assert len(trend) >= 1
        assert "day" in trend[0]
        assert "total_sessions" in trend[0]

    def test_top_failures(self):
        batch = self.engine.analyze_directory(SAMPLE_DIR)
        self.store.save_batch(batch)
        top = self.store.get_top_failures(30)
        assert len(top) >= 1
        assert "subcategory" in top[0]

    def test_framework_stats(self):
        batch = self.engine.analyze_directory(SAMPLE_DIR)
        self.store.save_batch(batch)
        stats = self.store.get_framework_stats(30)
        assert len(stats) >= 1
        assert "framework" in stats[0]
