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
        assert "0.1.0" in result.output

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
