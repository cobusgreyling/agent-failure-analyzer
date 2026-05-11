"""Tests for the afa explain CLI command."""

from pathlib import Path

from click.testing import CliRunner

from agent_failure_analyzer.cli import main

SAMPLE_DIR = Path(__file__).parent.parent / "sample_logs"


class TestExplainCommand:
    def setup_method(self):
        self.runner = CliRunner()

    def test_explain_first_failure(self):
        result = self.runner.invoke(
            main,
            ["explain", str(SAMPLE_DIR / "claude_code_tool_loop.jsonl"), "1"],
        )
        assert result.exit_code == 0
        assert "Failure #1" in result.output
        assert "How to fix" in result.output

    def test_explain_out_of_range(self):
        result = self.runner.invoke(
            main,
            ["explain", str(SAMPLE_DIR / "claude_code_tool_loop.jsonl"), "999"],
        )
        assert result.exit_code == 0
        assert "out of range" in result.output

    def test_explain_zero_index(self):
        result = self.runner.invoke(
            main,
            ["explain", str(SAMPLE_DIR / "claude_code_tool_loop.jsonl"), "0"],
        )
        assert result.exit_code == 0
        assert "out of range" in result.output

    def test_explain_session_index(self):
        result = self.runner.invoke(
            main,
            [
                "explain",
                str(SAMPLE_DIR / "claude_code_tool_loop.jsonl"),
                "1",
                "-s", "0",
            ],
        )
        assert result.exit_code == 0

    def test_explain_bad_session_index(self):
        result = self.runner.invoke(
            main,
            [
                "explain",
                str(SAMPLE_DIR / "claude_code_tool_loop.jsonl"),
                "1",
                "-s", "99",
            ],
        )
        assert result.exit_code == 0
        assert "out of range" in result.output
