"""
Auto-discover and ingest agent session logs from known locations.
"""

from __future__ import annotations

from pathlib import Path


def discover_claude_code_sessions(base: Path | None = None) -> list[Path]:
    """Find all Claude Code session log files.

    Searches ~/.claude/projects/ for JSONL session files.
    """
    if base is None:
        base = Path.home() / ".claude" / "projects"

    if not base.exists():
        return []

    sessions: list[Path] = []
    for jsonl in sorted(base.rglob("*.jsonl")):
        sessions.append(jsonl)

    return sessions


def discover_langsmith_exports(base: Path) -> list[Path]:
    """Find LangSmith exported JSON trace files."""
    if not base.exists():
        return []
    return sorted(base.rglob("*.json"))


def discover_all(directories: list[Path] | None = None) -> list[Path]:
    """Discover all known session log files."""
    found: list[Path] = []

    # Always check Claude Code default location
    found.extend(discover_claude_code_sessions())

    # Check any additional directories
    if directories:
        for d in directories:
            d = Path(d)
            if d.exists():
                found.extend(
                    p for p in sorted(d.rglob("*"))
                    if p.is_file() and p.suffix in (".json", ".jsonl")
                )

    return found
