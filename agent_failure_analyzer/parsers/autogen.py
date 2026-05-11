"""Parser for Microsoft AutoGen agent logs."""

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


class AutoGenParser(BaseParser):
    """Parse AutoGen conversation logs (JSON/JSONL).

    Handles the AutoGen conversation format with sender/content pairs,
    including GroupChat logs and two-agent conversations.
    """

    def can_parse(self, path: Path) -> bool:
        if path.suffix not in (".json", ".jsonl"):
            return False
        try:
            if path.suffix == ".jsonl":
                data = self._read_jsonl(path)
                if not data:
                    return False
                first = data[0]
            else:
                raw = self._read_json(path)
                if isinstance(raw, list) and raw:
                    first = raw[0]
                elif isinstance(raw, dict):
                    first = raw
                else:
                    return False

            # AutoGen logs typically have sender + content, or name + role
            return (
                isinstance(first, dict)
                and ("sender" in first or "name" in first)
                and ("content" in first or "message" in first)
                and any(
                    kw in str(first).lower()
                    for kw in ["autogen", "assistant", "user_proxy", "groupchat"]
                )
            )
        except Exception:
            return False

    def parse(self, path: Path) -> list[AgentSession]:
        if path.suffix == ".jsonl":
            records = self._read_jsonl(path)
        else:
            raw = self._read_json(path)
            records = raw if isinstance(raw, list) else [raw]

        if not records:
            return []

        events: list[SessionEvent] = []
        models_seen: set[str] = set()
        has_error = False

        for i, record in enumerate(records):
            if not isinstance(record, dict):
                continue

            sender = record.get("sender", record.get("name", "unknown"))
            content = record.get("content", record.get("message", ""))
            role = record.get("role", "")

            # Detect event type from sender/role
            sender_lower = str(sender).lower()
            if "user" in sender_lower or role == "user":
                event_type = EventType.USER_MESSAGE
            elif "tool" in sender_lower or "function" in sender_lower:
                event_type = EventType.TOOL_RESULT
            else:
                event_type = EventType.ASSISTANT_MESSAGE

            # Check for tool calls in content
            tool_name = None
            tool_args = None
            if isinstance(content, dict):
                if "function_call" in content:
                    event_type = EventType.TOOL_CALL
                    fc = content["function_call"]
                    tool_name = fc.get("name", "")
                    tool_args = fc.get("arguments", {})
                    content = str(fc)
                elif "tool_calls" in content:
                    event_type = EventType.TOOL_CALL
                    tc = content["tool_calls"]
                    if isinstance(tc, list) and tc:
                        tool_name = tc[0].get("function", {}).get("name", "")
                    content = str(tc)
                else:
                    content = str(content)

            # Check for errors
            error_msg = None
            content_str = str(content)
            if any(kw in content_str.lower() for kw in ["error", "exception", "traceback"]):
                error_msg = content_str[:500]
                has_error = True

            # Extract model
            model = record.get("model", None)
            if model:
                models_seen.add(model)

            timestamp = None
            if "timestamp" in record:
                try:
                    timestamp = datetime.fromisoformat(str(record["timestamp"]))
                except (ValueError, TypeError):
                    pass

            events.append(SessionEvent(
                timestamp=timestamp,
                event_type=event_type,
                content=content_str if isinstance(content_str, str) else str(content_str),
                tool_name=tool_name,
                tool_args=tool_args,
                error_message=error_msg,
            ))

        session_id = f"autogen_{path.stem}"
        outcome = SessionOutcome.FAILURE if has_error else SessionOutcome.UNKNOWN

        return [AgentSession(
            session_id=session_id,
            framework=AgentFramework.AUTOGEN,
            model=next(iter(models_seen), None),
            events=events,
            outcome=outcome,
            total_turns=sum(1 for e in events if e.event_type == EventType.USER_MESSAGE),
            metadata={"source_file": str(path)},
        )]
