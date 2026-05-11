"""Tests for session discovery / ingestion."""

from pathlib import Path

from agent_failure_analyzer.ingest import (
    discover_all,
    discover_claude_code_sessions,
)


def test_discover_nonexistent_path():
    sessions = discover_claude_code_sessions(Path("/nonexistent/path"))
    assert sessions == []


def test_discover_all_includes_extra_dirs(tmp_path):
    # Create a fake log
    (tmp_path / "test.jsonl").write_text('{"role": "user", "content": "hi"}')
    found = discover_all([tmp_path])
    assert any(str(tmp_path) in str(p) for p in found)
