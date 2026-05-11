"""Tests for the fingerprint module."""

from agent_failure_analyzer.fingerprint import (
    DedupResult,
    deduplicate_failures,
    fingerprint_failure,
    fingerprint_short,
)
from agent_failure_analyzer.models import (
    AgentFramework,
    AgentSession,
    AnalysisResult,
    FailureInstance,
    SessionOutcome,
)
from agent_failure_analyzer.taxonomy import (
    FailureCategory,
    FailureSubcategory,
    Severity,
)


def _make_failure(subcat, evidence=None):
    return FailureInstance(
        category=FailureCategory.TOOL_MISUSE,
        subcategory=subcat,
        severity=Severity.HIGH,
        description="test",
        evidence=evidence or [],
        confidence=0.9,
    )


class TestFingerprint:
    def test_stable_fingerprint(self):
        f = _make_failure(FailureSubcategory.INVALID_TOOL_ARGS, ["bad argument"])
        fp1 = fingerprint_failure(f)
        fp2 = fingerprint_failure(f)
        assert fp1 == fp2
        assert len(fp1) == 16

    def test_different_subcategories_differ(self):
        f1 = _make_failure(FailureSubcategory.INVALID_TOOL_ARGS)
        f2 = _make_failure(FailureSubcategory.WRONG_TOOL_SELECTED)
        assert fingerprint_failure(f1) != fingerprint_failure(f2)

    def test_short_fingerprint(self):
        f = _make_failure(FailureSubcategory.INVALID_TOOL_ARGS)
        fp = fingerprint_short(f)
        assert len(fp) == 8

    def test_short_fingerprint_ignores_evidence(self):
        f1 = _make_failure(FailureSubcategory.INVALID_TOOL_ARGS, ["evidence a"])
        f2 = _make_failure(FailureSubcategory.INVALID_TOOL_ARGS, ["evidence b"])
        assert fingerprint_short(f1) == fingerprint_short(f2)

    def test_normalizes_numbers_in_evidence(self):
        f1 = _make_failure(FailureSubcategory.INVALID_TOOL_ARGS, ["error at line 42"])
        f2 = _make_failure(FailureSubcategory.INVALID_TOOL_ARGS, ["error at line 99"])
        assert fingerprint_failure(f1) == fingerprint_failure(f2)


class TestDeduplicate:
    def test_deduplicates_identical_failures(self):
        f = _make_failure(FailureSubcategory.INVALID_TOOL_ARGS, ["same evidence"])
        session = AgentSession(
            session_id="s1",
            framework=AgentFramework.GENERIC,
            outcome=SessionOutcome.FAILURE,
        )
        results = [
            AnalysisResult(session=session, failures=[f], risk_score=0.5),
            AnalysisResult(
                session=AgentSession(
                    session_id="s2",
                    framework=AgentFramework.GENERIC,
                    outcome=SessionOutcome.FAILURE,
                ),
                failures=[f],
                risk_score=0.5,
            ),
        ]
        dedup = deduplicate_failures(results)
        assert isinstance(dedup, DedupResult)
        assert len(dedup.unique_fingerprints) == 1
        fp = next(iter(dedup.occurrence_count))
        assert dedup.occurrence_count[fp] == 2
        assert len(dedup.session_map[fp]) == 2

    def test_distinct_failures_not_merged(self):
        f1 = _make_failure(FailureSubcategory.INVALID_TOOL_ARGS, ["evidence a"])
        f2 = _make_failure(FailureSubcategory.WRONG_TOOL_SELECTED, ["evidence b"])
        session = AgentSession(
            session_id="s1",
            framework=AgentFramework.GENERIC,
            outcome=SessionOutcome.FAILURE,
        )
        results = [AnalysisResult(session=session, failures=[f1, f2], risk_score=0.5)]
        dedup = deduplicate_failures(results)
        assert len(dedup.unique_fingerprints) == 2
