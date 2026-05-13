"""
Failure detectors — one module per failure category.

Each module exposes a ``detect(session, config) -> list[FailureInstance]``
function. The orchestrator in ``classifier.py`` calls them in order. Adding
a new failure category is just: drop a new module here and append it to
``ALL_DETECTORS``.
"""

from __future__ import annotations

from collections.abc import Callable

from ...models import AgentSession, FailureInstance
from ..detector_config import DetectorConfig
from . import (
    context_overflow,
    error_cascade,
    hallucinations,
    instruction_drift,
    loops,
    planning,
    resource_exhaustion,
    safety_refusal,
    tool_misuse,
)

Detector = Callable[[AgentSession, DetectorConfig], list[FailureInstance]]

ALL_DETECTORS: tuple[Detector, ...] = (
    context_overflow.detect,
    tool_misuse.detect,
    loops.detect,
    hallucinations.detect,
    error_cascade.detect,
    instruction_drift.detect,
    planning.detect,
    resource_exhaustion.detect,
    safety_refusal.detect,
)

__all__ = ["ALL_DETECTORS", "Detector"]
