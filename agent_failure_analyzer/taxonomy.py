"""
Failure taxonomy for AI agent sessions.

Defines the canonical categories, subcategories, and severity levels
used to classify agent failures across frameworks.
"""

from enum import Enum


class FailureCategory(str, Enum):
    """Top-level failure categories."""

    CONTEXT_OVERFLOW = "context_overflow"
    TOOL_MISUSE = "tool_misuse"
    INSTRUCTION_DRIFT = "instruction_drift"
    HALLUCINATION = "hallucination"
    LOOP_REPETITION = "loop_repetition"
    ERROR_CASCADE = "error_cascade"
    PLANNING_FAILURE = "planning_failure"
    RESOURCE_EXHAUSTION = "resource_exhaustion"
    SAFETY_REFUSAL = "safety_refusal"
    UNKNOWN = "unknown"


class FailureSubcategory(str, Enum):
    """Granular failure subcategories."""

    # Context overflow
    CONTEXT_WINDOW_EXCEEDED = "context_window_exceeded"
    STALE_CONTEXT_POLLUTION = "stale_context_pollution"
    VERBOSE_TOOL_OUTPUT = "verbose_tool_output"
    MISSING_COMPACTION = "missing_compaction"

    # Tool misuse
    WRONG_TOOL_SELECTED = "wrong_tool_selected"
    INVALID_TOOL_ARGS = "invalid_tool_args"
    TOOL_NOT_FOUND = "tool_not_found"
    TOOL_TIMEOUT = "tool_timeout"
    REPEATED_TOOL_FAILURE = "repeated_tool_failure"

    # Instruction drift
    LOST_SYSTEM_PROMPT = "lost_system_prompt"
    GOAL_FORGOTTEN = "goal_forgotten"
    CONSTRAINT_VIOLATED = "constraint_violated"
    ROLE_DEVIATION = "role_deviation"

    # Hallucination
    FABRICATED_FILE_PATH = "fabricated_file_path"
    FABRICATED_API = "fabricated_api"
    FABRICATED_FACT = "fabricated_fact"
    NONEXISTENT_DEPENDENCY = "nonexistent_dependency"

    # Loop / repetition
    IDENTICAL_ACTION_LOOP = "identical_action_loop"
    SEMANTIC_LOOP = "semantic_loop"
    RETRY_WITHOUT_CHANGE = "retry_without_change"

    # Error cascade
    UNHANDLED_EXCEPTION = "unhandled_exception"
    SILENT_FAILURE = "silent_failure"
    MISINTERPRETED_ERROR = "misinterpreted_error"
    CASCADING_TOOL_ERRORS = "cascading_tool_errors"

    # Planning failure
    WRONG_DECOMPOSITION = "wrong_decomposition"
    SKIPPED_STEPS = "skipped_steps"
    OVERAMBITIOUS_PLAN = "overambitious_plan"
    NO_PLAN = "no_plan"

    # Resource exhaustion
    TOKEN_LIMIT_HIT = "token_limit_hit"
    RATE_LIMIT_HIT = "rate_limit_hit"
    COST_LIMIT_HIT = "cost_limit_hit"
    TIME_LIMIT_HIT = "time_limit_hit"

    # Safety refusal
    FALSE_POSITIVE_REFUSAL = "false_positive_refusal"
    APPROPRIATE_REFUSAL = "appropriate_refusal"

    # Unknown
    UNCLASSIFIED = "unclassified"


class Severity(str, Enum):
    """How badly the failure impacted the session."""

    CRITICAL = "critical"  # Session terminated or produced wrong output
    HIGH = "high"  # Major goal not achieved
    MEDIUM = "medium"  # Partial failure, workaround possible
    LOW = "low"  # Minor issue, session still succeeded
    INFO = "info"  # Observable pattern, not necessarily harmful


