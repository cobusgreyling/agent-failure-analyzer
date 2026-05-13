"""
Real-time streaming analysis.

Reads agent session events from stdin line-by-line (JSON or JSONL),
classifies failures on the fly, and prints alerts in real time.
"""

from __future__ import annotations

import json
import sys

from rich.console import Console

from .analyzers.classifier import FailureClassifier
from .models import (
    AgentFramework,
    AgentSession,
    EventType,
    SessionEvent,
    SessionOutcome,
)
from .reports.terminal_report import SEVERITY_COLORS


def _parse_event(line: str) -> SessionEvent | None:
    """Try to parse a JSON line into a SessionEvent."""
    try:
        data = json.loads(line.strip())
    except (json.JSONDecodeError, ValueError):
        return None

    if not isinstance(data, dict):
        return None

    # Try to detect event type from common field names
    event_type = EventType.SYSTEM
    role = (data.get("role") or data.get("type") or "").lower()
    if role in ("user", "human"):
        event_type = EventType.USER_MESSAGE
    elif role in ("assistant", "ai", "bot"):
        event_type = EventType.ASSISTANT_MESSAGE
    elif role in ("tool", "function"):
        event_type = EventType.TOOL_RESULT
    elif "tool_call" in data or "function_call" in data:
        event_type = EventType.TOOL_CALL
    elif data.get("error") or data.get("is_error"):
        event_type = EventType.ERROR

    content = data.get("content", data.get("text", data.get("message", "")))
    if isinstance(content, (list, dict)):
        content = json.dumps(content)

    return SessionEvent(
        event_type=event_type,
        content=str(content),
        tool_name=data.get("tool_name", data.get("name")),
        tool_args=data.get("tool_args", data.get("arguments")),
        error_message=data.get("error", data.get("error_message")),
    )


def stream_analyze(
    input_stream=None,
    console: Console | None = None,
    alert_severity: str = "medium",
) -> None:
    """Read events from a stream, classify in real-time, print alerts."""
    console = console or Console(stderr=True)
    classifier = FailureClassifier()
    stream = input_stream or sys.stdin

    severity_order = ["info", "low", "medium", "high", "critical"]
    min_sev_idx = severity_order.index(alert_severity)

    events: list[SessionEvent] = []
    event_count = 0
    failure_count = 0

    console.print("[bold]Streaming analysis started[/bold] (reading from stdin)")
    console.print(f"[dim]Alert threshold: {alert_severity}+[/dim]\n")

    try:
        for line in stream:
            line = line.strip()
            if not line:
                continue

            event = _parse_event(line)
            if event is None:
                continue

            events.append(event)
            event_count += 1

            # Run classification on the accumulated session
            session = AgentSession(
                session_id="stream",
                framework=AgentFramework.GENERIC,
                events=events,
                outcome=SessionOutcome.UNKNOWN,
            )

            failures = classifier.classify(session)

            # Check for new failures above threshold
            new_failures = failures[failure_count:]
            for f in new_failures:
                sev_idx = severity_order.index(f.severity.value)
                if sev_idx >= min_sev_idx:
                    sev_color = SEVERITY_COLORS.get(f.severity, "")
                    console.print(
                        f"[{sev_color}][{f.severity.value.upper()}][/{sev_color}] "
                        f"Event #{event_count}: {f.subcategory.value} — "
                        f"{f.description[:80]}"
                    )

            failure_count = len(failures)

            # Print progress periodically
            if event_count % 50 == 0:
                console.print(
                    f"[dim]... {event_count} events processed, "
                    f"{failure_count} failures detected[/dim]"
                )

    except KeyboardInterrupt:
        pass

    console.print(
        f"\n[bold]Stream complete:[/bold] {event_count} events, "
        f"{failure_count} failures detected"
    )
