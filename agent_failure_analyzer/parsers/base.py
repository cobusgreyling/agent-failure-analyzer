"""Base parser interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from ..models import AgentSession


class BaseParser(ABC):
    """Abstract base for all log parsers."""

    @abstractmethod
    def can_parse(self, path: Path) -> bool:
        """Return True if this parser can handle the given log file/directory."""

    @abstractmethod
    def parse(self, path: Path) -> list[AgentSession]:
        """Parse log file(s) and return normalized sessions."""

    @staticmethod
    def _read_json(path: Path) -> dict | list:
        import orjson

        return orjson.loads(path.read_bytes())

    @staticmethod
    def _read_jsonl(path: Path) -> list[dict]:
        import orjson

        lines = []
        for line in path.read_text().splitlines():
            line = line.strip()
            if line:
                lines.append(orjson.loads(line))
        return lines
