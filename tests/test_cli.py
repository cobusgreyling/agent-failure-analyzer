"""Tests for the CLI."""

from pathlib import Path

from click.testing import CliRunner

from agent_failure_analyzer.cli import main

SAMPLE_DIR = Path(__file__).parent.parent / "sample_logs"


class TestCLI:
    def setup_method(self):
        self.runner = CliRunner()

    def test_version(self):
        result = self.runner.invoke(main, ["--version"])
        assert result.exit_code == 0
        assert "0.3.0" in result.output

    def test_taxonomy(self):
        result = self.runner.invoke(main, ["taxonomy"])
        assert result.exit_code == 0
        assert "context_overflow" in result.output
        assert "tool_misuse" in result.output

    def test_analyze_file_terminal(self):
        result = self.runner.invoke(
            main, ["analyze", str(SAMPLE_DIR / "claude_code_context_overflow.jsonl")]
        )
        assert result.exit_code == 0
        assert "session" in result.output.lower() or "Session" in result.output

    def test_analyze_file_json(self):
        result = self.runner.invoke(
            main,
            ["analyze", str(SAMPLE_DIR / "claude_code_context_overflow.jsonl"), "-f", "json"],
        )
        assert result.exit_code == 0
        assert "session_id" in result.output
        assert "failures" in result.output

    def test_analyze_directory(self):
        result = self.runner.invoke(main, ["analyze", str(SAMPLE_DIR)])
        assert result.exit_code == 0

    def test_analyze_directory_json_output(self, tmp_path):
        out_file = tmp_path / "report.json"
        result = self.runner.invoke(
            main,
            ["analyze", str(SAMPLE_DIR), "-f", "json", "-o", str(out_file)],
        )
        assert result.exit_code == 0
        assert out_file.exists()
        import json
        data = json.loads(out_file.read_text())
        assert "total_sessions" in data
        assert "sessions" in data

    def test_analyze_with_min_confidence(self):
        result = self.runner.invoke(
            main,
            ["analyze", str(SAMPLE_DIR), "--min-confidence", "0.9"],
        )
        assert result.exit_code == 0

    def test_analyze_with_cost(self):
        result = self.runner.invoke(
            main,
            ["analyze", str(SAMPLE_DIR), "--cost"],
        )
        assert result.exit_code == 0

    def test_check_pass(self):
        # With high threshold, should pass
        result = self.runner.invoke(
            main,
            ["check", str(SAMPLE_DIR), "--max-risk", "0.99"],
        )
        assert result.exit_code == 0
        assert "PASS" in result.output

    def test_check_fail(self):
        # With very low threshold, should fail
        result = self.runner.invoke(
            main,
            ["check", str(SAMPLE_DIR), "--max-risk", "0.01"],
        )
        assert result.exit_code == 1
        assert "FAIL" in result.output

    def test_compare(self):
        result = self.runner.invoke(
            main,
            [
                "compare",
                str(SAMPLE_DIR / "claude_code_context_overflow.jsonl"),
                str(SAMPLE_DIR / "claude_code_tool_loop.jsonl"),
            ],
        )
        assert result.exit_code == 0
        assert "Risk Score" in result.output

    def test_trend_empty(self):
        result = self.runner.invoke(main, ["trend"])
        # Should work but show empty message (no stored data)
        assert result.exit_code == 0
