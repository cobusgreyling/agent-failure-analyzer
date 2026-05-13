"""Resource-exhaustion detectors (rate / cost / time limits)."""

from __future__ import annotations

from ...models import AgentSession, EventType, FailureInstance
from ...taxonomy import FailureCategory, FailureSubcategory, Severity
from ..detector_config import DetectorConfig
from ._keywords import COST_LIMIT_KEYWORDS, RATE_LIMIT_KEYWORDS, TIMEOUT_KEYWORDS


def detect(session: AgentSession, config: DetectorConfig) -> list[FailureInstance]:
    failures: list[FailureInstance] = []

    for i, event in enumerate(session.events):
        if event.event_type != EventType.ERROR or not event.error_message:
            continue
        msg = event.error_message.lower()

        if any(kw in msg for kw in RATE_LIMIT_KEYWORDS):
            failures.append(FailureInstance(
                category=FailureCategory.RESOURCE_EXHAUSTION,
                subcategory=FailureSubcategory.RATE_LIMIT_HIT,
                severity=Severity.HIGH,
                description="Session hit API rate limit.",
                evidence=[event.error_message[:200]],
                event_indices=[i],
                confidence=0.95,
            ))

        if any(kw in msg for kw in COST_LIMIT_KEYWORDS):
            failures.append(FailureInstance(
                category=FailureCategory.RESOURCE_EXHAUSTION,
                subcategory=FailureSubcategory.COST_LIMIT_HIT,
                severity=Severity.CRITICAL,
                description="Session hit cost/spending limit.",
                evidence=[event.error_message[:200]],
                event_indices=[i],
                confidence=0.9,
            ))

        if any(kw in msg for kw in TIMEOUT_KEYWORDS):
            failures.append(FailureInstance(
                category=FailureCategory.RESOURCE_EXHAUSTION,
                subcategory=FailureSubcategory.TIME_LIMIT_HIT,
                severity=Severity.HIGH,
                description="Operation timed out.",
                evidence=[event.error_message[:200]],
                event_indices=[i],
                confidence=0.85,
            ))

    return failures
