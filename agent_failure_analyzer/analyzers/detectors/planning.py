"""Planning-failure detectors."""

from __future__ import annotations

from ...models import AgentSession, EventType, FailureInstance
from ...taxonomy import FailureCategory, FailureSubcategory, Severity
from ..detector_config import DetectorConfig
from ._keywords import PLAN_MENTION_KEYWORDS


def detect(session: AgentSession, config: DetectorConfig) -> list[FailureInstance]:
    failures: list[FailureInstance] = []
    events = session.events

    tool_call_count = sum(1 for e in events if e.event_type == EventType.TOOL_CALL)
    error_count = sum(
        1 for e in events
        if e.event_type == EventType.ERROR
        or (e.event_type == EventType.TOOL_RESULT and e.error_message)
    )

    if (
        tool_call_count > config.overambitious_tool_calls
        and error_count > tool_call_count * config.overambitious_error_rate
    ):
        failures.append(FailureInstance(
            category=FailureCategory.PLANNING_FAILURE,
            subcategory=FailureSubcategory.OVERAMBITIOUS_PLAN,
            severity=Severity.HIGH,
            description=(
                f"Session had {tool_call_count} tool calls with {error_count} errors "
                f"({error_count/tool_call_count:.0%} failure rate) — "
                f"suggests an overambitious or poorly planned approach."
            ),
            evidence=[],
            event_indices=[],
            confidence=0.6,
        ))

    n = config.no_plan_first_n
    if len(events) > n:
        first_n = events[:n]
        has_thinking = any(e.event_type == EventType.THINKING for e in first_n)
        has_plan_mention = any(
            e.event_type == EventType.ASSISTANT_MESSAGE
            and any(kw in e.content.lower() for kw in PLAN_MENTION_KEYWORDS)
            for e in first_n
        )
        immediate_tools = sum(
            1 for e in first_n if e.event_type == EventType.TOOL_CALL
        )
        if (
            immediate_tools >= config.no_plan_tool_threshold
            and not has_thinking
            and not has_plan_mention
        ):
            failures.append(FailureInstance(
                category=FailureCategory.PLANNING_FAILURE,
                subcategory=FailureSubcategory.NO_PLAN,
                severity=Severity.LOW,
                description=(
                    f"Agent made {config.no_plan_tool_threshold}+ tool calls "
                    f"in the first {n} events without planning."
                ),
                evidence=[],
                event_indices=list(range(n)),
                confidence=0.5,
            ))

    return failures
