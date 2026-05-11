"""
Log anonymizer.

Strips PII, API keys, secrets, and sensitive file paths from
session logs before sharing or reporting.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .models import AgentSession, SessionEvent

# Patterns for sensitive data
_PATTERNS: list[tuple[str, str, re.Pattern[str]]] = [
    (
        "api_key",
        "[REDACTED_API_KEY]",
        re.compile(
            r"(?:sk-|api[_-]?key|token|bearer|authorization)"
            r"[\s:=]*['\"]?([a-zA-Z0-9_\-]{20,})['\"]?",
            re.IGNORECASE,
        ),
    ),
    (
        "email",
        "[REDACTED_EMAIL]",
        re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"),
    ),
    (
        "ip_address",
        "[REDACTED_IP]",
        re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b"),
    ),
    (
        "phone",
        "[REDACTED_PHONE]",
        re.compile(r"\+?\d{1,4}[\s.-]?\(?\d{1,4}\)?[\s.-]?\d{3,4}[\s.-]?\d{4}"),
    ),
    (
        "aws_key",
        "[REDACTED_AWS_KEY]",
        re.compile(r"(?:AKIA|ASIA)[A-Z0-9]{16}"),
    ),
    (
        "password",
        "[REDACTED_PASSWORD]",
        re.compile(
            r"(?:password|passwd|pwd|secret)[\s:=]*['\"]?([^\s'\"]{8,})['\"]?",
            re.IGNORECASE,
        ),
    ),
    (
        "ssh_key",
        "[REDACTED_SSH_KEY]",
        re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----"),
    ),
    (
        "jwt",
        "[REDACTED_JWT]",
        re.compile(r"eyJ[a-zA-Z0-9_-]{10,}\.eyJ[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]+"),
    ),
]

# Home directory path patterns
_HOME_PATTERN = re.compile(r"/(?:home|Users)/[a-zA-Z0-9_.-]+")


@dataclass
class AnonymizeStats:
    """Statistics from an anonymization pass."""

    total_redactions: int = 0
    redaction_types: dict[str, int] = field(default_factory=dict)
    events_modified: int = 0


def anonymize_text(text: str, redact_paths: bool = True) -> tuple[str, dict[str, int]]:
    """Anonymize a single text string. Returns (cleaned_text, redaction_counts)."""
    counts: dict[str, int] = {}

    for name, replacement, pattern in _PATTERNS:
        matches = pattern.findall(text)
        if matches:
            counts[name] = len(matches)
            text = pattern.sub(replacement, text)

    if redact_paths:
        path_matches = _HOME_PATTERN.findall(text)
        if path_matches:
            counts["home_path"] = len(path_matches)
            text = _HOME_PATTERN.sub("/home/[REDACTED_USER]", text)

    return text, counts


def anonymize_event(event: SessionEvent, redact_paths: bool = True) -> tuple[SessionEvent, bool]:
    """Anonymize a single session event. Returns (event, was_modified)."""
    modified = False

    new_content, counts = anonymize_text(event.content, redact_paths)
    if counts:
        modified = True
        event = event.model_copy(update={"content": new_content})

    if event.error_message:
        new_err, err_counts = anonymize_text(event.error_message, redact_paths)
        if err_counts:
            modified = True
            event = event.model_copy(update={"error_message": new_err})

    return event, modified


def anonymize_session(
    session: AgentSession,
    redact_paths: bool = True,
) -> tuple[AgentSession, AnonymizeStats]:
    """Anonymize an entire session. Returns a new session with PII removed."""
    stats = AnonymizeStats()
    new_events = []

    for event in session.events:
        new_event, was_modified = anonymize_event(event, redact_paths)
        new_events.append(new_event)
        if was_modified:
            stats.events_modified += 1

    # Anonymize session-level metadata
    new_meta = dict(session.metadata)
    for key in list(new_meta.keys()):
        if isinstance(new_meta[key], str):
            new_val, counts = anonymize_text(str(new_meta[key]), redact_paths)
            if counts:
                new_meta[key] = new_val
                for name, cnt in counts.items():
                    stats.redaction_types[name] = stats.redaction_types.get(name, 0) + cnt
                    stats.total_redactions += cnt

    new_session = session.model_copy(update={
        "events": new_events,
        "metadata": new_meta,
    })

    return new_session, stats
