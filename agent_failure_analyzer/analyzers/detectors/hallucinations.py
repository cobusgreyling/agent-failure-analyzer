"""Hallucination detectors."""

from __future__ import annotations

from ...models import AgentSession, EventType, FailureInstance
from ...taxonomy import FailureCategory, FailureSubcategory, Severity
from ..detector_config import DetectorConfig
from ._keywords import (
    FILE_NOT_FOUND_KEYWORDS,
    FILE_TOOL_NAMES,
    NONEXISTENT_DEPENDENCY_KEYWORDS,
)


def detect(session: AgentSession, config: DetectorConfig) -> list[FailureInstance]:
    failures: list[FailureInstance] = []
    events = session.events

    for i, event in enumerate(events):
        if event.event_type == EventType.TOOL_CALL and event.tool_name in FILE_TOOL_NAMES:
            if i + 1 < len(events):
                next_evt = events[i + 1]
                if next_evt.error_message and any(
                    kw in next_evt.error_message.lower() for kw in FILE_NOT_FOUND_KEYWORDS
                ):
                    path_str = ""
                    if event.tool_args and isinstance(event.tool_args, dict):
                        path_str = str(
                            event.tool_args.get("path", event.tool_args.get("file_path", ""))
                        )
                    failures.append(FailureInstance(
                        category=FailureCategory.HALLUCINATION,
                        subcategory=FailureSubcategory.FABRICATED_FILE_PATH,
                        severity=Severity.MEDIUM,
                        description=(
                            f"Agent referenced non-existent file: {path_str or 'unknown'}"
                        ),
                        evidence=[event.content[:200], next_evt.error_message[:200]],
                        event_indices=[i, i + 1],
                        confidence=0.8,
                    ))

    for i, event in enumerate(events):
        if event.event_type == EventType.ASSISTANT_MESSAGE:
            for j in range(i + 1, min(i + 5, len(events))):
                next_evt = events[j]
                if next_evt.error_message and any(
                    kw in next_evt.error_message.lower()
                    for kw in NONEXISTENT_DEPENDENCY_KEYWORDS
                ):
                    failures.append(FailureInstance(
                        category=FailureCategory.HALLUCINATION,
                        subcategory=FailureSubcategory.NONEXISTENT_DEPENDENCY,
                        severity=Severity.HIGH,
                        description="Agent referenced a non-existent package or module.",
                        evidence=[event.content[:200], next_evt.error_message[:200]],
                        event_indices=[i, j],
                        confidence=0.75,
                    ))
                    break

    return failures
