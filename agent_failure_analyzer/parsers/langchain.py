"""Parser for LangChain / LangSmith trace logs.

Handles both LangSmith exported JSON traces and LangChain callback-based logs.
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


class LangChainParser(BaseParser):
    """Parse LangChain / LangSmith session traces."""

    def can_parse(self, path: Path) -> bool:
        if path.is_file() and path.suffix == ".json":
            try:
                data = self._read_json(path)
                if isinstance(data, dict):
                    return any(
                        k in data
                        for k in ["runs", "traces", "lc_kwargs", "callback_events"]
                    )
                if isinstance(data, list) and data:
                    return any(
                        k in data[0]
                        for k in [
                            "run_type",
                            "name",
                            "inputs",
                            "serialized",
                        ]
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

        # LangSmith export format: {"runs": [...]}
        if isinstance(data, dict) and "runs" in data:
            return self._parse_runs(data["runs"], path)

        # LangSmith trace list
        if isinstance(data, dict) and "traces" in data:
            return self._parse_runs(data["traces"], path)

        # Direct list of runs/events
        if isinstance(data, list):
            return self._parse_runs(data, path)

        # Callback events format
        if isinstance(data, dict) and "callback_events" in data:
            return self._parse_callback_events(data["callback_events"], path)

        return []

    def _parse_runs(self, runs: list[dict], path: Path) -> list[AgentSession]:
        if not runs:
            return []

        events: list[SessionEvent] = []
        model = None
        total_tokens = 0

        for run in runs:
            run_events = self._run_to_events(run)
            events.extend(run_events)

            # Extract model info
            if "extra" in run and "invocation_params" in run.get("extra", {}):
                model = run["extra"]["invocation_params"].get("model_name", model)

            # Token usage
            if "total_tokens" in run.get("extra", {}).get("token_usage", {}):
                total_tokens += run["extra"]["token_usage"]["total_tokens"]

        outcome = self._infer_outcome(events, runs)

        session = AgentSession(
            session_id=runs[0].get("session_id", path.stem) if runs else path.stem,
            framework=AgentFramework.LANGCHAIN,
            model=model,
            start_time=self._parse_time(runs[0].get("start_time")) if runs else None,
            end_time=self._parse_time(runs[-1].get("end_time")) if runs else None,
            events=events,
            outcome=outcome,
            total_tokens=total_tokens if total_tokens > 0 else None,
            total_turns=sum(1 for e in events if e.event_type == EventType.USER_MESSAGE),
            metadata={"source_file": str(path)},
        )
        return [session]

    def _run_to_events(self, run: dict) -> list[SessionEvent]:
        events = []
        run_type = run.get("run_type", "")
        timestamp = self._parse_time(run.get("start_time"))
        error = run.get("error")

        if run_type == "llm":
            # Input
            inputs = run.get("inputs", {})
            prompts = inputs.get("prompts", inputs.get("messages", []))
            if isinstance(prompts, list):
                for msg in prompts:
                    if isinstance(msg, dict):
                        role = msg.get("role", msg.get("type", "user"))
                        content = msg.get("content", str(msg))
                    else:
                        role = "user"
                        content = str(msg)

                    evt_type = (
                        EventType.USER_MESSAGE if role in ("user", "human")
                        else EventType.ASSISTANT_MESSAGE if role in ("assistant", "ai")
                        else EventType.SYSTEM
                    )
                    events.append(SessionEvent(
                        timestamp=timestamp,
                        event_type=evt_type,
                        content=content,
                    ))

            # Output
            outputs = run.get("outputs", {})
            if outputs:
                generations = outputs.get("generations", [[]])
                for gen_list in generations:
                    for gen in gen_list if isinstance(gen_list, list) else [gen_list]:
                        if isinstance(gen, dict):
                            events.append(SessionEvent(
                                timestamp=self._parse_time(run.get("end_time")),
                                event_type=EventType.ASSISTANT_MESSAGE,
                                content=gen.get("text", gen.get("message", {}).get("content", "")),
                            ))

        elif run_type == "tool":
            tool_name = run.get("name", "unknown_tool")
            events.append(SessionEvent(
                timestamp=timestamp,
                event_type=EventType.TOOL_CALL,
                content=str(run.get("inputs", "")),
                tool_name=tool_name,
                tool_args=run.get("inputs") if isinstance(run.get("inputs"), dict) else None,
            ))
            if run.get("outputs"):
                events.append(SessionEvent(
                    timestamp=self._parse_time(run.get("end_time")),
                    event_type=EventType.TOOL_RESULT,
                    content=str(run.get("outputs", "")),
                    tool_name=tool_name,
                    error_message=error,
                ))

        elif run_type == "chain":
            # Recurse into child runs
            for child in run.get("child_runs", []):
                events.extend(self._run_to_events(child))

        if error:
            events.append(SessionEvent(
                timestamp=self._parse_time(run.get("end_time")),
                event_type=EventType.ERROR,
                content=error,
                error_message=error,
            ))

        return events

    def _parse_callback_events(
        self, callback_events: list[dict], path: Path
    ) -> list[AgentSession]:
        events: list[SessionEvent] = []
        for cb in callback_events:
            event_name = cb.get("event", "")
            timestamp = self._parse_time(cb.get("timestamp"))

            if "on_llm_start" in event_name:
                events.append(SessionEvent(
                    timestamp=timestamp,
                    event_type=EventType.SYSTEM,
                    content=f"LLM started: {cb.get('name', '')}",
                ))
            elif "on_llm_end" in event_name:
                events.append(SessionEvent(
                    timestamp=timestamp,
                    event_type=EventType.ASSISTANT_MESSAGE,
                    content=str(cb.get("response", "")),
                ))
            elif "on_tool_start" in event_name:
                events.append(SessionEvent(
                    timestamp=timestamp,
                    event_type=EventType.TOOL_CALL,
                    content=str(cb.get("input", "")),
                    tool_name=cb.get("name"),
                ))
            elif "on_tool_end" in event_name:
                events.append(SessionEvent(
                    timestamp=timestamp,
                    event_type=EventType.TOOL_RESULT,
                    content=str(cb.get("output", "")),
                    tool_name=cb.get("name"),
                ))
            elif "on_tool_error" in event_name or "error" in event_name:
                events.append(SessionEvent(
                    timestamp=timestamp,
                    event_type=EventType.ERROR,
                    content=str(cb.get("error", "")),
                    error_message=str(cb.get("error", "")),
                ))

        session = AgentSession(
            session_id=path.stem,
            framework=AgentFramework.LANGCHAIN,
            events=events,
            outcome=self._infer_outcome(events, []),
            total_turns=sum(1 for e in events if e.event_type == EventType.USER_MESSAGE),
            metadata={"source_file": str(path)},
        )
        return [session]

    @staticmethod
    def _parse_time(val) -> datetime | None:
        if val is None:
            return None
        if isinstance(val, datetime):
            return val
        try:
            return datetime.fromisoformat(str(val))
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _infer_outcome(
        events: list[SessionEvent], runs: list[dict]
    ) -> SessionOutcome:
        # Check for errors in runs
        for run in runs:
            if run.get("error") and run.get("run_type") in ("chain", "agent"):
                return SessionOutcome.FAILURE

        error_events = [e for e in events if e.event_type == EventType.ERROR]
        if len(error_events) >= 2:
            return SessionOutcome.FAILURE

        if events and events[-1].event_type == EventType.ERROR:
            return SessionOutcome.FAILURE

        if len(events) < 3:
            return SessionOutcome.ABANDONED

        return SessionOutcome.UNKNOWN
