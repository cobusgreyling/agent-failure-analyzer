"""Tool-misuse detectors."""

from __future__ import annotations

from collections import Counter

from ...models import AgentSession, EventType, FailureInstance
from ...taxonomy import FailureCategory, FailureSubcategory, Severity
from ..detector_config import DetectorConfig
from ._keywords import INVALID_TOOL_ARGS_KEYWORDS, TOOL_NOT_FOUND_KEYWORDS


def detect(session: AgentSession, config: DetectorConfig) -> list[FailureInstance]:
    failures: list[FailureInstance] = []
    events = session.events

    tool_errors: list[tuple[int, str]] = [
        (i, event.tool_name or "unknown")
        for i, event in enumerate(events)
        if event.event_type == EventType.TOOL_RESULT and event.error_message
    ]

    tool_error_counts = Counter(name for _, name in tool_errors)
    for tool_name, count in tool_error_counts.items():
        if count >= config.repeated_tool_failure_count:
            indices = [i for i, n in tool_errors if n == tool_name]
            failures.append(FailureInstance(
                category=FailureCategory.TOOL_MISUSE,
                subcategory=FailureSubcategory.REPEATED_TOOL_FAILURE,
                severity=Severity.HIGH,
                description=(
                    f"Tool '{tool_name}' failed {count} times"
                    " without successful recovery."
                ),
                evidence=[
                    events[idx].error_message or events[idx].content[:200]
                    for idx in indices[:3]
                ],
                event_indices=indices,
                confidence=0.85,
            ))

    for i, event in enumerate(events):
        if event.event_type == EventType.TOOL_RESULT and event.error_message:
            msg = event.error_message.lower()
            if any(kw in msg for kw in INVALID_TOOL_ARGS_KEYWORDS):
                failures.append(FailureInstance(
                    category=FailureCategory.TOOL_MISUSE,
                    subcategory=FailureSubcategory.INVALID_TOOL_ARGS,
                    severity=Severity.MEDIUM,
                    description=f"Tool call at event {i} received invalid arguments.",
                    evidence=[event.error_message[:300]],
                    event_indices=[i],
                    confidence=0.8,
                ))

    for i, event in enumerate(events):
        if event.event_type in (EventType.ERROR, EventType.TOOL_RESULT):
            msg = (event.error_message or event.content).lower()
            if any(kw in msg for kw in TOOL_NOT_FOUND_KEYWORDS):
                failures.append(FailureInstance(
                    category=FailureCategory.TOOL_MISUSE,
                    subcategory=FailureSubcategory.TOOL_NOT_FOUND,
                    severity=Severity.HIGH,
                    description=f"Agent attempted to use a non-existent tool at event {i}.",
                    evidence=[(event.error_message or event.content)[:300]],
                    event_indices=[i],
                    confidence=0.9,
                ))

    return failures