# Mapping from subcategory to parent category
SUBCATEGORY_TO_CATEGORY: dict[FailureSubcategory, FailureCategory] = {
    # Context overflow
    FailureSubcategory.CONTEXT_WINDOW_EXCEEDED: FailureCategory.CONTEXT_OVERFLOW,
    FailureSubcategory.STALE_CONTEXT_POLLUTION: FailureCategory.CONTEXT_OVERFLOW,
    FailureSubcategory.VERBOSE_TOOL_OUTPUT: FailureCategory.CONTEXT_OVERFLOW,
    FailureSubcategory.MISSING_COMPACTION: FailureCategory.CONTEXT_OVERFLOW,
    # Tool misuse
    FailureSubcategory.WRONG_TOOL_SELECTED: FailureCategory.TOOL_MISUSE,
    FailureSubcategory.INVALID_TOOL_ARGS: FailureCategory.TOOL_MISUSE,
    FailureSubcategory.TOOL_NOT_FOUND: FailureCategory.TOOL_MISUSE,
    FailureSubcategory.TOOL_TIMEOUT: FailureCategory.TOOL_MISUSE,
    FailureSubcategory.REPEATED_TOOL_FAILURE: FailureCategory.TOOL_MISUSE,
    # Instruction drift
    FailureSubcategory.LOST_SYSTEM_PROMPT: FailureCategory.INSTRUCTION_DRIFT,
    FailureSubcategory.GOAL_FORGOTTEN: FailureCategory.INSTRUCTION_DRIFT,
    FailureSubcategory.CONSTRAINT_VIOLATED: FailureCategory.INSTRUCTION_DRIFT,
    FailureSubcategory.ROLE_DEVIATION: FailureCategory.INSTRUCTION_DRIFT,
    # Hallucination
    FailureSubcategory.FABRICATED_FILE_PATH: FailureCategory.HALLUCINATION,
    FailureSubcategory.FABRICATED_API: FailureCategory.HALLUCINATION,
    FailureSubcategory.FABRICATED_FACT: FailureCategory.HALLUCINATION,
    FailureSubcategory.NONEXISTENT_DEPENDENCY: FailureCategory.HALLUCINATION,
    # Loop / repetition
    FailureSubcategory.IDENTICAL_ACTION_LOOP: FailureCategory.LOOP_REPETITION,
    FailureSubcategory.SEMANTIC_LOOP: FailureCategory.LOOP_REPETITION,
    FailureSubcategory.RETRY_WITHOUT_CHANGE: FailureCategory.LOOP_REPETITION,
    # Error cascade
    FailureSubcategory.UNHANDLED_EXCEPTION: FailureCategory.ERROR_CASCADE,
    FailureSubcategory.SILENT_FAILURE: FailureCategory.ERROR_CASCADE,
    FailureSubcategory.MISINTERPRETED_ERROR: FailureCategory.ERROR_CASCADE,
    FailureSubcategory.CASCADING_TOOL_ERRORS: FailureCategory.ERROR_CASCADE,
    # Planning failure
    FailureSubcategory.WRONG_DECOMPOSITION: FailureCategory.PLANNING_FAILURE,
    FailureSubcategory.SKIPPED_STEPS: FailureCategory.PLANNING_FAILURE,
    FailureSubcategory.OVERAMBITIOUS_PLAN: FailureCategory.PLANNING_FAILURE,
    FailureSubcategory.NO_PLAN: FailureCategory.PLANNING_FAILURE,
    # Resource exhaustion
    FailureSubcategory.TOKEN_LIMIT_HIT: FailureCategory.RESOURCE_EXHAUSTION,
    FailureSubcategory.RATE_LIMIT_HIT: FailureCategory.RESOURCE_EXHAUSTION,
    FailureSubcategory.COST_LIMIT_HIT: FailureCategory.RESOURCE_EXHAUSTION,
    FailureSubcategory.TIME_LIMIT_HIT: FailureCategory.RESOURCE_EXHAUSTION,
    # Safety refusal
    FailureSubcategory.FALSE_POSITIVE_REFUSAL: FailureCategory.SAFETY_REFUSAL,
    FailureSubcategory.APPROPRIATE_REFUSAL: FailureCategory.SAFETY_REFUSAL,
    # Unknown
    FailureSubcategory.UNCLASSIFIED: FailureCategory.UNKNOWN,
}


# Human-readable descriptions for reports
CATEGORY_DESCRIPTIONS: dict[FailureCategory, str] = {
    FailureCategory.CONTEXT_OVERFLOW: (
        "The agent's context window filled up, causing loss of instructions, "
        "stale information, or session termination."
    ),
    FailureCategory.TOOL_MISUSE: (
        "The agent selected the wrong tool, passed invalid arguments, "
        "or failed to recover from tool errors."
    ),
    FailureCategory.INSTRUCTION_DRIFT: (
        "The agent forgot or deviated from its original instructions, "
        "system prompt, or user goals."
    ),
    FailureCategory.HALLUCINATION: (
        "The agent fabricated file paths, APIs, facts, or dependencies "
        "that don't exist."
    ),
    FailureCategory.LOOP_REPETITION: (
        "The agent repeated the same action or similar actions without "
        "making progress."
    ),
    FailureCategory.ERROR_CASCADE: (
        "An initial error triggered a chain of subsequent failures "
        "the agent couldn't recover from."
    ),
    FailureCategory.PLANNING_FAILURE: (
        "The agent's approach to decomposing or sequencing the task "
        "was fundamentally flawed."
    ),
    FailureCategory.RESOURCE_EXHAUSTION: (
        "The session hit a hard limit on tokens, rate, cost, or time."
    ),
    FailureCategory.SAFETY_REFUSAL: (
        "The agent refused to proceed due to safety filters, "
        "whether appropriately or as a false positive."
    ),
    FailureCategory.UNKNOWN: (
        "The failure could not be classified into a known category."
    ),
}
