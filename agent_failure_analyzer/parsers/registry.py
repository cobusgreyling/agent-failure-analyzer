"""Parser registry — auto-detects the right parser for a given log file."""

from __future__ import annotations

import sys
from pathlib import Path

from ..models import AgentSession
from .autogen import AutoGenParser
from .base import BaseParser
from .claude_code import ClaudeCodeParser
from .crewai import CrewAIParser
from .generic import GenericJSONParser
from .langchain import LangChainParser
from .openai_assistants import OpenAIAssistantsParser


def _load_plugin_parsers() -> list[BaseParser]:
    """Load parsers registered via the 'afa.parsers' entry point group."""
    plugins: list[BaseParser] = []
    if sys.version_info >= (3, 12):
        from importlib.metadata import entry_points
        eps = entry_points(group="afa.parsers")
    else:
        from importlib.metadata import entry_points
        all_eps = entry_points()
        eps = all_eps.get("afa.parsers", [])  # type: ignore[union-attr]

    for ep in eps:
        try:
            parser_cls = ep.load()
            instance = parser_cls()
            if isinstance(instance, BaseParser):
                plugins.append(instance)
        except Exception:
            continue
    return plugins


class ParserRegistry:
    """Try each specialized parser, fall back to generic.

    Discovers plugin parsers via the ``afa.parsers`` entry point group.
    Plugin parsers are tried after built-in specific parsers but before
    the generic fallback.
    """

    def __init__(self) -> None:
        # Order matters: try specific parsers before generic
        plugin_parsers = _load_plugin_parsers()
        self._parsers: list[BaseParser] = [
            ClaudeCodeParser(),
            LangChainParser(),
            CrewAIParser(),
            AutoGenParser(),
            OpenAIAssistantsParser(),
            *plugin_parsers,
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
