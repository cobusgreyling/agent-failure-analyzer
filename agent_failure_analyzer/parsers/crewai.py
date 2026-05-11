"""Parser for CrewAI session logs.

CrewAI logs task delegations, agent actions, and crew-level outputs.
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


class CrewAIParser(BaseParser):
    """Parse CrewAI JSON session logs."""

    def can_parse(self, path: Path) -> bool:
        if path.is_file() and path.suffix == ".json":
            try:
                data = self._read_json(path)
                if isinstance(data, dict):
                    return any(
                        k in data for k in ["crew", "tasks", "agents", "crew_output"]
                    )
            except Exception:
                return False
        if path.is_dir():
            return any(p.suffix == ".json" for p in path.rglob("*.json"))
        return False

    def parse(self, path: Path) -> list[AgentSession]:
        if path.is_dir():
            sessions = []
            for json_file in sorted(path.rglob("*.json")):
                try:
                    sessions.extend(self._parse_file(json_file))
                except Exception:
                    continue
            return sessions
        return self._parse_file(path)

    def _parse_file(self, path: Path) -> list[AgentSession]:
        data = self._read_json(path)
        if not isinstance(data, dict):
            return []

        events: list[SessionEvent] = []
        total_tokens = 0

        # Parse tasks and their execution
        tasks = data.get("tasks", [])
        for task in tasks:
            events.extend(self._task_to_events(task))
            total_tokens += task.get("tokens_used", 0)

        # Parse agent interactions if present
        for agent_log in data.get("agent_logs", []):
            events.extend(self._agent_log_to_events(agent_log))

        # Parse crew output
        crew_output = data.get("crew_output", data.get("output", ""))
        if crew_output:
            events.append(SessionEvent(
                event_type=EventType.ASSISTANT_MESSAGE,
                content=str(crew_output),
                metadata={"source": "crew_output"},
            ))

        outcome = self._infer_outcome(data, events)

        session = AgentSession(
            session_id=data.get("crew_id", data.get("id", path.stem)),
            framework=AgentFramework.CREWAI,
            model=data.get("model", data.get("llm")),
            start_time=self._parse_time(data.get("start_time")),
            end_time=self._parse_time(data.get("end_time")),
            events=events,
            outcome=outcome,
            total_tokens=total_tokens if total_tokens > 0 else None,
            total_turns=len(tasks),
            metadata={
                "source_file": str(path),
                "crew_name": data.get("crew", {}).get("name", ""),
                "num_agents": len(data.get("agents", [])),
            },
        )
        return [session]

    def _task_to_events(self, task: dict) -> list[SessionEvent]:
        events = []
        timestamp = self._parse_time(task.get("start_time"))

        # Task assignment
        events.append(SessionEvent(
            timestamp=timestamp,
            event_type=EventType.SYSTEM,
            content=(
                f"Task assigned to {task.get('agent', 'unknown')}:"
                f" {task.get('description', '')}"
            ),
            metadata={"task_id": task.get("id", ""), "agent": task.get("agent", "")},
        ))

        # Tool calls within the task
        for tool_call in task.get("tool_calls", []):
            events.append(SessionEvent(
                timestamp=self._parse_time(tool_call.get("timestamp")),
                event_type=EventType.TOOL_CALL,
                content=str(tool_call.get("input", "")),
                tool_name=tool_call.get("tool", tool_call.get("name")),
                tool_args=(
                    tool_call.get("input")
                    if isinstance(tool_call.get("input"), dict)
                    else None
                ),
            ))
            if "output" in tool_call or "result" in tool_call:
                error = tool_call.get("error")
                events.append(SessionEvent(
                    timestamp=self._parse_time(tool_call.get("timestamp")),
                    event_type=EventType.TOOL_RESULT,
                    content=str(tool_call.get("output", tool_call.get("result", ""))),
                    tool_name=tool_call.get("tool", tool_call.get("name")),
                    error_message=error,
                ))

        # Task output
        if task.get("output") or task.get("result"):
            events.append(SessionEvent(
                timestamp=self._parse_time(task.get("end_time")),
                event_type=EventType.ASSISTANT_MESSAGE,
                content=str(task.get("output", task.get("result", ""))),
            ))

        # Task error
        if task.get("error"):
            events.append(SessionEvent(
                timestamp=self._parse_time(task.get("end_time")),
                event_type=EventType.ERROR,
                content=str(task.get("error")),
                error_message=str(task.get("error")),
            ))

        return events

    def _agent_log_to_events(self, agent_log: dict) -> list[SessionEvent]:
        events = []

        for entry in agent_log.get("entries", []):
            timestamp = self._parse_time(entry.get("timestamp"))
            entry_type = entry.get("type", "")

            if entry_type == "thought":
                events.append(SessionEvent(
                    timestamp=timestamp,
                    event_type=EventType.THINKING,
                    content=entry.get("content", ""),
                ))
            elif entry_type == "action":
                events.append(SessionEvent(
                    timestamp=timestamp,
                    event_type=EventType.TOOL_CALL,
                    content=str(entry.get("input", "")),
                    tool_name=entry.get("tool"),
                ))
            elif entry_type == "observation":
                events.append(SessionEvent(
                    timestamp=timestamp,
                    event_type=EventType.TOOL_RESULT,
                    content=entry.get("content", ""),
                ))
            elif entry_type == "error":
                events.append(SessionEvent(
                    timestamp=timestamp,
                    event_type=EventType.ERROR,
                    content=entry.get("content", ""),
                    error_message=entry.get("content", ""),
                ))

        return events

    @staticmethod
    def _parse_time(val) -> datetime | None:
        if val is None:
            return None
        try:
            return datetime.fromisoformat(str(val))
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _infer_outcome(data: dict, events: list[SessionEvent]) -> SessionOutcome:
        status = data.get("status", "").lower()
        if status == "success":
            return SessionOutcome.SUCCESS
        if status in ("failed", "error"):
            return SessionOutcome.FAILURE

        error_events = [e for e in events if e.event_type == EventType.ERROR]
        if error_events:
            return SessionOutcome.FAILURE

        if data.get("crew_output") or data.get("output"):
            return SessionOutcome.SUCCESS

        return SessionOutcome.UNKNOWN
