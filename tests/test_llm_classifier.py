"""Tests for the LLM classifier (mocked — no API key needed)."""

from unittest.mock import MagicMock

from agent_failure_analyzer.analyzers.llm_classifier import (
    LLMClassifier,
    _format_session_transcript,
    merge_failures,
    needs_llm_review,
)
from agent_failure_analyzer.models import (
    AgentFramework,
    AgentSession,
    EventType,
    FailureInstance,
    SessionEvent,
    SessionOutcome,
)
from agent_failure_analyzer.taxonomy import (
    FailureCategory,
    FailureSubcategory,
    Severity,
)


def _make_session(
    outcome=SessionOutcome.FAILURE, num_events=5, has_errors=False
) -> AgentSession:
    events = []
    for i in range(num_events):
        if has_errors and i == num_events - 1:
            events.append(SessionEvent(
                event_type=EventType.ERROR,
                content="Something went wrong",
                error_message="Something went wrong",
            ))
        else:
            events.append(SessionEvent(
                event_type=EventType.ASSISTANT_MESSAGE,
                content=f"Response {i}",
            ))
    return AgentSession(
        session_id="test-session",
        framework=AgentFramework.GENERIC,
        events=events,
        outcome=outcome,
    )


class TestFormatTranscript:
    def test_basic_formatting(self):
        session = _make_session(num_events=3)
        transcript = _format_session_transcript(session)
        assert "test-session" in transcript
        assert "generic" in transcript
        assert "Response 0" in transcript
        assert "Response 2" in transcript

    def test_truncates_long_content(self):
        session = AgentSession(
            session_id="long",
            framework=AgentFramework.GENERIC,
            events=[
                SessionEvent(
                    event_type=EventType.TOOL_RESULT,
                    content="x" * 5000,
                )
            ],
            outcome=SessionOutcome.UNKNOWN,
        )
        transcript = _format_session_transcript(session)
        assert "truncated" in transcript

    def test_limits_events(self):
        session = _make_session(num_events=150)
        transcript = _format_session_transcript(session, max_events=50)
        assert "100 more events truncated" in transcript


class TestNeedsLLMReview:
    def test_failed_session_no_heuristics(self):
        session = _make_session(outcome=SessionOutcome.FAILURE)
        assert needs_llm_review([], session) is True

    def test_failed_session_low_confidence(self):
        session = _make_session(outcome=SessionOutcome.FAILURE)
        failures = [
            FailureInstance(
                category=FailureCategory.UNKNOWN,
                subcategory=FailureSubcategory.UNCLASSIFIED,
                severity=Severity.LOW,
                description="Something",
                confidence=0.3,
            )
        ]
        assert needs_llm_review(failures, session) is True

    def test_long_session_no_findings(self):
        session = _make_session(outcome=SessionOutcome.UNKNOWN, num_events=25)
        assert needs_llm_review([], session) is True

    def test_good_session_with_findings(self):
        session = _make_session(outcome=SessionOutcome.SUCCESS, num_events=5)
        failures = [
            FailureInstance(
                category=FailureCategory.TOOL_MISUSE,
                subcategory=FailureSubcategory.INVALID_TOOL_ARGS,
                severity=Severity.MEDIUM,
                description="Bad args",
                confidence=0.8,
            )
        ]
        assert needs_llm_review(failures, session) is False


