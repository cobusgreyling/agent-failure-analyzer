"""Tests for the MCP server helper functions.

These exercise the underlying tool implementations without requiring the
`mcp` SDK to be installed. The wire-protocol layer (FastMCP) is thin —
it just JSON-serializes the dicts returned here.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent_failure_analyzer.mcp_server import (
    analyze_path,
    compare_sessions,
    explain_failure,
    list_taxonomy,
    remediation_for,
)

SAMPLE_DIR = Path(__file__).parent.parent / "sample_logs"
CONTEXT_OVERFLOW = SAMPLE_DIR / "claude_code_context_overflow.jsonl"
TOOL_LOOP = SAMPLE_DIR / "claude_code_tool_loop.jsonl"


class TestAnalyzePath:
    def test_file(self):
        out = analyze_path(str(CONTEXT_OVERFLOW))
        assert "sessions" in out
        assert out["session_count"] >= 1
        assert out["sessions"][0]["session_id"]
        assert "risk_score" in out["sessions"][0]

    def test_directory(self):
        out = analyze_path(str(SAMPLE_DIR))
        assert "total_sessions" in out
        assert out["total_sessions"] >= 1
        assert "category_counts" in out

    def test_missing_path(self):
        out = analyze_path("/does/not/exist")
        assert "error" in out


class TestExplain:
    def test_first_failure(self):
        analysis = analyze_path(str(CONTEXT_OVERFLOW))
        assert analysis["sessions"][0]["failure_count"] >= 1

        out = explain_failure(str(CONTEXT_OVERFLOW), failure_index=1)
        assert "category" in out
        assert "subcategory" in out
        assert "remediation" in out
        assert isinstance(out["remediation"], list)
        assert out["remediation"]

    def test_out_of_range(self):
        out = explain_failure(str(CONTEXT_OVERFLOW), failure_index=999)
        assert "error" in out


class TestTaxonomy:
    def test_shape(self):
        out = list_taxonomy()
        assert "categories" in out
        assert "context_overflow" in out["categories"]
        assert "subcategories" in out["categories"]["context_overflow"]
        assert "context_window_exceeded" in out["categories"]["context_overflow"]["subcategories"]


class TestCompare:
    def test_same_file(self):
        out = compare_sessions(str(CONTEXT_OVERFLOW), str(CONTEXT_OVERFLOW))
        assert out["risk_delta"] == 0
        assert out["new_failures"] == []
        assert out["resolved_failures"] == []

    def test_different_files(self):
        out = compare_sessions(str(CONTEXT_OVERFLOW), str(TOOL_LOOP))
        assert "a" in out and "b" in out
        assert "risk_delta" in out


class TestRemediation:
    def test_known(self):
        out = remediation_for("context_window_exceeded")
        assert out["subcategory"] == "context_window_exceeded"
        assert out["suggestions"]

    def test_unknown(self):
        out = remediation_for("not_a_real_subcategory")
        assert "error" in out
        assert "valid_subcategories" in out


def _mcp_available() -> bool:
    try:
        import mcp.server.fastmcp  # noqa: F401
        return True
    except ImportError:
        return False


@pytest.mark.skipif(not _mcp_available(), reason="mcp SDK not installed")
class TestServerBuild:
    def test_build_server_registers_tools(self):
        from agent_failure_analyzer.mcp_server import SERVER_NAME, build_server

        server = build_server()
        assert server.name == SERVER_NAME
        # FastMCP exposes run() for the stdio transport; verify it builds
        # without error and that the entry point is callable.
        assert callable(getattr(server, "run", None))


def test_analyze_json_serializable():
    """The values returned by analyze_path must round-trip through JSON."""
    out = analyze_path(str(CONTEXT_OVERFLOW))
    assert json.loads(json.dumps(out, default=str))
