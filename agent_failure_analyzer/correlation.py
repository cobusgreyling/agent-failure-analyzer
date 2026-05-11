"""
Multi-session correlation.

Detects patterns and common failure signatures that recur
across multiple sessions, revealing systemic issues.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from .models import BatchAnalysisResult


@dataclass
class CorrelationPattern:
    """A pattern detected across multiple sessions."""

    pattern_type: str
    description: str
    affected_sessions: list[str] = field(default_factory=list)
    frequency: int = 0
    confidence: float = 0.0


@dataclass
class CorrelationReport:
    """Results of multi-session correlation analysis."""

    patterns: list[CorrelationPattern] = field(default_factory=list)
    total_sessions: int = 0
    co_occurrence_matrix: dict[str, dict[str, int]] = field(default_factory=dict)


def correlate(batch: BatchAnalysisResult) -> CorrelationReport:
    """Analyze a batch of results for cross-session patterns."""
    report = CorrelationReport(total_sessions=batch.total_sessions)

    if not batch.results:
        return report

    # 1. Recurring failure subcategories (appear in 30%+ of sessions)
    subcat_sessions: dict[str, list[str]] = {}
    for r in batch.results:
        seen = set()
        for f in r.failures:
            sub = f.subcategory.value
            if sub not in seen:
                subcat_sessions.setdefault(sub, []).append(r.session.session_id)
                seen.add(sub)

    threshold = max(2, batch.total_sessions * 0.3)
    for sub, sessions in subcat_sessions.items():
        if len(sessions) >= threshold:
            pct = len(sessions) / batch.total_sessions
            report.patterns.append(CorrelationPattern(
                pattern_type="recurring_failure",
                description=(
                    f"'{sub}' appears in {len(sessions)}/{batch.total_sessions} "
                    f"sessions ({pct:.0%}) — likely a systemic issue."
                ),
                affected_sessions=sessions,
                frequency=len(sessions),
                confidence=min(0.95, 0.5 + pct * 0.5),
            ))

    # 2. Co-occurring failures (failures that tend to appear together)
    co_occur: Counter[tuple[str, str]] = Counter()
    for r in batch.results:
        subcats = sorted({f.subcategory.value for f in r.failures})
        for i in range(len(subcats)):
            for j in range(i + 1, len(subcats)):
                co_occur[(subcats[i], subcats[j])] += 1

    for (a, b), count in co_occur.most_common(10):
        if count >= 2:
            report.co_occurrence_matrix.setdefault(a, {})[b] = count
            report.co_occurrence_matrix.setdefault(b, {})[a] = count
            if count >= threshold:
                report.patterns.append(CorrelationPattern(
                    pattern_type="co_occurring",
                    description=(
                        f"'{a}' and '{b}' co-occur in {count} sessions — "
                        "may share a root cause."
                    ),
                    frequency=count,
                    confidence=min(0.9, count / batch.total_sessions),
                ))

    # 3. Framework-specific failures
    fw_failures: dict[str, Counter[str]] = {}
    for r in batch.results:
        fw = r.session.framework.value
        fw_failures.setdefault(fw, Counter())
        for f in r.failures:
            fw_failures[fw][f.subcategory.value] += 1

    if len(fw_failures) > 1:
        for fw, counts in fw_failures.items():
            for sub, cnt in counts.most_common(3):
                # Check if this failure is disproportionately common in this framework
                total_sub = sum(
                    fc.get(sub, 0) for fc in fw_failures.values()
                )
                if total_sub > 0 and cnt / total_sub > 0.7 and cnt >= 2:
                    report.patterns.append(CorrelationPattern(
                        pattern_type="framework_specific",
                        description=(
                            f"'{sub}' is concentrated in {fw} "
                            f"({cnt}/{total_sub} occurrences, "
                            f"{cnt/total_sub:.0%}) — may be framework-specific."
                        ),
                        frequency=cnt,
                        confidence=0.7,
                    ))

    # 4. Model-specific failures
    model_failures: dict[str, Counter[str]] = {}
    for r in batch.results:
        model = r.session.model or "unknown"
        model_failures.setdefault(model, Counter())
        for f in r.failures:
            model_failures[model][f.subcategory.value] += 1

    if len(model_failures) > 1:
        for model, counts in model_failures.items():
            if model == "unknown":
                continue
            for sub, cnt in counts.most_common(3):
                total_sub = sum(
                    mc.get(sub, 0) for mc in model_failures.values()
                )
                if total_sub > 0 and cnt / total_sub > 0.7 and cnt >= 2:
                    report.patterns.append(CorrelationPattern(
                        pattern_type="model_specific",
                        description=(
                            f"'{sub}' is concentrated in model '{model}' "
                            f"({cnt}/{total_sub} occurrences) — "
                            "may be model-specific behavior."
                        ),
                        frequency=cnt,
                        confidence=0.65,
                    ))

    # 5. Escalation pattern: sessions that start with low-severity
    #    failures and escalate to critical
    escalation_sessions = []
    for r in batch.results:
        if len(r.failures) < 2:
            continue
        severities = [f.severity.value for f in r.failures]
        sev_order = {"info": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}
        sev_nums = [sev_order.get(s, 0) for s in severities]
        if sev_nums and sev_nums[-1] > sev_nums[0] and sev_nums[-1] >= 3:
            escalation_sessions.append(r.session.session_id)

    if len(escalation_sessions) >= 2:
        report.patterns.append(CorrelationPattern(
            pattern_type="escalation",
            description=(
                f"{len(escalation_sessions)} sessions show failure escalation "
                "(low -> high/critical severity over time)."
            ),
            affected_sessions=escalation_sessions,
            frequency=len(escalation_sessions),
            confidence=0.6,
        ))

    # Sort patterns by frequency
    report.patterns.sort(key=lambda p: p.frequency, reverse=True)
    return report
