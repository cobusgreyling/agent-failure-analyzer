"""Context-overflow detectors."""

from __future__ import annotations

from ...models import AgentSession, EventType, FailureInstance
from ...taxonomy import FailureCategory, FailureSubcategory, Severity
from ..detector_config import DetectorConfig
from ._keywords import CONTEXT_WINDOW_KEYWORDS


def detect(session: AgentSession, config: DetectorConfig) -> list[FailureInstance]:
    failures: list[FailureInstance] = []
    events = session.events

    for i, event in enumerate(events):
        if event.event_type == EventType.ERROR and event.error_message:
            msg = event.error_message.lower()
            if any(kw in msg for kw in CONTEXT_WINDOW_KEYWORDS):
                failures.append(FailureInstance(
                    category=FailureCategory.CONTEXT_OVERFLOW,
                    subcategory=FailureSubcategory.CONTEXT_WINDOW_EXCEEDED,
                    severity=Severity.CRITICAL,
                    description="Session hit context window limit.",
                    evidence=[event.error_message],
                    event_indices=[i],
                    confidence=0.95,
                ))

    verbose_indices = [
        i for i, event in enumerate(events)
        if event.event_type == EventType.TOOL_RESULT
        and len(event.content) > config.verbose_tool_output_chars
    ]

    if len(verbose_indices) >= config.verbose_tool_output_count:
        failures.append(FailureInstance(
            category=FailureCategory.CONTEXT_OVERFLOW,
            subcategory=FailureSubcategory.VERBOSE_TOOL_OUTPUT,
            severity=Severity.MEDIUM,
            description=(
                f"{len(verbose_indices)} tool outputs exceeded "
                f"{config.verbose_tool_output_chars} chars, "
                "consuming significant context budget."
            ),
            evidence=[
                f"Event {i}: {len(events[i].content)} chars"
                for i in verbose_indices[:5]
            ],
            event_indices=verbose_indices,
            confidence=0.7,
        ))

    if session.total_tokens and session.total_tokens > config.total_tokens_threshold:
        failures.append(FailureInstance(
            category=FailureCategory.CONTEXT_OVERFLOW,
            subcategory=FailureSubcategory.STALE_CONTEXT_POLLUTION,
            severity=Severity.HIGH,
            description=(
                f"Session consumed {session.total_tokens:,} tokens"
                " — likely context pressure."
            ),
            evidence=[f"Total tokens: {session.total_tokens:,}"],
            event_indices=[],
            confidence=0.6,
        ))

    return failures
