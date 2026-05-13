"""
MCP (Model Context Protocol) server exposing Agent Failure Analyzer tools.

Lets MCP-aware clients (Claude Code, Claude Desktop, etc.) call the
analyzer directly — "explain why this session failed", "show me the
taxonomy", "diff these two runs" — without leaving the agent.

The helper functions below are importable on their own and do not require
the `mcp` SDK. The SDK is only needed to actually run the server.

Run with:

    afa mcp                # stdio transport (default for MCP clients)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .analyzers.engine import AnalysisEngine
from .remediation import get_remediation
from .reports.json_report import JSONReporter
from .taxonomy import (
    CATEGORY_DESCRIPTIONS,
    SUBCATEGORY_TO_CATEGORY,
    FailureSubcategory,
)

SERVER_NAME = "agent-failure-analyzer"


# ── Tool implementations (pure functions, no MCP dependency) ──────────


def analyze_path(path: str, llm_auto: bool = False) -> dict[str, Any]:
    """Analyze a single log file or a directory of logs."""
    p = Path(path)
    if not p.exists():
        return {"error": f"path not found: {path}"}

    engine = AnalysisEngine(llm_auto=llm_auto)
    reporter = JSONReporter()

    if p.is_dir():
        return reporter.batch_to_dict(engine.analyze_directory(p))

    results = engine.analyze_file(p)
    return {
        "session_count": len(results),
        "sessions": [reporter.session_to_dict(r) for r in results],
    }


def explain_failure(
    path: str, failure_index: int, session_index: int = 0
) -> dict[str, Any]:
    """Detailed explanation + remediation for a specific failure (1-based)."""
    p = Path(path)
    if not p.exists():
        return {"error": f"path not found: {path}"}

    results = AnalysisEngine().analyze_file(p)
    if not results:
        return {"error": "no sessions found"}
    if session_index < 0 or session_index >= len(results):
        return {
            "error": f"session_index out of range (0..{len(results) - 1})",
            "session_count": len(results),
        }

    result = results[session_index]
    if not result.failures:
        return {
            "session_id": result.session.session_id,
            "failures": [],
            "message": "no failures detected",
        }
    if failure_index < 1 or failure_index > len(result.failures):
        return {
            "error": f"failure_index out of range (1..{len(result.failures)})",
            "failure_count": len(result.failures),
        }

    failure = result.failures[failure_index - 1]
    category = SUBCATEGORY_TO_CATEGORY.get(failure.subcategory, failure.category)

    return {
        "session_id": result.session.session_id,
        "failure_index": failure_index,
        "category": category.value,
        "subcategory": failure.subcategory.value,
        "severity": failure.severity.value,
        "confidence": round(failure.confidence, 2),
        "description": failure.description,
        "category_description": CATEGORY_DESCRIPTIONS.get(category, ""),
        "evidence": failure.evidence,
        "event_indices": failure.event_indices,
        "remediation": get_remediation(failure.subcategory),
    }


def list_taxonomy() -> dict[str, Any]:
    """Return categories → subcategories with descriptions."""
    categories: dict[str, dict[str, Any]] = {}
    for sub, cat in SUBCATEGORY_TO_CATEGORY.items():
        bucket = categories.setdefault(
            cat.value,
            {
                "description": CATEGORY_DESCRIPTIONS.get(cat, ""),
                "subcategories": [],
            },
        )
        bucket["subcategories"].append(sub.value)
    return {"categories": categories}


def compare_sessions(file_a: str, file_b: str) -> dict[str, Any]:
    """Diff two single-session files."""
    pa, pb = Path(file_a), Path(file_b)
    if not pa.exists() or not pb.exists():
        return {"error": "both file_a and file_b must exist"}

    engine = AnalysisEngine()
    ra = engine.analyze_file(pa)
    rb = engine.analyze_file(pb)
    if not ra or not rb:
        return {"error": "each file must contain at least one session"}

    a, b = ra[0], rb[0]
    fa = {(f.subcategory.value, f.description) for f in a.failures}
    fb = {(f.subcategory.value, f.description) for f in b.failures}

    return {
        "a": {
            "session_id": a.session.session_id,
            "risk_score": round(a.risk_score, 3),
            "failure_count": len(a.failures),
        },
        "b": {
            "session_id": b.session.session_id,
            "risk_score": round(b.risk_score, 3),
            "failure_count": len(b.failures),
        },
        "risk_delta": round(b.risk_score - a.risk_score, 3),
        "new_failures": [
            {"subcategory": s, "description": d} for s, d in sorted(fb - fa)
        ],
        "resolved_failures": [
            {"subcategory": s, "description": d} for s, d in sorted(fa - fb)
        ],
    }


def get_trend_data(days: int = 30) -> dict[str, Any]:
    """Pull trend data from the SQLite history (populated by `afa analyze --store`)."""
    from .storage import AnalysisStore

    store = AnalysisStore()
    return {
        "days": days,
        "total_runs": store.get_total_runs(),
        "daily": store.get_trend(days=days),
        "top_failures": store.get_top_failures(days=days),
        "framework_stats": store.get_framework_stats(days=days),
    }


def remediation_for(subcategory: str) -> dict[str, Any]:
    """Lookup remediation suggestions for a failure subcategory."""
    try:
        sub = FailureSubcategory(subcategory)
    except ValueError:
        return {
            "error": f"unknown subcategory: {subcategory}",
            "valid_subcategories": [s.value for s in FailureSubcategory],
        }
    return {"subcategory": sub.value, "suggestions": get_remediation(sub)}


# ── MCP server wiring (requires the `mcp` SDK) ────────────────────────


def build_server() -> Any:
    """Construct a FastMCP server with all tools registered.

    Raises ImportError if the `mcp` package is not installed.
    """
    from mcp.server.fastmcp import FastMCP

    server = FastMCP(SERVER_NAME)

    @server.tool()
    def analyze(path: str, llm_auto: bool = False) -> str:
        """Classify failures in an agent session log file or directory.

        Returns a JSON report with per-session risk scores, failure
        categories, and aggregate statistics across sessions.

        Args:
            path: Path to a .json/.jsonl file or a directory of logs.
            llm_auto: If true, escalate to the LLM classifier when
                heuristics are likely insufficient. Requires
                ANTHROPIC_API_KEY in the environment.
        """
        return json.dumps(analyze_path(path, llm_auto=llm_auto), default=str)

    @server.tool()
    def explain(path: str, failure_index: int, session_index: int = 0) -> str:
        """Explain a single classified failure and suggest fixes.

        Args:
            path: Path to the log file.
            failure_index: 1-based failure index (as printed by `afa analyze`).
            session_index: 0-based session index when the file has multiple
                sessions. Defaults to 0.
        """
        return json.dumps(
            explain_failure(path, failure_index, session_index), default=str
        )

    @server.tool()
    def taxonomy() -> str:
        """Return the full failure taxonomy — categories, subcategories, descriptions."""
        return json.dumps(list_taxonomy())

    @server.tool()
    def compare(file_a: str, file_b: str) -> str:
        """Diff two session logs: risk delta, newly-introduced failures, resolved failures."""
        return json.dumps(compare_sessions(file_a, file_b), default=str)

    @server.tool()
    def trend(days: int = 30) -> str:
        """Trend data over the last N days from the stored history.

        Requires prior `afa analyze --store` runs to populate the SQLite history.
        """
        return json.dumps(get_trend_data(days=days), default=str)

    @server.tool()
    def remediation(subcategory: str) -> str:
        """Remediation suggestions for a given failure subcategory.

        Example subcategory values: "context_window_exceeded",
        "invalid_tool_args", "fabricated_file_path". Call `taxonomy` to
        see the full list.
        """
        return json.dumps(remediation_for(subcategory))

    return server


def run_stdio() -> None:
    """Run the MCP server over stdio."""
    build_server().run()
