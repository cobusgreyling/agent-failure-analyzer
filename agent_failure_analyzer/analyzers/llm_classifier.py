"""
LLM-powered failure classifier using the Anthropic Claude API.

Provides deeper analysis than heuristics alone — catches subtle instruction
drift, semantic hallucinations, and nuanced planning failures that pattern
matching misses. Designed to run as an optional second pass on sessions where
heuristic confidence is low or no failures were detected despite a bad outcome.

Requires: ANTHROPIC_API_KEY environment variable.
Uses prompt caching for efficiency when analyzing multiple sessions.
"""

from __future__ import annotations

import json
import os
from typing import Any

from ..models import AgentSession, EventType, FailureInstance, SessionOutcome
from ..taxonomy import (
    CATEGORY_DESCRIPTIONS,
    FailureCategory,
    FailureSubcategory,
    Severity,
    SUBCATEGORY_TO_CATEGORY,
)

# Build taxonomy reference for the prompt (once, at import time)
_TAXONOMY_REF = ""
for cat in FailureCategory:
    subs = [s.value for s, c in SUBCATEGORY_TO_CATEGORY.items() if c == cat]
    _TAXONOMY_REF += f"\n{cat.value}: {', '.join(subs)}"

_SYSTEM_PROMPT = f"""You are an expert AI agent debugger. You analyze agent session transcripts
and classify failures using a structured taxonomy.

## Failure Taxonomy
{_TAXONOMY_REF}

## Severity Levels
- critical: Session terminated or produced wrong output
- high: Major goal not achieved
- medium: Partial failure, workaround possible
- low: Minor issue, session still succeeded
- info: Observable pattern, not necessarily harmful

## Your Task
Analyze the session transcript and identify ALL failures present. For each failure:
1. Choose the most specific subcategory from the taxonomy
2. Assign severity based on actual impact
3. Write a concise description of what went wrong
4. Quote specific evidence from the transcript
5. Rate your confidence (0.0-1.0)

Look especially for:
- Subtle instruction drift (agent gradually deviating from the goal)
- Semantic hallucinations (plausible-sounding but fabricated information)
- Planning failures (wrong approach even if individual steps succeed)
- Silent failures (errors that were ignored or misinterpreted)
- Quality issues (technically correct but poor solution)

## Response Format
Return a JSON array of failure objects. Each object must have:
- "category": one of the category values
- "subcategory": one of the subcategory values
- "severity": one of critical/high/medium/low/info
- "description": what went wrong (1-2 sentences)
- "evidence": array of quoted strings from the transcript
- "confidence": float 0.0-1.0

If no failures are found, return an empty array: []

Return ONLY the JSON array, no other text."""


def _format_session_transcript(session: AgentSession, max_events: int = 100) -> str:
    """Convert a session into a readable transcript for the LLM."""
    lines = []
    lines.append(f"Session ID: {session.session_id}")
    lines.append(f"Framework: {session.framework.value}")
    if session.model:
        lines.append(f"Model: {session.model}")
    lines.append(f"Outcome: {session.outcome.value}")
    if session.total_tokens:
        lines.append(f"Total tokens: {session.total_tokens:,}")
    lines.append(f"Events: {len(session.events)}")
    lines.append("---")

    events = session.events[:max_events]
    for i, event in enumerate(events):
        prefix = f"[{i}] {event.event_type.value}"
        if event.tool_name:
            prefix += f" ({event.tool_name})"

        content = event.content
        # Truncate very long content
        if len(content) > 1000:
            content = content[:1000] + f"... [{len(content) - 1000} chars truncated]"

        if event.error_message:
            lines.append(f"{prefix}: ERROR: {event.error_message[:500]}")
        elif content:
            lines.append(f"{prefix}: {content}")
        else:
            lines.append(prefix)

    if len(session.events) > max_events:
        lines.append(f"... [{len(session.events) - max_events} more events truncated]")

    return "\n".join(lines)


