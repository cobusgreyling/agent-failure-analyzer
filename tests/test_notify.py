"""Tests for the notify module."""

from unittest.mock import patch

from agent_failure_analyzer.models import (
    AgentFramework,
    AgentSession,
    AnalysisResult,
    BatchAnalysisResult,
    FailureInstance,
    SessionOutcome,
)
from agent_failure_analyzer.notify import (
    NotifyConfig,
    _build_payload,
    _build_slack_payload,
    notify_batch,
    should_notify,
)
from agent_failure_analyzer.taxonomy import (
    FailureCategory,
    FailureSubcategory,
    Severity,
)


def _make_result(risk_score=0.7, failure_count=2):
    failures = [
        FailureInstance(
            category=FailureCategory.TOOL_MISUSE,
            subcategory=FailureSubcategory.INVALID_TOOL_ARGS,
            severity=Severity.HIGH,
            description=f"failure {i}",
            confidence=0.8,
        )
        for i in range(failure_count)
    ]
    session = AgentSession(
        session_id="test-session",
        framework=AgentFramework.GENERIC,
        model="gpt-4-turbo",
        outcome=SessionOutcome.FAILURE,
    )
    return AnalysisResult(
        session=session,
        failures=failures,
        risk_score=risk_score,
        summary="Test session with failures",
    )


class TestShouldNotify:
    def test_above_threshold(self):
        result = _make_result(risk_score=0.7)
        config = NotifyConfig(risk_threshold=0.5)
        assert should_notify(result, config)

    def test_below_threshold(self):
        result = _make_result(risk_score=0.3)
        config = NotifyConfig(risk_threshold=0.5)
        assert not should_notify(result, config)

    def test_min_failures_check(self):
        result = _make_result(risk_score=0.8, failure_count=1)
        config = NotifyConfig(risk_threshold=0.5, min_failures=3)
        assert not should_notify(result, config)


class TestBuildPayload:
    def test_generic_payload(self):
        result = _make_result()
        config = NotifyConfig()
        payload = _build_payload(result, config)
        assert payload["event"] == "afa.high_risk_session"
        assert payload["session_id"] == "test-session"
        assert payload["framework"] == "generic"
        assert payload["risk_score"] == 0.7
        assert len(payload["failures"]) == 2

    def test_payload_with_evidence(self):
        result = _make_result()
        config = NotifyConfig(include_evidence=True)
        payload = _build_payload(result, config)
        # Evidence key should be present in failure entries
        for f in payload["failures"]:
            assert "evidence" in f

    def test_slack_payload(self):
        result = _make_result()
        config = NotifyConfig()
        payload = _build_slack_payload(result, config)
        assert "blocks" in payload
        assert len(payload["blocks"]) == 3
        # Header should contain risk
        header = payload["blocks"][0]
        assert "Risk" in header["text"]["text"]


class TestNotifyBatch:
    @patch("agent_failure_analyzer.notify._post_json", return_value=True)
    def test_sends_webhook(self, mock_post):
        result = _make_result(risk_score=0.8)
        config = NotifyConfig(
            webhook_url="https://example.com/hook",
            risk_threshold=0.5,
        )
        batch = BatchAnalysisResult(results=[result], total_sessions=1)
        count = notify_batch(batch, config)
        assert count == 1
        mock_post.assert_called_once()

    @patch("agent_failure_analyzer.notify._post_json", return_value=True)
    def test_sends_both_webhook_and_slack(self, mock_post):
        result = _make_result(risk_score=0.8)
        config = NotifyConfig(
            webhook_url="https://example.com/hook",
            slack_webhook_url="https://hooks.slack.com/test",
            risk_threshold=0.5,
        )
        batch = BatchAnalysisResult(results=[result], total_sessions=1)
        count = notify_batch(batch, config)
        assert count == 2
        assert mock_post.call_count == 2

    @patch("agent_failure_analyzer.notify._post_json", return_value=False)
    def test_handles_post_failure(self, mock_post):
        result = _make_result(risk_score=0.8)
        config = NotifyConfig(
            webhook_url="https://example.com/hook",
            risk_threshold=0.5,
        )
        batch = BatchAnalysisResult(results=[result], total_sessions=1)
        count = notify_batch(batch, config)
        assert count == 0

    def test_skips_low_risk(self):
        result = _make_result(risk_score=0.2)
        config = NotifyConfig(
            webhook_url="https://example.com/hook",
            risk_threshold=0.5,
        )
        batch = BatchAnalysisResult(results=[result], total_sessions=1)
        count = notify_batch(batch, config)
        assert count == 0
