"""Tests for the anonymizer module."""

from agent_failure_analyzer.anonymizer import (
    AnonymizeStats,
    anonymize_event,
    anonymize_session,
    anonymize_text,
)
from agent_failure_analyzer.models import (
    AgentFramework,
    AgentSession,
    EventType,
    SessionEvent,
    SessionOutcome,
)


class TestAnonymizeText:
    def test_redacts_email(self):
        text = "Contact user@example.com for details"
        cleaned, counts = anonymize_text(text)
        assert "[REDACTED_EMAIL]" in cleaned
        assert "user@example.com" not in cleaned
        assert counts.get("email", 0) >= 1

    def test_redacts_api_key(self):
        text = "api_key: sk-abcdefghijklmnopqrstuvwxyz12345678"
        cleaned, counts = anonymize_text(text)
        assert "[REDACTED_API_KEY]" in cleaned
        assert counts.get("api_key", 0) >= 1

    def test_redacts_ip_address(self):
        text = "Server at 192.168.1.100 is down"
        cleaned, counts = anonymize_text(text)
        assert "[REDACTED_IP]" in cleaned
        assert "192.168.1.100" not in cleaned

    def test_redacts_aws_key(self):
        text = "Use AKIAIOSFODNN7EXAMPLE for access"
        cleaned, counts = anonymize_text(text)
        assert "[REDACTED_AWS_KEY]" in cleaned

    def test_redacts_jwt(self):
        # JWT placed without a "token:" prefix to avoid the api_key pattern matching first
        text = "auth eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.abc123def456ghi"
        cleaned, counts = anonymize_text(text)
        assert "[REDACTED_JWT]" in cleaned

    def test_redacts_home_paths(self):
        text = "File at /Users/johndoe/Documents/secret.txt"
        cleaned, counts = anonymize_text(text, redact_paths=True)
        assert "/home/[REDACTED_USER]" in cleaned
        assert "johndoe" not in cleaned

    def test_skips_paths_when_disabled(self):
        text = "File at /Users/johndoe/Documents/secret.txt"
        cleaned, counts = anonymize_text(text, redact_paths=False)
        assert "johndoe" in cleaned

    def test_no_redaction_needed(self):
        text = "This is a normal message with no PII"
        cleaned, counts = anonymize_text(text)
        assert cleaned == text
        assert counts == {}


class TestAnonymizeEvent:
    def test_anonymizes_content(self):
        event = SessionEvent(
            event_type=EventType.ASSISTANT_MESSAGE,
            content="Send to user@example.com",
        )
        new_event, modified = anonymize_event(event)
        assert modified
        assert "[REDACTED_EMAIL]" in new_event.content

    def test_anonymizes_error_message(self):
        event = SessionEvent(
            event_type=EventType.ERROR,
            content="Failed",
            error_message="Auth failed for user@example.com",
        )
        new_event, modified = anonymize_event(event)
        assert modified
        assert "[REDACTED_EMAIL]" in new_event.error_message

    def test_unmodified_when_clean(self):
        event = SessionEvent(
            event_type=EventType.USER_MESSAGE,
            content="Hello world",
        )
        new_event, modified = anonymize_event(event)
        assert not modified


class TestAnonymizeSession:
    def test_anonymizes_full_session(self):
        session = AgentSession(
            session_id="test-session",
            framework=AgentFramework.GENERIC,
            events=[
                SessionEvent(
                    event_type=EventType.USER_MESSAGE,
                    content="My email is admin@corp.com",
                ),
                SessionEvent(
                    event_type=EventType.ASSISTANT_MESSAGE,
                    content="I'll contact admin@corp.com",
                ),
            ],
            outcome=SessionOutcome.SUCCESS,
            metadata={"user": "admin@corp.com"},
        )
        new_session, stats = anonymize_session(session)
        assert isinstance(stats, AnonymizeStats)
        assert stats.events_modified >= 1
        # Original is unchanged
        assert "admin@corp.com" in session.events[0].content
        # New session is redacted
        assert "admin@corp.com" not in new_session.events[0].content
