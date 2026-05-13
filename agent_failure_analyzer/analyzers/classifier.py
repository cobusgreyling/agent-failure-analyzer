"""
Failure classifier — thin orchestrator over per-category detectors.

The detection logic lives in ``detectors/<category>.py``; this module just
wires them together and exposes a ``FailureClassifier`` class for callers
that prefer an object-oriented API.
"""

from __future__ import annotations

from ..models import AgentSession, FailureInstance
from .detector_config import DetectorConfig
from .detectors import ALL_DETECTORS


class FailureClassifier:
    """Classifies failures in a normalized agent session."""

    def __init__(self, config: DetectorConfig | None = None) -> None:
        self.config = config or DetectorConfig()

    def classify(self, session: AgentSession) -> list[FailureInstance]:
        if not session.events:
            return []

        failures: list[FailureInstance] = []
        for detect in ALL_DETECTORS:
            failures.extend(detect(session, self.config))
        return failures
