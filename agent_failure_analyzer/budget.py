"""
Token budget advisor.

Analyzes token usage patterns across sessions and recommends
optimal token budgets and model configurations.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .models import AnalysisResult, BatchAnalysisResult


@dataclass
class BudgetAdvice:
    """Token budget recommendation for a set of sessions."""

    avg_tokens: int = 0
    median_tokens: int = 0
    p95_tokens: int = 0
    max_tokens: int = 0
    recommended_budget: int = 0
    waste_ratio: float = 0.0
    suggestions: list[str] = field(default_factory=list)
    per_framework: dict[str, dict] = field(default_factory=dict)


def analyze_budget(batch: BatchAnalysisResult) -> BudgetAdvice:
    """Analyze token usage and recommend budgets."""
    advice = BudgetAdvice()

    token_counts = []
    wasted_tokens = 0
    total_tokens = 0
    framework_tokens: dict[str, list[int]] = {}

    for r in batch.results:
        session = r.session
        tokens = session.total_tokens or _estimate_tokens(r)
        if tokens > 0:
            token_counts.append(tokens)
            total_tokens += tokens
            fw = session.framework.value
            framework_tokens.setdefault(fw, []).append(tokens)

        # Estimate wasted tokens from failed tool calls
        for f in r.failures:
            for idx in f.event_indices:
                if idx < len(session.events):
                    event = session.events[idx]
                    if event.token_count:
                        wasted_tokens += event.token_count

    if not token_counts:
        advice.suggestions.append(
            "No token data available. Enable token tracking in your framework."
        )
        return advice

    token_counts.sort()
    n = len(token_counts)

    advice.avg_tokens = total_tokens // n
    advice.median_tokens = token_counts[n // 2]
    advice.p95_tokens = token_counts[int(n * 0.95)] if n >= 5 else token_counts[-1]
    advice.max_tokens = token_counts[-1]
    advice.waste_ratio = wasted_tokens / total_tokens if total_tokens > 0 else 0.0

    # Recommended budget: p95 + 20% headroom
    advice.recommended_budget = int(advice.p95_tokens * 1.2)

    # Per-framework breakdown
    for fw, counts in framework_tokens.items():
        counts.sort()
        fn = len(counts)
        advice.per_framework[fw] = {
            "avg": sum(counts) // fn,
            "median": counts[fn // 2],
            "p95": counts[int(fn * 0.95)] if fn >= 5 else counts[-1],
            "sessions": fn,
        }

    # Generate suggestions
    if advice.waste_ratio > 0.3:
        advice.suggestions.append(
            f"Token waste is {advice.waste_ratio:.0%} — consider adding "
            "error recovery to reduce wasted tokens from failed operations."
        )

    if advice.max_tokens > advice.p95_tokens * 2:
        advice.suggestions.append(
            f"Max usage ({advice.max_tokens:,}) is >2x p95 ({advice.p95_tokens:,}) — "
            "outlier sessions may need task decomposition."
        )

    if advice.avg_tokens > 100_000:
        advice.suggestions.append(
            "Average token usage exceeds 100k — consider enabling "
            "context compaction or splitting long tasks."
        )

    if advice.avg_tokens < 5_000:
        advice.suggestions.append(
            "Token usage is low — current budget settings are likely adequate."
        )

    if len(framework_tokens) > 1:
        fw_avgs = {
            fw: sum(c) // len(c) for fw, c in framework_tokens.items()
        }
        highest = max(fw_avgs, key=fw_avgs.get)  # type: ignore[arg-type]
        lowest = min(fw_avgs, key=fw_avgs.get)  # type: ignore[arg-type]
        if fw_avgs[highest] > fw_avgs[lowest] * 2:
            advice.suggestions.append(
                f"{highest} uses {fw_avgs[highest]:,} tokens avg vs "
                f"{lowest} at {fw_avgs[lowest]:,} — "
                "consider framework-specific budgets."
            )

    return advice


def _estimate_tokens(result: AnalysisResult) -> int:
    """Estimate total tokens from event content lengths."""
    total = 0
    for event in result.session.events:
        if event.token_count:
            total += event.token_count
        elif event.content:
            # Rough estimate: ~4 chars per token
            total += len(event.content) // 4
    return total
