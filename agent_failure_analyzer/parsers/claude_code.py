"""Parser for Claude Code session logs.

Claude Code stores session data as JSONL files with structured events.
This parser handles both the JSONL conversation format and the
session metadata format.
"""

from __future__ import annotations

import uuid
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


class ClaudeCodeParser(BaseParser):
    """Parse Claude Code JSONL session logs."""

    def can_parse(self, path: Path) -> bool:
        if path.is_file() and path.suffix == ".jsonl":
            try:
                first_line = self._read_jsonl(path)[:1]
                if first_line:
                    entry = first_line[0]
                    # Claude Code logs have type/role fields
                    return "type" in entry or "role" in entry
            except Exception:
                return False
        if path.is_dir():
            return any(p.suffix == ".jsonl" for p in path.rglob("*.jsonl"))
        return False

    def parse(self, path: Path) -> list[AgentSession]:
        if path.is_dir():
            sessions = []
            for jsonl_file in sorted(path.rglob("*.jsonl")):
                sessions.extend(self._parse_file(jsonl_file))
            return sessions
        return self._parse_file(path)

    def _parse_file(self, path: Path) -> list[AgentSession]:
        entries = self._read_jsonl(path)
        if not entries:
            return []

        events: list[SessionEvent] = []
        total_tokens = 0
        model = None

        for entry in entries:
            event = self._entry_to_event(entry)
            if event:
                events.append(event)

            # Extract metadata
            if "model" in entry:
                model = entry["model"]
            if "usage" in entry:
                usage = entry["usage"]
                total_tokens += usage.get("input_tokens", 0) + usage.get("output_tokens", 0)

        if not events:
            return []

        # Determine outcome
        outcome = self._infer_outcome(events)

        # Count turns (user messages)
        turns = sum(1 for e in events if e.event_type == EventType.USER_MESSAGE)

        session = AgentSession(
            session_id=path.stem or str(uuid.uuid4()),
            framework=AgentFramework.CLAUDE_CODE,
            model=model,
            start_time=events[0].timestamp,
            end_time=events[-1].timestamp,
            events=events,
            outcome=outcome,
            total_tokens=total_tokens if total_tokens > 0 else None,
            total_turns=turns,
            metadata={"source_file": str(path)},
        )
        return [session]

    def _entry_to_event(self, entry: dict) -> SessionEvent | None:
        role = entry.get("role", "")
        msg_type = entry.get("type", "")
        timestamp = None

        if "timestamp" in entry:
            try:
                timestamp = datetime.fromisoformat(entry["timestamp"])
            except (ValueError, TypeError):
                pass

        # User message
        if role == "user" or msg_type == "human":
            content = self._extract_content(entry)
            return SessionEvent(
                timestamp=timestamp,
                event_type=EventType.USER_MESSAGE,
                content=content,
                token_count=entry.get("usage", {}).get("input_tokens"),
            )

        # Assistant message
        if role == "assistant" or msg_type == "assistant":
            content = self._extract_content(entry)
            return SessionEvent(
                timestamp=timestamp,
                event_type=EventType.ASSISTANT_MESSAGE,
                content=content,
                token_count=entry.get("usage", {}).get("output_tokens"),
            )

        # Tool use
        if msg_type == "tool_use" or "tool_use" in str(entry.get("content", "")):
            tool_name = entry.get("name", entry.get("tool_name", "unknown"))
            return SessionEvent(
                timestamp=timestamp,
                event_type=EventType.TOOL_CALL,
                content=str(entry.get("input", "")),
                tool_name=tool_name,
                tool_args=entry.get("input"),
            )

        # Tool result
        if msg_type == "tool_result" or role == "tool":
            error_msg = None
            if entry.get("is_error") or entry.get("status") == "error":
                error_msg = self._extract_content(entry)
            return SessionEvent(
                timestamp=timestamp,
                event_type=EventType.TOOL_RESULT,
                content=self._extract_content(entry),
                tool_name=entry.get("tool_use_id", entry.get("name")),
                error_message=error_msg,
            )

        # System / error
        if msg_type == "error" or "error" in entry:
            return SessionEvent(
                timestamp=timestamp,
                event_type=EventType.ERROR,
                content=str(entry.get("error", entry.get("message", ""))),
                error_message=str(entry.get("error", "")),
            )

        return None

    @staticmethod
    def _extract_content(entry: dict) -> str:
        content = entry.get("content", "")
        if isinstance(content, list):
            parts = []
            for block in content:
                if isinstance(block, dict):
                    parts.append(block.get("text", str(block)))
                else:
                    parts.append(str(block))
            return "\n".join(parts)
        return str(content)

    @staticmethod
    def _infer_outcome(events: list[SessionEvent]) -> SessionOutcome:
        if not events:
            return SessionOutcome.UNKNOWN

        # Check last few events for error patterns
        last_events = events[-5:]
        error_count = sum(1 for e in last_events if e.event_type == EventType.ERROR)

        if error_count >= 2:
            return SessionOutcome.FAILURE

        # Check if session ended with an error
        if last_events and last_events[-1].event_type == EventType.ERROR:
            return SessionOutcome.FAILURE

        # Check for context overflow signals
        for e in last_events:
            if e.error_message and any(
                kw in e.error_message.lower()
                for kw in ["context", "token limit", "too long", "max_tokens"]
            ):
                return SessionOutcome.FAILURE

        # If session has reasonable length and no terminal errors
        total_events = len(events)
        if total_events < 3:
            return SessionOutcome.ABANDONED

        return SessionOutcome.UNKNOWN
