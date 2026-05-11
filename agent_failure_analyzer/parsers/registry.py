"""Parser registry — auto-detects the right parser for a given log file."""

from __future__ import annotations

from pathlib import Path

from ..models import AgentSession
from .base import BaseParser
from .claude_code import ClaudeCodeParser
from .crewai import CrewAIParser
from .generic import GenericJSONParser
from .langchain import LangChainParser


class ParserRegistry:
    """Try each specialized parser, fall back to generic."""

    def __init__(self) -> None:
        # Order matters: try specific parsers before generic
        self._parsers: list[BaseParser] = [
            ClaudeCodeParser(),
            LangChainParser(),
            CrewAIParser(),
            GenericJSONParser(),
        ]

    def parse(self, path: Path) -> list[AgentSession]:
        path = Path(path)
        for parser in self._parsers:
            if parser.can_parse(path):
                return parser.parse(path)
        return []

    def parse_directory(self, directory: Path) -> list[AgentSession]:
        directory = Path(directory)
        sessions: list[AgentSession] = []
        log_files = sorted(
            p for p in directory.rglob("*")
            if p.is_file() and p.suffix in (".json", ".jsonl")
        )
        for log_file in log_files:
            try:
                sessions.extend(self.parse(log_file))
            except Exception:
                continue
        return sessions


def get_parser() -> ParserRegistry:
    """Return a configured parser registry."""
    return ParserRegistry()
