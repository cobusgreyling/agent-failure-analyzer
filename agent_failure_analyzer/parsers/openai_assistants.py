"""Parser for OpenAI Assistants API run logs."""

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


class OpenAIAssistantsParser(BaseParser):
    """Parse OpenAI Assistants API run/thread logs (JSON).

    Handles thread message exports and run step logs from the
    OpenAI Assistants API, including tool call steps.
    """

    def can_parse(self, path: Path) -> bool:
        if path.suffix != ".json":
            return False
        try:
            raw = self._read_json(path)
            if isinstance(raw, dict):
                # Check for Assistants API objects
                obj_type = raw.get("object", "")
                return obj_type in (
                    "thread",
                    "thread.run",
                    "list",
                    "thread.message",
                ) or (
                    "data" in raw
                    and isinstance(raw["data"], list)
                    and raw["data"]
                    and isinstance(raw["data"][0], dict)
                    and raw["data"][0].get("object", "").startswith("thread")
                )
            if isinstance(raw, list) and raw:
                first = raw[0]
                return isinstance(first, dict) and (
                    first.get("object", "").startswith("thread")
                    or "assistant_id" in first
                )
            return False
        except Exception:
            return False

    def parse(self, path: Path) -> list[AgentSession]:
        raw = self._read_json(path)

        # Normalize to a list of records
        if isinstance(raw, dict):
            if "data" in raw and isinstance(raw["data"], list):
                records = raw["data"]
            else:
                records = [raw]
        elif isinstance(raw, list):
            records = raw
        else:
            return []

        events: list[SessionEvent] = []
        model = None
        assistant_id = None
        thread_id = None
        has_error = False
        status = None

        for record in records:
            if not isinstance(record, dict):
                continue

            obj_type = record.get("object", "")

            # Extract metadata
            if record.get("model"):
                model = record["model"]
            if record.get("assistant_id"):
                assistant_id = record["assistant_id"]
            if record.get("thread_id"):
                thread_id = record["thread_id"]
            if record.get("status"):
                status = record["status"]

            # Thread messages
            if obj_type == "thread.message":
                role = record.get("role", "")
                content_blocks = record.get("content", [])
                content_text = ""
                for block in content_blocks:
                    if isinstance(block, dict):
                        if block.get("type") == "text":
                            content_text += block.get("text", {}).get("value", "")
                        elif block.get("type") == "image_file":
                            content_text += "[image]"

                event_type = (
                    EventType.USER_MESSAGE if role == "user" else EventType.ASSISTANT_MESSAGE
                )

                timestamp = None
                if "created_at" in record:
                    try:
                        timestamp = datetime.fromtimestamp(record["created_at"])
                    except (ValueError, TypeError, OSError):
                        pass

                events.append(SessionEvent(
                    timestamp=timestamp,
                    event_type=event_type,
                    content=content_text,
                ))

            # Run steps
            elif obj_type == "thread.run.step":
                step_type = record.get("type", "")
                step_details = record.get("step_details", {})

                if step_type == "tool_calls":
                    tool_calls = step_details.get("tool_calls", [])
                    for tc in tool_calls:
                        tc_type = tc.get("type", "")
                        if tc_type == "function":
                            fn = tc.get("function", {})
                            events.append(SessionEvent(
                                event_type=EventType.TOOL_CALL,
                                content=str(fn.get("arguments", "")),
                                tool_name=fn.get("name", ""),
                                tool_args={"arguments": fn.get("arguments", "")},
                            ))
                            # Add output if present
                            output = fn.get("output")
                            if output:
                                error_msg = None
                                if any(
                                    kw in str(output).lower()
                                    for kw in ["error", "exception", "failed"]
                                ):
                                    error_msg = str(output)[:500]
                                    has_error = True
                                events.append(SessionEvent(
                                    event_type=EventType.TOOL_RESULT,
                                    content=str(output),
                                    tool_name=fn.get("name", ""),
                                    error_message=error_msg,
                                ))
                        elif tc_type == "code_interpreter":
                            ci = tc.get("code_interpreter", {})
                            events.append(SessionEvent(
                                event_type=EventType.TOOL_CALL,
                                content=ci.get("input", ""),
                                tool_name="code_interpreter",
                            ))
                        elif tc_type == "file_search":
                            events.append(SessionEvent(
                                event_type=EventType.TOOL_CALL,
                                content="file_search",
                                tool_name="file_search",
                            ))

                elif step_type == "message_creation":
                    msg_id = step_details.get("message_creation", {}).get("message_id", "")
                    events.append(SessionEvent(
                        event_type=EventType.ASSISTANT_MESSAGE,
                        content=f"[message: {msg_id}]",
                    ))

            # Run object
            elif obj_type == "thread.run":
                if record.get("last_error"):
                    err = record["last_error"]
                    has_error = True
                    events.append(SessionEvent(
                        event_type=EventType.ERROR,
                        content=str(err),
                        error_message=f"{err.get('code', '')}: {err.get('message', '')}",
                    ))

        # Determine outcome
        if has_error or status == "failed":
            outcome = SessionOutcome.FAILURE
        elif status == "completed":
            outcome = SessionOutcome.SUCCESS
        elif status in ("cancelled", "expired"):
            outcome = SessionOutcome.ABANDONED
        else:
            outcome = SessionOutcome.UNKNOWN

        session_id = thread_id or f"oai_{path.stem}"

        return [AgentSession(
            session_id=session_id,
            framework=AgentFramework.GENERIC,  # Using GENERIC since no OPENAI enum yet
            model=model,
            events=events,
            outcome=outcome,
            total_turns=sum(1 for e in events if e.event_type == EventType.USER_MESSAGE),
            metadata={
                "source_file": str(path),
                "assistant_id": assistant_id or "",
                "parser": "openai_assistants",
            },
        )]
