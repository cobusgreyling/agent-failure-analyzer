"""Generic JSON/JSONL parser for unrecognized formats.

Attempts best-effort parsing of any JSON-based agent log.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from ..models import (
    AgentFramework,
    AgentSession,
    EventType,
    SessionEvent,
    SessionOutcome,
)
from .base import BaseParser


class GenericJSONParser(BaseParser):
    """Best-effort parser for JSON/JSONL agent logs."""

    def can_parse(self, path: Path) -> bool:
        return path.is_file() and path.suffix in (".json", ".jsonl")

    def parse(self, path: Path) -> list[AgentSession]:
        if path.suffix == ".jsonl":
            entries = self._read_jsonl(path)
        else:
            data = self._read_json(path)
            entries = data if isinstance(data, list) else [data]

        events: list[SessionEvent] = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            event = self._guess_event(entry)
            if event:
                events.append(event)

        if not events:
            return []

        session = AgentSession(
            session_id=path.stem,
            framework=AgentFramework.GENERIC,
            events=events,
            outcome=self._infer_outcome(events),
            total_turns=sum(1 for e in events if e.event_type == EventType.USER_MESSAGE),
            metadata={"source_file": str(path)},
        )
        return [session]

    def _guess_event(self, entry: dict) -> SessionEvent | None:
        timestamp = None
        for ts_key in ("timestamp", "time", "created_at", "ts", "datetime"):
            if ts_key in entry:
                try:
                    timestamp = datetime.fromisoformat(str(entry[ts_key]))
                except (ValueError, TypeError):
                    pass
                break

        # Detect event type from common keys
        role = entry.get("role", entry.get("type", entry.get("event_type", ""))).lower()

        if role in ("user", "human", "input"):
            return SessionEvent(
                timestamp=timestamp,
                event_type=EventType.USER_MESSAGE,
                content=self._get_content(entry),
            )

        if role in ("assistant", "ai", "bot", "output", "response"):
            return SessionEvent(
                timestamp=timestamp,
                event_type=EventType.ASSISTANT_MESSAGE,
                content=self._get_content(entry),
            )

        if role in ("tool", "function", "action") or "tool" in entry or "function_call" in entry:
            tool_name = (
                entry.get("tool", entry.get("name", entry.get("function", {}).get("name")))
            )
            return SessionEvent(
                timestamp=timestamp,
                event_type=EventType.TOOL_CALL,
                content=self._get_content(entry),
                tool_name=str(tool_name) if tool_name else None,
                tool_args=entry.get("arguments", entry.get("input", entry.get("args"))),
            )

        if role in ("error", "exception") or "error" in entry:
            error_msg = str(entry.get("error", entry.get("message", entry.get("content", ""))))
            return SessionEvent(
                timestamp=timestamp,
                event_type=EventType.ERROR,
                content=error_msg,
                error_message=error_msg,
            )

        if role in ("system", "info", "log"):
            return SessionEvent(
                timestamp=timestamp,
                event_type=EventType.SYSTEM,
                content=self._get_content(entry),
            )

        # If we can't determine the type, try content-based detection
        content = self._get_content(entry)
        if content:
            return SessionEvent(
                timestamp=timestamp,
                event_type=EventType.SYSTEM,
                content=content,
                metadata={"raw_keys": list(entry.keys())},
            )

        return None

    @staticmethod
    def _get_content(entry: dict) -> str:
        for key in ("content", "text", "message", "output", "data", "body"):
            if key in entry:
                val = entry[key]
                if isinstance(val, str):
                    return val
                return str(val)
        return ""

    @staticmethod
    def _infer_outcome(events: list[SessionEvent]) -> SessionOutcome:
        error_count = sum(1 for e in events if e.event_type == EventType.ERROR)
        if error_count >= 2:
            return SessionOutcome.FAILURE
        if events and events[-1].event_type == EventType.ERROR:
            return SessionOutcome.FAILURE
        if len(events) < 3:
            return SessionOutcome.ABANDONED
        return SessionOutcome.UNKNOWN
