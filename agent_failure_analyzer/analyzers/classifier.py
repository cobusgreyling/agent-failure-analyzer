"""
Failure classifier — pattern-matching and heuristic-based classification.

Each detector method checks for a specific failure pattern and returns
FailureInstance objects when patterns match.
"""

from __future__ import annotations

import re
from collections import Counter

from ..models import (
    AgentSession,
    EventType,
    FailureInstance,
    SessionEvent,
)
from ..taxonomy import FailureCategory, FailureSubcategory, Severity


class FailureClassifier:
    """Classifies failures in a normalized agent session."""

    def classify(self, session: AgentSession) -> list[FailureInstance]:
        failures: list[FailureInstance] = []
        events = session.events

        if not events:
            return failures

        failures.extend(self._detect_context_overflow(session))
        failures.extend(self._detect_tool_misuse(events))
        failures.extend(self._detect_loops(events))
        failures.extend(self._detect_hallucinations(events))
        failures.extend(self._detect_error_cascades(events))
        failures.extend(self._detect_instruction_drift(events))
        failures.extend(self._detect_planning_failures(events))
        failures.extend(self._detect_resource_exhaustion(session))
        failures.extend(self._detect_safety_refusals(events))

        return failures

    # ── Context Overflow ──────────────────────────────────────────────

    def _detect_context_overflow(self, session: AgentSession) -> list[FailureInstance]:
        failures = []
        events = session.events

        # Check for explicit context/token limit errors
        for i, event in enumerate(events):
            if event.event_type == EventType.ERROR and event.error_message:
                msg = event.error_message.lower()
                if any(kw in msg for kw in [
                    "context length", "context window", "max_tokens",
                    "token limit", "too many tokens", "maximum context",
                    "context_length_exceeded",
                ]):
                    failures.append(FailureInstance(
                        category=FailureCategory.CONTEXT_OVERFLOW,
                        subcategory=FailureSubcategory.CONTEXT_WINDOW_EXCEEDED,
                        severity=Severity.CRITICAL,
                        description="Session hit context window limit.",
                        evidence=[event.error_message],
                        event_indices=[i],
                        confidence=0.95,
                    ))

        # Check for verbose tool outputs (> 5000 chars)
        verbose_indices = []
        for i, event in enumerate(events):
            if event.event_type == EventType.TOOL_RESULT and len(event.content) > 5000:
                verbose_indices.append(i)

        if len(verbose_indices) >= 3:
            failures.append(FailureInstance(
                category=FailureCategory.CONTEXT_OVERFLOW,
                subcategory=FailureSubcategory.VERBOSE_TOOL_OUTPUT,
                severity=Severity.MEDIUM,
                description=(
                    f"{len(verbose_indices)} tool outputs exceeded 5000 chars, "
                    "consuming significant context budget."
                ),
                evidence=[
                    f"Event {i}: {len(events[i].content)} chars"
                    for i in verbose_indices[:5]
                ],
                event_indices=verbose_indices,
                confidence=0.7,
            ))

        # Token-based detection
        if session.total_tokens and session.total_tokens > 150_000:
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

    # ── Tool Misuse ───────────────────────────────────────────────────

    def _detect_tool_misuse(self, events: list[SessionEvent]) -> list[FailureInstance]:
        failures = []

        # Find tool calls followed by error results
        tool_errors: list[tuple[int, str]] = []
        for i, event in enumerate(events):
            if event.event_type == EventType.TOOL_RESULT and event.error_message:
                tool_name = event.tool_name or "unknown"
                tool_errors.append((i, tool_name))

        # Repeated failures on the same tool
        tool_error_counts = Counter(name for _, name in tool_errors)
        for tool_name, count in tool_error_counts.items():
            if count >= 3:
                indices = [i for i, n in tool_errors if n == tool_name]
                failures.append(FailureInstance(
                    category=FailureCategory.TOOL_MISUSE,
                    subcategory=FailureSubcategory.REPEATED_TOOL_FAILURE,
                    severity=Severity.HIGH,
                    description=(
                        f"Tool '{tool_name}' failed {count} times"
                        " without successful recovery."
                    ),
                    evidence=[
                        events[idx].error_message or events[idx].content[:200]
                        for idx in indices[:3]
                    ],
                    event_indices=indices,
                    confidence=0.85,
                ))

        # Invalid tool args (common patterns)
        for i, event in enumerate(events):
            if event.event_type == EventType.TOOL_RESULT and event.error_message:
                msg = event.error_message.lower()
                if any(kw in msg for kw in [
                    "invalid arg", "missing required", "unexpected keyword",
                    "validation error", "type error", "not found",
                ]):
                    failures.append(FailureInstance(
                        category=FailureCategory.TOOL_MISUSE,
                        subcategory=FailureSubcategory.INVALID_TOOL_ARGS,
                        severity=Severity.MEDIUM,
                        description=f"Tool call at event {i} received invalid arguments.",
                        evidence=[event.error_message[:300]],
                        event_indices=[i],
                        confidence=0.8,
                    ))

        # Tool not found
        for i, event in enumerate(events):
            if event.event_type in (EventType.ERROR, EventType.TOOL_RESULT):
                msg = (event.error_message or event.content).lower()
                if any(kw in msg for kw in [
                    "tool not found", "unknown tool", "no such tool",
                    "tool_not_found", "unrecognized tool",
                ]):
                    failures.append(FailureInstance(
                        category=FailureCategory.TOOL_MISUSE,
                        subcategory=FailureSubcategory.TOOL_NOT_FOUND,
                        severity=Severity.HIGH,
                        description=f"Agent attempted to use a non-existent tool at event {i}.",
                        evidence=[(event.error_message or event.content)[:300]],
                        event_indices=[i],
                        confidence=0.9,
                    ))

        return failures

    # ── Loops / Repetition ────────────────────────────────────────────

    def _detect_loops(self, events: list[SessionEvent]) -> list[FailureInstance]:
        failures = []

        # Identical action loop: same tool + same args called 3+ times
        tool_calls = [
            (i, e.tool_name, str(e.tool_args) if e.tool_args else e.content[:200])
            for i, e in enumerate(events)
            if e.event_type == EventType.TOOL_CALL
        ]

        if len(tool_calls) >= 3:
            # Sliding window to detect consecutive identical calls
            for start in range(len(tool_calls) - 2):
                window = tool_calls[start : start + 3]
                signatures = [(tc[1], tc[2]) for tc in window]
                if len(set(signatures)) == 1:
                    indices = [tc[0] for tc in window]
                    failures.append(FailureInstance(
                        category=FailureCategory.LOOP_REPETITION,
                        subcategory=FailureSubcategory.IDENTICAL_ACTION_LOOP,
                        severity=Severity.HIGH,
                        description=(
                            f"Agent called '{window[0][1]}' with identical arguments "
                            f"3+ times consecutively."
                        ),
                        evidence=[f"Tool: {window[0][1]}, Args: {window[0][2][:100]}"],
                        event_indices=indices,
                        confidence=0.9,
                    ))
                    break  # Report once per loop

        # Retry without change: tool fails, then retried identically
        for i in range(len(tool_calls) - 1):
            idx_a, name_a, args_a = tool_calls[i]
            idx_b, name_b, args_b = tool_calls[i + 1]

            if name_a == name_b and args_a == args_b:
                # Check if there was an error between them
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

        # Semantic loop: assistant messages that are very similar
        assistant_msgs = [
            (i, e.content)
            for i, e in enumerate(events)
            if e.event_type == EventType.ASSISTANT_MESSAGE and len(e.content) > 50
        ]
        if len(assistant_msgs) >= 3:
            for start in range(len(assistant_msgs) - 2):
                msg_window = assistant_msgs[start : start + 3]
                texts = [t[1][:300] for t in msg_window]
                # Simple similarity: check if messages share >70% of words
                word_sets = [set(t.lower().split()) for t in texts]
                if len(word_sets[0]) > 5:
                    overlap_01 = len(word_sets[0] & word_sets[1]) / max(len(word_sets[0]), 1)
                    overlap_12 = len(word_sets[1] & word_sets[2]) / max(len(word_sets[1]), 1)
                    if overlap_01 > 0.7 and overlap_12 > 0.7:
                        failures.append(FailureInstance(
                            category=FailureCategory.LOOP_REPETITION,
                            subcategory=FailureSubcategory.SEMANTIC_LOOP,
                            severity=Severity.MEDIUM,
                            description=(
                            "Agent produced 3+ semantically similar"
                            " responses in sequence."
                        ),
                            evidence=[t[:150] for _, t in msg_window],
                            event_indices=[idx for idx, _ in msg_window],
                            confidence=0.65,
                        ))
                        break

        return failures

    # ── Hallucinations ────────────────────────────────────────────────

    def _detect_hallucinations(self, events: list[SessionEvent]) -> list[FailureInstance]:
        failures = []

        # Fabricated file paths: tool call references a path, then "not found" error
        for i, event in enumerate(events):
            if event.event_type == EventType.TOOL_CALL and event.tool_name in (
                "Read", "read_file", "open_file", "cat", "Edit", "write_file",
            ):
                # Check next event for "not found"
                if i + 1 < len(events):
                    next_evt = events[i + 1]
                    if next_evt.error_message and any(
                        kw in next_evt.error_message.lower()
                        for kw in ["not found", "no such file", "does not exist", "enoent"]
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
                            f"Agent referenced non-existent file:"
                            f" {path_str or 'unknown'}"
                        ),
                            evidence=[
                                event.content[:200],
                                next_evt.error_message[:200],
                            ],
                            event_indices=[i, i + 1],
                            confidence=0.8,
                        ))

        # Fabricated APIs/dependencies in assistant messages
        for i, event in enumerate(events):
            if event.event_type == EventType.ASSISTANT_MESSAGE:
                # Check if the assistant suggests a package and it later fails
                for j in range(i + 1, min(i + 5, len(events))):
                    next_evt = events[j]
                    if next_evt.error_message and any(
                        kw in next_evt.error_message.lower()
                        for kw in [
                            "no module named", "modulenotfounderror",
                            "package not found", "npm err",
                        ]
                    ):
                        failures.append(FailureInstance(
                            category=FailureCategory.HALLUCINATION,
                            subcategory=FailureSubcategory.NONEXISTENT_DEPENDENCY,
                            severity=Severity.HIGH,
                            description="Agent referenced a non-existent package or module.",
                            evidence=[
                                event.content[:200],
                                next_evt.error_message[:200],
                            ],
                            event_indices=[i, j],
                            confidence=0.75,
                        ))
                        break

        return failures

    # ── Error Cascades ────────────────────────────────────────────────

    def _detect_error_cascades(self, events: list[SessionEvent]) -> list[FailureInstance]:
        failures = []

        # Find sequences of 3+ consecutive errors
        error_streak = []
        for i, event in enumerate(events):
            is_error = (
                event.event_type == EventType.ERROR
                or (event.event_type == EventType.TOOL_RESULT and event.error_message)
            )
            if is_error:
                error_streak.append(i)
            else:
                if len(error_streak) >= 3:
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

        # Check trailing streak
        if len(error_streak) >= 3:
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

        # Misinterpreted error: agent responds to an error without addressing it
        for i, event in enumerate(events):
            if event.event_type == EventType.ERROR and event.error_message:
                # Look at the next assistant message
                for j in range(i + 1, min(i + 3, len(events))):
                    next_evt = events[j]
                    if next_evt.event_type == EventType.ASSISTANT_MESSAGE:
                        # Check if the response mentions the error
                        error_keywords = set(event.error_message.lower().split()[:5])
                        response_words = set(next_evt.content.lower().split())
                        overlap = error_keywords & response_words
                        if len(overlap) < 2 and len(error_keywords) > 3:
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

    # ── Instruction Drift ─────────────────────────────────────────────

    def _detect_instruction_drift(self, events: list[SessionEvent]) -> list[FailureInstance]:
        failures = []

        # Look for explicit signals of drift
        drift_keywords = [
            "i already told you", "that's not what i asked",
            "you forgot", "wrong approach", "start over",
            "not what i meant", "go back to", "you were supposed to",
            "you're going off track", "stick to the plan",
        ]

        for i, event in enumerate(events):
            if event.event_type == EventType.USER_MESSAGE:
                content_lower = event.content.lower()
                for kw in drift_keywords:
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

        # Constraint violation: user sets a constraint, agent violates it
        constraint_patterns = [
            r"don'?t\s+(use|create|modify|delete|change|add|remove)",
            r"only\s+(use|modify|edit|change)",
            r"never\s+(use|create|modify|delete)",
            r"do\s+not\s+(use|create|modify|delete|change)",
        ]
        user_constraints: list[tuple[int, str]] = []
        for i, event in enumerate(events):
            if event.event_type == EventType.USER_MESSAGE:
                for pattern in constraint_patterns:
                    match = re.search(pattern, event.content.lower())
                    if match:
                        user_constraints.append((i, match.group()))

        # If user complains after setting constraints, likely a violation
        if user_constraints:
            for i, event in enumerate(events):
                if event.event_type == EventType.USER_MESSAGE and i > user_constraints[0][0]:
                    content_lower = event.content.lower()
                    if any(
                        kw in content_lower
                        for kw in ["why did you", "i said don't", "i told you not"]
                    ):
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

    # ── Planning Failures ─────────────────────────────────────────────

    def _detect_planning_failures(self, events: list[SessionEvent]) -> list[FailureInstance]:
        failures = []

        # Overambitious plan: very long session with many tool calls but failure outcome
        tool_call_count = sum(1 for e in events if e.event_type == EventType.TOOL_CALL)
        error_count = sum(
            1 for e in events
            if e.event_type == EventType.ERROR
            or (e.event_type == EventType.TOOL_RESULT and e.error_message)
        )

        if tool_call_count > 20 and error_count > tool_call_count * 0.4:
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

        # No plan: agent jumps straight into tool calls without thinking/planning
        if len(events) > 5:
            first_5 = events[:5]
            has_thinking = any(e.event_type == EventType.THINKING for e in first_5)
            has_plan_mention = any(
                e.event_type == EventType.ASSISTANT_MESSAGE
                and any(kw in e.content.lower() for kw in ["plan", "approach", "steps", "first"])
                for e in first_5
            )
            immediate_tools = sum(
                1 for e in first_5 if e.event_type == EventType.TOOL_CALL
            )
            if immediate_tools >= 3 and not has_thinking and not has_plan_mention:
                failures.append(FailureInstance(
                    category=FailureCategory.PLANNING_FAILURE,
                    subcategory=FailureSubcategory.NO_PLAN,
                    severity=Severity.LOW,
                    description="Agent made 3+ tool calls in the first 5 events without planning.",
                    evidence=[],
                    event_indices=list(range(5)),
                    confidence=0.5,
                ))

        return failures

    # ── Resource Exhaustion ───────────────────────────────────────────

    def _detect_resource_exhaustion(self, session: AgentSession) -> list[FailureInstance]:
        failures = []
        events = session.events

        for i, event in enumerate(events):
            if event.event_type != EventType.ERROR or not event.error_message:
                continue
            msg = event.error_message.lower()

            if any(kw in msg for kw in ["rate limit", "rate_limit", "429", "too many requests"]):
                failures.append(FailureInstance(
                    category=FailureCategory.RESOURCE_EXHAUSTION,
                    subcategory=FailureSubcategory.RATE_LIMIT_HIT,
                    severity=Severity.HIGH,
                    description="Session hit API rate limit.",
                    evidence=[event.error_message[:200]],
                    event_indices=[i],
                    confidence=0.95,
                ))

            if any(kw in msg for kw in ["cost limit", "budget", "spending"]):
                failures.append(FailureInstance(
                    category=FailureCategory.RESOURCE_EXHAUSTION,
                    subcategory=FailureSubcategory.COST_LIMIT_HIT,
                    severity=Severity.CRITICAL,
                    description="Session hit cost/spending limit.",
                    evidence=[event.error_message[:200]],
                    event_indices=[i],
                    confidence=0.9,
                ))

            if any(kw in msg for kw in ["timeout", "timed out", "deadline exceeded"]):
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

    # ── Safety Refusals ───────────────────────────────────────────────

    def _detect_safety_refusals(self, events: list[SessionEvent]) -> list[FailureInstance]:
        failures = []

        refusal_patterns = [
            "i can't", "i cannot", "i'm not able to", "i am not able to",
            "i must decline", "i'm unable to", "as an ai",
            "i don't think i should", "that would be inappropriate",
            "safety", "policy", "guidelines",
        ]

        for i, event in enumerate(events):
            if event.event_type == EventType.ASSISTANT_MESSAGE:
                content_lower = event.content.lower()
                if any(p in content_lower for p in refusal_patterns):
                    # Check if user was frustrated by the refusal
                    is_false_positive = False
                    for j in range(i + 1, min(i + 3, len(events))):
                        if events[j].event_type == EventType.USER_MESSAGE:
                            user_msg = events[j].content.lower()
                            if any(
                                kw in user_msg
                                for kw in [
                                    "just do it", "that's fine", "it's okay",
                                    "i have permission", "this is my", "authorized",
                                    "why not", "come on",
                                ]
                            ):
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
