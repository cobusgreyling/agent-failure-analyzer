"""Instruction-drift detectors."""

from __future__ import annotations

import re

from ...models import AgentSession, EventType, FailureInstance
from ...taxonomy import FailureCategory, FailureSubcategory, Severity
from ..detector_config import DetectorConfig
from ._keywords import (
    CONSTRAINT_COMPLAINT_KEYWORDS,
    CONSTRAINT_PATTERNS,
    DRIFT_KEYWORDS,
)


def detect(session: AgentSession, config: DetectorConfig) -> list[FailureInstance]:
    failures: list[FailureInstance] = []
    events = session.events

    for i, event in enumerate(events):
        if event.event_type == EventType.USER_MESSAGE:
            content_lower = event.content.lower()
            for kw in DRIFT_KEYWORDS:
                if kw in content_lower:
                    failures.append(FailureInstance(
                        category=FailureCategory.INSTRUCTION_DRIFT,
                        subcategory=FailureSubcategory.GOAL_FORGOTTEN,
                        severity=Severity.HIGH,
                        description="User indicated the agent deviated from the goal.",
                        evidence=[event.content[:300]],
                        event_indices=[i],
                        confidence=0.75,
                    ))
                    break

    user_constraints: list[tuple[int, str]] = []
    for i, event in enumerate(events):
        if event.event_type == EventType.USER_MESSAGE:
            for pattern in CONSTRAINT_PATTERNS:
                match = re.search(pattern, event.content.lower())
                if match:
                    user_constraints.append((i, match.group()))

    if user_constraints:
        for i, event in enumerate(events):
            if event.event_type == EventType.USER_MESSAGE and i > user_constraints[0][0]:
                content_lower = event.content.lower()
                if any(kw in content_lower for kw in CONSTRAINT_COMPLAINT_KEYWORDS):
                    failures.append(FailureInstance(
                        category=FailureCategory.INSTRUCTION_DRIFT,
                        subcategory=FailureSubcategory.CONSTRAINT_VIOLATED,
                        severity=Severity.HIGH,
                        description="Agent violated a user-specified constraint.",
                        evidence=[
                            f"Constraint: {user_constraints[0][1]}",
                            f"Complaint: {event.content[:200]}",
                        ],
                        event_indices=[user_constraints[0][0], i],
                        confidence=0.7,
                    ))

    return failures
