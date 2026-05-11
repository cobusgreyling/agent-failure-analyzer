"""
Failure fingerprinting.

Generates stable hashes for failure instances to enable
deduplication, tracking, and cross-session matching.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

from .models import AnalysisResult, FailureInstance


def fingerprint_failure(failure: FailureInstance) -> str:
    """Generate a stable fingerprint for a failure instance.

    The fingerprint is based on category, subcategory, and
    the first piece of evidence (normalized). This allows matching
    failures across sessions even when descriptions differ slightly.
    """
    parts = [
        failure.category.value,
        failure.subcategory.value,
    ]

    # Add normalized evidence for specificity
    if failure.evidence:
        # Normalize: lowercase, strip whitespace, truncate
        normalized = failure.evidence[0].lower().strip()[:200]
        # Remove variable parts (numbers, hashes, paths)
        import re
        normalized = re.sub(r"\d+", "N", normalized)
        normalized = re.sub(r"/[\w./]+", "/PATH", normalized)
        normalized = re.sub(r"0x[a-f0-9]+", "ADDR", normalized)
        parts.append(normalized)

    content = "|".join(parts)
    return hashlib.sha256(content.encode()).hexdigest()[:16]


def fingerprint_short(failure: FailureInstance) -> str:
    """Generate a shorter fingerprint based only on category + subcategory.

    Useful for grouping similar failures regardless of evidence details.
    """
    content = f"{failure.category.value}|{failure.subcategory.value}"
    return hashlib.sha256(content.encode()).hexdigest()[:8]


@dataclass
class DedupResult:
    """Result of deduplicating failures across sessions."""

    unique_fingerprints: dict[str, FailureInstance] = field(default_factory=dict)
    occurrence_count: dict[str, int] = field(default_factory=dict)
    session_map: dict[str, list[str]] = field(default_factory=dict)


def deduplicate_failures(results: list[AnalysisResult]) -> DedupResult:
    """Deduplicate failures across multiple analysis results.

    Returns unique failures with occurrence counts and session mapping.
    """
    dedup = DedupResult()

    for result in results:
        session_id = result.session.session_id
        for failure in result.failures:
            fp = fingerprint_failure(failure)

            if fp not in dedup.unique_fingerprints:
                dedup.unique_fingerprints[fp] = failure

            dedup.occurrence_count[fp] = dedup.occurrence_count.get(fp, 0) + 1
            dedup.session_map.setdefault(fp, []).append(session_id)

    return dedup
