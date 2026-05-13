"""Loop / repetition detectors."""

from __future__ import annotations

import json

from ...models import AgentSession, EventType, FailureInstance, SessionEvent
from ...taxonomy import FailureCategory, FailureSubcategory, Severity
from ..detector_config import DetectorConfig


def _tool_call_signature(event: SessionEvent) -> str:
    """Stable, order-independent signature for a tool call's arguments."""
    if event.tool_args is None:
        return event.content[:200]
    try:
        return json.dumps(event.tool_args, sort_keys=True, default=str)
    except TypeError:
        if isinstance(event.tool_args, dict):
            return repr(sorted(event.tool_args.items()))
        return str(event.tool_args)


def detect(session: AgentSession, config: DetectorConfig) -> list[FailureInstance]:
    failures: list[FailureInstance] = []
    events = session.events

    tool_calls: list[tuple[int, str | None, str]] = [
        (i, e.tool_name, _tool_call_signature(e))
        for i, e in enumerate(events)
        if e.event_type == EventType.TOOL_CALL
    ]

    window = config.identical_loop_window
    if len(tool_calls) >= window:
        for start in range(len(tool_calls) - window + 1):
            slice_ = tool_calls[start : start + window]
            signatures = [(tc[1], tc[2]) for tc in slice_]
            if len(set(signatures)) == 1:
                indices = [tc[0] for tc in slice_]
                failures.append(FailureInstance(
                    category=FailureCategory.LOOP_REPETITION,
                    subcategory=FailureSubcategory.IDENTICAL_ACTION_LOOP,
                    severity=Severity.HIGH,
                    description=(
                        f"Agent called '{slice_[0][1]}' with identical arguments "
                        f"{window}+ times consecutively."
                    ),
                    evidence=[f"Tool: {slice_[0][1]}, Args: {slice_[0][2][:100]}"],
                    event_indices=indices,
                    confidence=0.9,
                ))
                break

    for i in range(len(tool_calls) - 1):
        idx_a, name_a, args_a = tool_calls[i]
        idx_b, name_b, args_b = tool_calls[i + 1]

        if name_a == name_b and args_a == args_b:
            between = events[idx_a + 1 : idx_b]
            had_error = any(
                e.event_type in (EventType.ERROR, EventType.TOOL_RESULT)
                and e.error_message
                for e in between
            )
            if had_error:
                failures.append(FailureInstance(
                    category=FailureCategory.LOOP_REPETITION,
                    subcategory=FailureSubcategory.RETRY_WITHOUT_CHANGE,
                    severity=Severity.MEDIUM,
                    description=(
                        f"Agent retried '{name_a}' with identical arguments "
                        f"after a failure, without modifying the approach."
                    ),
                    evidence=[f"Events {idx_a} and {idx_b}"],
                    event_indices=[idx_a, idx_b],
                    confidence=0.85,
                ))
                break

    assistant_msgs = [
        (i, e.content)
        for i, e in enumerate(events)
        if e.event_type == EventType.ASSISTANT_MESSAGE
        and len(e.content) > config.semantic_loop_min_msg_chars
    ]
    sem_window = config.semantic_loop_window
    if len(assistant_msgs) >= sem_window:
        for start in range(len(assistant_msgs) - sem_window + 1):
            msg_window = assistant_msgs[start : start + sem_window]
            texts = [t[1][:300] for t in msg_window]
            word_sets = [set(t.lower().split()) for t in texts]
            if len(word_sets[0]) > config.semantic_loop_min_unique_words:
                overlap_01 = len(word_sets[0] & word_sets[1]) / max(len(word_sets[0]), 1)
                overlap_12 = len(word_sets[1] & word_sets[2]) / max(len(word_sets[1]), 1)
                ratio = config.semantic_loop_overlap_ratio
                if overlap_01 > ratio and overlap_12 > ratio:
                    failures.append(FailureInstance(
                        category=FailureCategory.LOOP_REPETITION,
                        subcategory=FailureSubcategory.SEMANTIC_LOOP,
                        severity=Severity.MEDIUM,
                        description=(
                            f"Agent produced {sem_window}+ semantically similar"
                            " responses in sequence."
                        ),
                        evidence=[t[:150] for _, t in msg_window],
                        event_indices=[idx for idx, _ in msg_window],
                        confidence=0.65,
                    ))
                    break

    return failures
