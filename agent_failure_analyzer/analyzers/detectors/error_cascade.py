"""Error-cascade detectors."""

from __future__ import annotations

from ...models import AgentSession, EventType, FailureInstance
from ...taxonomy import FailureCategory, FailureSubcategory, Severity
from ..detector_config import DetectorConfig


def _is_error(event) -> bool:
    return (
        event.event_type == EventType.ERROR
        or (event.event_type == EventType.TOOL_RESULT and event.error_message)
    )


def detect(session: AgentSession, config: DetectorConfig) -> list[FailureInstance]:
    failures: list[FailureInstance] = []
    events = session.events
    min_streak = config.error_cascade_min_streak

    error_streak: list[int] = []
    for i, event in enumerate(events):
        if _is_error(event):
            error_streak.append(i)
        else:
            if len(error_streak) >= min_streak:
                failures.append(FailureInstance(
                    category=FailureCategory.ERROR_CASCADE,
                    subcategory=FailureSubcategory.CASCADING_TOOL_ERRORS,
                    severity=Severity.HIGH,
                    description=f"Cascade of {len(error_streak)} consecutive errors.",
                    evidence=[
                        (events[idx].error_message or events[idx].content)[:150]
                        for idx in error_streak[:5]
                    ],
                    event_indices=error_streak,
                    confidence=0.85,
                ))
            error_streak = []

    if len(error_streak) >= min_streak:
        failures.append(FailureInstance(
            category=FailureCategory.ERROR_CASCADE,
            subcategory=FailureSubcategory.CASCADING_TOOL_ERRORS,
            severity=Severity.CRITICAL,
            description=(
                f"Session ended with a cascade of {len(error_streak)} "
                f"consecutive errors."
            ),
            evidence=[
                (events[idx].error_message or events[idx].content)[:150]
                for idx in error_streak[:5]
            ],
            event_indices=error_streak,
            confidence=0.9,
        ))

    for i, event in enumerate(events):
        if event.event_type == EventType.ERROR and event.error_message:
            for j in range(i + 1, min(i + 3, len(events))):
                next_evt = events[j]
                if next_evt.event_type == EventType.ASSISTANT_MESSAGE:
                    error_keywords = set(event.error_message.lower().split()[:5])
                    response_words = set(next_evt.content.lower().split())
                    overlap = error_keywords & response_words
                    if (
                        len(overlap) < config.misinterpreted_overlap_threshold
                        and len(error_keywords) > 3
                    ):
                        failures.append(FailureInstance(
                            category=FailureCategory.ERROR_CASCADE,
                            subcategory=FailureSubcategory.MISINTERPRETED_ERROR,
                            severity=Severity.MEDIUM,
                            description=(
                                "Agent's response after an error doesn't address "
                                "the error content."
                            ),
                            evidence=[
                                f"Error: {event.error_message[:150]}",
                                f"Response: {next_evt.content[:150]}",
                            ],
                            event_indices=[i, j],
                            confidence=0.5,
                        ))
                    break

    return failures