class TestMergeFailures:
    def test_dedup_same_subcategory_keeps_higher_confidence(self):
        heuristic = [
            FailureInstance(
                category=FailureCategory.TOOL_MISUSE,
                subcategory=FailureSubcategory.INVALID_TOOL_ARGS,
                severity=Severity.MEDIUM,
                description="Heuristic finding",
                confidence=0.6,
            )
        ]
        llm = [
            FailureInstance(
                category=FailureCategory.TOOL_MISUSE,
                subcategory=FailureSubcategory.INVALID_TOOL_ARGS,
                severity=Severity.HIGH,
                description="LLM finding with better detail",
                confidence=0.9,
            )
        ]
        merged = merge_failures(heuristic, llm)
        assert len(merged) == 1
        assert merged[0].confidence == 0.9
        assert merged[0].description == "LLM finding with better detail"

    def test_novel_llm_findings_added(self):
        heuristic = [
            FailureInstance(
                category=FailureCategory.TOOL_MISUSE,
                subcategory=FailureSubcategory.INVALID_TOOL_ARGS,
                severity=Severity.MEDIUM,
                description="Heuristic",
                confidence=0.8,
            )
        ]
        llm = [
            FailureInstance(
                category=FailureCategory.INSTRUCTION_DRIFT,
                subcategory=FailureSubcategory.GOAL_FORGOTTEN,
                severity=Severity.HIGH,
                description="Agent drifted from goal",
                confidence=0.85,
            )
        ]
        merged = merge_failures(heuristic, llm)
        assert len(merged) == 2
        subcats = {f.subcategory for f in merged}
        assert FailureSubcategory.INVALID_TOOL_ARGS in subcats
        assert FailureSubcategory.GOAL_FORGOTTEN in subcats

    def test_empty_inputs(self):
        assert merge_failures([], []) == []
        f = FailureInstance(
            category=FailureCategory.UNKNOWN,
            subcategory=FailureSubcategory.UNCLASSIFIED,
            severity=Severity.LOW,
            description="test",
            confidence=0.5,
        )
        assert len(merge_failures([f], [])) == 1
        assert len(merge_failures([], [f])) == 1


class TestLLMClassifierParsing:
    def test_parse_valid_response(self):
        mock_response = MagicMock()
        mock_block = MagicMock()
        mock_block.text = '''[
            {
                "category": "instruction_drift",
                "subcategory": "goal_forgotten",
                "severity": "high",
                "description": "Agent forgot the user's original request",
                "evidence": ["User said X but agent did Y"],
                "confidence": 0.85
            }
        ]'''
        mock_response.content = [mock_block]

        results = LLMClassifier._parse_response(mock_response)
        assert len(results) == 1
        assert results[0].category == FailureCategory.INSTRUCTION_DRIFT
        assert results[0].subcategory == FailureSubcategory.GOAL_FORGOTTEN
        assert results[0].severity == Severity.HIGH
        assert results[0].confidence == 0.85

    def test_parse_markdown_wrapped_response(self):
        mock_response = MagicMock()
        mock_block = MagicMock()
        mock_block.text = '''```json
[
    {
        "category": "hallucination",
        "subcategory": "fabricated_file_path",
        "severity": "medium",
        "description": "Agent referenced non-existent file",
        "evidence": [],
        "confidence": 0.7
    }
]
```'''
        mock_response.content = [mock_block]

        results = LLMClassifier._parse_response(mock_response)
        assert len(results) == 1
        assert results[0].category == FailureCategory.HALLUCINATION

    def test_parse_empty_array(self):
        mock_response = MagicMock()
        mock_block = MagicMock()
        mock_block.text = "[]"
        mock_response.content = [mock_block]

        results = LLMClassifier._parse_response(mock_response)
        assert results == []

    def test_parse_invalid_json(self):
        mock_response = MagicMock()
        mock_block = MagicMock()
        mock_block.text = "This is not JSON at all"
        mock_response.content = [mock_block]

        results = LLMClassifier._parse_response(mock_response)
        assert len(results) == 1
        assert results[0].subcategory == FailureSubcategory.UNCLASSIFIED

    def test_parse_invalid_enum_values_skipped(self):
        mock_response = MagicMock()
        mock_block = MagicMock()
        mock_block.text = (
            '[{"category": "not_a_real_category", "subcategory": "invalid",'
            ' "severity": "high", "description": "bad", "confidence": 0.5},'
            '{"category": "tool_misuse", "subcategory": "invalid_tool_args",'
            ' "severity": "medium", "description": "good", "confidence": 0.8}]'
        )
        mock_response.content = [mock_block]

        results = LLMClassifier._parse_response(mock_response)
        assert len(results) == 1
        assert results[0].subcategory == FailureSubcategory.INVALID_TOOL_ARGS
