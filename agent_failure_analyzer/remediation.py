"""
Failure remediation suggestions.

Maps each failure subcategory to concrete, actionable fix suggestions
that help users resolve the detected issues.
"""

from __future__ import annotations

from .taxonomy import FailureSubcategory

# Mapping from subcategory to a list of remediation suggestions
REMEDIATION_MAP: dict[FailureSubcategory, list[str]] = {
    # Context overflow
    FailureSubcategory.CONTEXT_WINDOW_EXCEEDED: [
        "Enable context compaction / summarization before the window fills.",
        "Split long tasks into smaller sub-tasks with fresh context.",
        "Use a model with a larger context window.",
    ],
    FailureSubcategory.STALE_CONTEXT_POLLUTION: [
        "Periodically summarize and prune earlier conversation turns.",
        "Use explicit memory or scratchpad instead of relying on raw context.",
        "Reduce verbose intermediate outputs that consume context budget.",
    ],
    FailureSubcategory.VERBOSE_TOOL_OUTPUT: [
        "Truncate or summarize tool outputs before feeding them back.",
        "Use tool output filters to return only relevant fields.",
        "Set max_output_length on tool configurations.",
    ],
    FailureSubcategory.MISSING_COMPACTION: [
        "Enable automatic context compaction in your framework settings.",
        "Add a compaction step after every N turns.",
        "Use a sliding-window approach to keep context fresh.",
    ],
    # Tool misuse
    FailureSubcategory.WRONG_TOOL_SELECTED: [
        "Improve tool descriptions to make capabilities more distinct.",
        "Add negative examples showing when NOT to use each tool.",
        "Reduce the number of similar tools to avoid selection confusion.",
    ],
    FailureSubcategory.INVALID_TOOL_ARGS: [
        "Add stricter JSON schema validation to tool definitions.",
        "Include argument examples in tool descriptions.",
        "Use enum types for constrained parameters.",
    ],
    FailureSubcategory.TOOL_NOT_FOUND: [
        "Verify all tools are registered before session starts.",
        "Check for typos in tool names referenced by the agent.",
        "Ensure tool plugins are installed and discoverable.",
    ],
    FailureSubcategory.TOOL_TIMEOUT: [
        "Increase timeout limits for long-running tools.",
        "Add progress indicators so the agent knows to wait.",
        "Break long operations into smaller, checkpointed steps.",
    ],
    FailureSubcategory.REPEATED_TOOL_FAILURE: [
        "Add a retry budget — limit retries to 2-3 before escalating.",
        "Implement fallback tools or alternative approaches.",
        "Instruct the agent to diagnose errors before retrying.",
    ],
    # Instruction drift
    FailureSubcategory.LOST_SYSTEM_PROMPT: [
        "Pin critical instructions at both the start and end of context.",
        "Use periodic system prompt reminders during long sessions.",
        "Keep the system prompt concise and highlight must-follow rules.",
    ],
    FailureSubcategory.GOAL_FORGOTTEN: [
        "Restate the user's goal in the system prompt or scratchpad.",
        "Add a goal-tracking mechanism that checks alignment each turn.",
        "Break multi-step tasks into explicit checklists.",
    ],
    FailureSubcategory.CONSTRAINT_VIOLATED: [
        "Enumerate constraints as numbered rules in the system prompt.",
        "Add guardrails that validate actions against constraints pre-execution.",
        "Use output validation to catch constraint violations before delivery.",
    ],
    FailureSubcategory.ROLE_DEVIATION: [
        "Strengthen the persona/role definition in the system prompt.",
        "Add examples of in-role vs out-of-role behavior.",
        "Use a role-check prompt before generating responses.",
    ],
    # Hallucination
    FailureSubcategory.FABRICATED_FILE_PATH: [
        "Instruct the agent to verify file existence before referencing.",
        "Use directory listing tools before file operations.",
        "Add pre-execution checks that validate paths exist.",
    ],
    FailureSubcategory.FABRICATED_API: [
        "Ground the agent in actual API documentation.",
        "Use tool definitions that enumerate available endpoints.",
        "Validate API calls against an OpenAPI spec before execution.",
    ],
    FailureSubcategory.FABRICATED_FACT: [
        "Instruct the agent to cite sources for factual claims.",
        "Use retrieval-augmented generation (RAG) for factual grounding.",
        "Add a fact-check step before presenting information to users.",
    ],
    FailureSubcategory.NONEXISTENT_DEPENDENCY: [
        "Validate package names against the registry before suggesting.",
        "Provide a pre-approved dependency list in the system prompt.",
        "Use a tool that checks package existence before installation.",
    ],
    # Loop / repetition
    FailureSubcategory.IDENTICAL_ACTION_LOOP: [
        "Add loop detection that breaks after 3 identical actions.",
        "Track recent actions in a scratchpad to detect repetition.",
        "Force the agent to explain why it's retrying before allowing it.",
    ],
    FailureSubcategory.SEMANTIC_LOOP: [
        "Add a progress tracker that detects stalled advancement.",
        "Limit the number of similar responses before forcing a new approach.",
        "Instruct the agent to check if it's making progress each turn.",
    ],
    FailureSubcategory.RETRY_WITHOUT_CHANGE: [
        "Require the agent to modify its approach after any failure.",
        "Implement exponential backoff with strategy changes.",
        "Add a 'what did I learn from this error?' reflection step.",
    ],
    # Error cascade
    FailureSubcategory.UNHANDLED_EXCEPTION: [
        "Add try/catch wrappers around tool executions.",
        "Implement graceful error recovery in the agent loop.",
        "Return structured error messages that the agent can act on.",
    ],
    FailureSubcategory.SILENT_FAILURE: [
        "Ensure all tool operations return explicit success/failure signals.",
        "Add assertion checks after critical operations.",
        "Log tool outputs even on apparent success for audit.",
    ],
    FailureSubcategory.MISINTERPRETED_ERROR: [
        "Format error messages to clearly separate cause and suggested fix.",
        "Include error codes that map to specific recovery procedures.",
        "Instruct the agent to quote the error message in its analysis.",
    ],
    FailureSubcategory.CASCADING_TOOL_ERRORS: [
        "Implement circuit breakers — stop after 3 consecutive errors.",
        "Add a 'step back and reassess' instruction after multiple failures.",
        "Separate independent operations so one failure doesn't block others.",
    ],
    # Planning failure
    FailureSubcategory.WRONG_DECOMPOSITION: [
        "Require the agent to produce a plan and get user approval first.",
        "Provide task decomposition examples in the system prompt.",
        "Add a plan-validation step before execution begins.",
    ],
    FailureSubcategory.SKIPPED_STEPS: [
        "Use explicit checklists that must be completed in order.",
        "Add dependencies between steps so skipping is prevented.",
        "Require the agent to confirm each step before proceeding.",
    ],
    FailureSubcategory.OVERAMBITIOUS_PLAN: [
        "Limit the scope of each session to a single well-defined task.",
        "Add a complexity estimator that flags plans with too many steps.",
        "Instruct the agent to simplify when a plan exceeds 10 steps.",
    ],
    FailureSubcategory.NO_PLAN: [
        "Require a planning/thinking step before any tool calls.",
        "Add a 'think before you act' instruction to the system prompt.",
        "Use structured output that mandates a plan field.",
    ],
    # Resource exhaustion
    FailureSubcategory.TOKEN_LIMIT_HIT: [
        "Use a smaller model for sub-tasks that don't need full capability.",
        "Implement token budgeting — allocate tokens per sub-task.",
        "Enable context compaction to free up token budget.",
    ],
    FailureSubcategory.RATE_LIMIT_HIT: [
        "Implement exponential backoff with jitter for API calls.",
        "Batch multiple operations to reduce API call frequency.",
        "Use a rate limiter that queues requests within limits.",
    ],
    FailureSubcategory.COST_LIMIT_HIT: [
        "Set per-session cost budgets with early warning at 80%.",
        "Use cheaper models for routine operations, reserving premium for complex tasks.",
        "Monitor token usage in real-time and alert before limits.",
    ],
    FailureSubcategory.TIME_LIMIT_HIT: [
        "Increase timeout limits for known long-running operations.",
        "Add progress checkpoints so work isn't lost on timeout.",
        "Parallelize independent operations to reduce total time.",
    ],
    # Safety refusal
    FailureSubcategory.FALSE_POSITIVE_REFUSAL: [
        "Refine safety instructions to reduce false positives for your use case.",
        "Add explicit permissions for the agent's authorized actions.",
        "Use allowlists for operations the agent is permitted to perform.",
    ],
    FailureSubcategory.APPROPRIATE_REFUSAL: [
        "Review if the requested action truly requires safety restrictions.",
        "Adjust the request to stay within the agent's safety boundaries.",
        "Use a human-in-the-loop step for operations that trigger refusals.",
    ],
    # Unknown
    FailureSubcategory.UNCLASSIFIED: [
        "Review the session transcript manually for unusual patterns.",
        "Consider using LLM-based classification (--llm) for better coverage.",
        "Report unclassified failures to help improve the taxonomy.",
    ],
}


def get_remediation(subcategory: FailureSubcategory) -> list[str]:
    """Get remediation suggestions for a failure subcategory."""
    return REMEDIATION_MAP.get(subcategory, [
        "Review the session transcript for context on this failure.",
        "Consider using LLM-based classification for deeper analysis.",
    ])
