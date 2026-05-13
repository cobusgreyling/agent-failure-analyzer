"""Safety-refusal detectors."""

from __future__ import annotations

from ...models import AgentSession, EventType, FailureInstance
from ...taxonomy import FailureCategory, FailureSubcategory, Severity
from ..detector_config import DetectorConfig
from ._keywords import REFUSAL_OVERRIDE_KEYWORDS, REFUSAL_PATTERNS


def detect(session: AgentSession, config: DetectorConfig) -> list[FailureInstance]:
    failures: list[FailureInstance] = []
    events = session.events

    for i, event in enumerate(events):
        if event.event_type != EventType.ASSISTANT_MESSAGE:
            continue
        content_lower = event.content.lower()
        if not any(p in content_lower for p in REFUSAL_PATTERNS):
            continue

        is_false_positive = False
        for j in range(i + 1, min(i + 3, len(events))):
            if events[j].event_type == EventType.USER_MESSAGE:
                user_msg = events[j].content.lower()
                if any(kw in user_msg for kw in REFUSAL_OVERRIDE_KEYWORDS):
                    is_false_positive = True
                    break

        subcategory = (
            FailureSubcategory.FALSE_POSITIVE_REFUSAL
            if is_false_positive
            else FailureSubcategory.APPROPRIATE_REFUSAL
        )
        severity = Severity.MEDIUM if is_false_positive else Severity.INFO

        failures.append(FailureInstance(
            category=FailureCategory.SAFETY_REFUSAL,
            subcategory=subcategory,
            severity=severity,
            description=(
                "Agent refused a request"
                + (" (likely false positive)" if is_false_positive else "")
                + "."
            ),
            evidence=[event.content[:300]],
            event_indices=[i],
            confidence=0.6 if is_false_positive else 0.5,
        ))

    return failures
