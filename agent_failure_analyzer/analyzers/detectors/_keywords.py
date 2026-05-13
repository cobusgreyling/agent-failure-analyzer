"""
Keyword tables for the heuristic detectors.

These are tuples (not sets) so iteration order is stable across runs —
useful when the order of generated FailureInstance evidence matters for
tests and snapshot comparison.
"""

from __future__ import annotations

CONTEXT_WINDOW_KEYWORDS: tuple[str, ...] = (
    "context length", "context window", "max_tokens",
    "token limit", "too many tokens", "maximum context",
    "context_length_exceeded",
)

INVALID_TOOL_ARGS_KEYWORDS: tuple[str, ...] = (
    "invalid arg", "missing required", "unexpected keyword",
    "validation error", "type error", "not found",
)

TOOL_NOT_FOUND_KEYWORDS: tuple[str, ...] = (
    "tool not found", "unknown tool", "no such tool",
    "tool_not_found", "unrecognized tool",
)

FILE_NOT_FOUND_KEYWORDS: tuple[str, ...] = (
    "not found", "no such file", "does not exist", "enoent",
)

NONEXISTENT_DEPENDENCY_KEYWORDS: tuple[str, ...] = (
    "no module named", "modulenotfounderror",
    "package not found", "npm err",
)

FILE_TOOL_NAMES: tuple[str, ...] = (
    "Read", "read_file", "open_file", "cat", "Edit", "write_file",
)

DRIFT_KEYWORDS: tuple[str, ...] = (
    "i already told you", "that's not what i asked",
    "you forgot", "wrong approach", "start over",
    "not what i meant", "go back to", "you were supposed to",
    "you're going off track", "stick to the plan",
)

CONSTRAINT_PATTERNS: tuple[str, ...] = (
    r"don'?t\s+(use|create|modify|delete|change|add|remove)",
    r"only\s+(use|modify|edit|change)",
    r"never\s+(use|create|modify|delete)",
    r"do\s+not\s+(use|create|modify|delete|change)",
)

CONSTRAINT_COMPLAINT_KEYWORDS: tuple[str, ...] = (
    "why did you", "i said don't", "i told you not",
)

PLAN_MENTION_KEYWORDS: tuple[str, ...] = (
    "plan", "approach", "steps", "first",
)

RATE_LIMIT_KEYWORDS: tuple[str, ...] = (
    "rate limit", "rate_limit", "429", "too many requests",
)

COST_LIMIT_KEYWORDS: tuple[str, ...] = (
    "cost limit", "budget", "spending",
)

TIMEOUT_KEYWORDS: tuple[str, ...] = (
    "timeout", "timed out", "deadline exceeded",
)

REFUSAL_PATTERNS: tuple[str, ...] = (
    "i can't", "i cannot", "i'm not able to", "i am not able to",
    "i must decline", "i'm unable to", "as an ai",
    "i don't think i should", "that would be inappropriate",
    "safety", "policy", "guidelines",
)

REFUSAL_OVERRIDE_KEYWORDS: tuple[str, ...] = (
    "just do it", "that's fine", "it's okay",
    "i have permission", "this is my", "authorized",
    "why not", "come on",
)