class LLMClassifier:
    """Classify failures using Claude API with prompt caching."""

    def __init__(
        self,
        model: str = "claude-sonnet-4-6",
        api_key: str | None = None,
        max_tokens: int = 4096,
    ) -> None:
        self.model = model
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self.max_tokens = max_tokens
        self._client = None

    def _get_client(self):
        """Lazy-init the Anthropic client."""
        if self._client is None:
            try:
                import anthropic
            except ImportError:
                raise ImportError(
                    "The 'anthropic' package is required for LLM classification. "
                    "Install it with: pip install agent-failure-analyzer[llm]"
                )
            if not self.api_key:
                raise ValueError(
                    "ANTHROPIC_API_KEY environment variable is required for LLM classification."
                )
            self._client = anthropic.Anthropic(api_key=self.api_key)
        return self._client

    def classify(self, session: AgentSession) -> list[FailureInstance]:
        """Classify failures in a session using Claude."""
        client = self._get_client()
        transcript = _format_session_transcript(session)

        response = client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=[
                {
                    "type": "text",
                    "text": _SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[
                {
                    "role": "user",
                    "content": f"Analyze this agent session transcript for failures:\n\n{transcript}",
                }
            ],
        )

        return self._parse_response(response)

    def classify_batch(
        self, sessions: list[AgentSession]
    ) -> dict[str, list[FailureInstance]]:
        """Classify multiple sessions, benefiting from prompt caching.

        The system prompt (with taxonomy) is cached across calls within
        the 5-minute TTL window, reducing cost for batch analysis.
        """
        results: dict[str, list[FailureInstance]] = {}
        for session in sessions:
            try:
                results[session.session_id] = self.classify(session)
            except Exception as e:
                results[session.session_id] = [
                    FailureInstance(
                        category=FailureCategory.UNKNOWN,
                        subcategory=FailureSubcategory.UNCLASSIFIED,
                        severity=Severity.INFO,
                        description=f"LLM classification failed: {e}",
                        confidence=0.0,
                    )
                ]
        return results

    @staticmethod
    def _parse_response(response) -> list[FailureInstance]:
        """Parse the Claude API response into FailureInstance objects."""
        text = ""
        for block in response.content:
            if hasattr(block, "text"):
                text += block.text

        # Extract JSON from response (handle markdown code blocks)
        text = text.strip()
        if text.startswith("```"):
            # Remove markdown code fences
            lines = text.split("\n")
            text = "\n".join(
                line for line in lines
                if not line.strip().startswith("```")
            )

        try:
            raw_failures = json.loads(text)
        except json.JSONDecodeError:
            return [
                FailureInstance(
                    category=FailureCategory.UNKNOWN,
                    subcategory=FailureSubcategory.UNCLASSIFIED,
                    severity=Severity.INFO,
                    description=f"LLM returned unparseable response: {text[:200]}",
                    confidence=0.0,
                )
            ]

        if not isinstance(raw_failures, list):
            return []

        failures = []
        for raw in raw_failures:
            if not isinstance(raw, dict):
                continue
            try:
                failure = FailureInstance(
                    category=FailureCategory(raw.get("category", "unknown")),
                    subcategory=FailureSubcategory(raw.get("subcategory", "unclassified")),
                    severity=Severity(raw.get("severity", "info")),
                    description=raw.get("description", ""),
                    evidence=raw.get("evidence", []),
                    confidence=float(raw.get("confidence", 0.5)),
                )
                failures.append(failure)
            except (ValueError, KeyError):
                continue

        return failures


def needs_llm_review(heuristic_failures: list[FailureInstance], session: AgentSession) -> bool:
    """Decide whether a session would benefit from LLM review.

    Returns True when:
    - Session failed but heuristics found nothing
    - All heuristic findings have low confidence (<0.6)
    - Session is long (>20 events) with no findings (subtle issues likely)
    """
    if session.outcome in (SessionOutcome.FAILURE, SessionOutcome.ABANDONED):
        if not heuristic_failures:
            return True
        if all(f.confidence < 0.6 for f in heuristic_failures):
            return True

    if len(session.events) > 20 and not heuristic_failures:
        return True

    return False


def merge_failures(
    heuristic: list[FailureInstance],
    llm: list[FailureInstance],
) -> list[FailureInstance]:
    """Merge heuristic and LLM findings, deduplicating overlaps.

    When both find the same subcategory, keep the one with higher confidence.
    LLM findings that are novel (not found by heuristics) are added with a
    source tag.
    """
    merged: dict[str, FailureInstance] = {}

    # Index heuristic findings by subcategory
    for f in heuristic:
        key = f"{f.subcategory.value}:{f.description[:50]}"
        if key not in merged or f.confidence > merged[key].confidence:
            merged[key] = f

    # Add/upgrade with LLM findings
    for f in llm:
        # Check if heuristics already found this subcategory
        existing_key = None
        for key, existing in merged.items():
            if existing.subcategory == f.subcategory:
                existing_key = key
                break

        if existing_key:
            # Keep the higher-confidence one
            if f.confidence > merged[existing_key].confidence:
                merged[existing_key] = f
        else:
            # Novel LLM finding — tag it via evidence
            if "[source: llm]" not in f.evidence:
                f.evidence.append("[source: llm]")
            key = f"{f.subcategory.value}:{f.description[:50]}"
            merged[key] = f

    return sorted(merged.values(), key=lambda f: f.confidence, reverse=True)
