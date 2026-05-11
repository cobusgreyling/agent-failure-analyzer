"""
Cost waste estimation for failed agent sessions.

Calculates tokens consumed after the point of failure — the "wasted" tokens
that were spent on actions that couldn't succeed.
"""

from __future__ import annotations

from dataclasses import dataclass

from .models import AgentSession, AnalysisResult, EventType, FailureInstance

# Approximate pricing per 1M tokens (input/output) for common models
MODEL_PRICING: dict[str, tuple[float, float]] = {
    # (input_per_1M, output_per_1M)
    "claude-opus-4-6": (15.0, 75.0),
    "claude-sonnet-4-6": (3.0, 15.0),
    "claude-haiku-4-5": (0.80, 4.0),
    "gpt-4": (30.0, 60.0),
    "gpt-4-turbo": (10.0, 30.0),
    "gpt-4o": (2.50, 10.0),
    "gpt-3.5-turbo": (0.50, 1.50),
}

# Default estimate if model unknown
DEFAULT_PRICING = (5.0, 20.0)


@dataclass
class CostEstimate:
    """Cost waste estimation for a session."""

    total_tokens: int
    wasted_tokens: int
    waste_ratio: float
    estimated_total_cost_usd: float
    estimated_wasted_cost_usd: float
    failure_point_event_index: int | None
    model: str | None


def estimate_waste(result: AnalysisResult) -> CostEstimate:
    """Estimate token and cost waste for a session with failures.

    Identifies the earliest high-severity failure event and counts all
    tokens consumed after that point as wasted.
    """
    session = result.session
    failures = result.failures

    if not failures or not session.events:
        return CostEstimate(
            total_tokens=session.total_tokens or 0,
            wasted_tokens=0,
            waste_ratio=0.0,
            estimated_total_cost_usd=0.0,
            estimated_wasted_cost_usd=0.0,
            failure_point_event_index=None,
            model=session.model,
        )

    # Find earliest significant failure event
    significant = [
        f for f in failures
        if f.severity.value in ("critical", "high", "medium")
    ]
    if not significant:
        significant = failures

    earliest_idx = min(
        (idx for f in significant for idx in f.event_indices),
        default=len(session.events) - 1,
    )

    # Count tokens before and after the failure point
    total_tokens = 0
    tokens_before = 0
    tokens_after = 0

    for i, event in enumerate(session.events):
        event_tokens = event.token_count or _estimate_event_tokens(event)
        total_tokens += event_tokens
        if i < earliest_idx:
            tokens_before += event_tokens
        else:
            tokens_after += event_tokens

    # Use session total if available (more accurate)
    if session.total_tokens and session.total_tokens > total_tokens:
        scale = session.total_tokens / max(total_tokens, 1)
        tokens_after = int(tokens_after * scale)
        total_tokens = session.total_tokens

    # Estimate cost
    pricing = _get_pricing(session.model)
    avg_price_per_token = (pricing[0] + pricing[1]) / 2 / 1_000_000
    total_cost = total_tokens * avg_price_per_token
    wasted_cost = tokens_after * avg_price_per_token

    waste_ratio = tokens_after / max(total_tokens, 1)

    return CostEstimate(
        total_tokens=total_tokens,
        wasted_tokens=tokens_after,
        waste_ratio=waste_ratio,
        estimated_total_cost_usd=round(total_cost, 4),
        estimated_wasted_cost_usd=round(wasted_cost, 4),
        failure_point_event_index=earliest_idx,
        model=session.model,
    )


def _estimate_event_tokens(event) -> int:
    """Rough token count estimate from content length."""
    content_len = len(event.content) if event.content else 0
    return max(1, content_len // 4)  # ~4 chars per token


def _get_pricing(model: str | None) -> tuple[float, float]:
    """Look up model pricing, with fuzzy matching."""
    if not model:
        return DEFAULT_PRICING

    model_lower = model.lower()
    for key, pricing in MODEL_PRICING.items():
        if key in model_lower or model_lower in key:
            return pricing

    # Fuzzy: check if any pricing key is a substring
    for key, pricing in MODEL_PRICING.items():
        if any(part in model_lower for part in key.split("-") if len(part) > 3):
            return pricing

    return DEFAULT_PRICING
