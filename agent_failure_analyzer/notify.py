"""
Webhook and Slack notifications for high-risk sessions.

Sends alerts when sessions exceed configurable risk thresholds,
enabling integration with incident response workflows.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass

from .models import AnalysisResult, BatchAnalysisResult


@dataclass
class NotifyConfig:
    """Configuration for notifications."""

    webhook_url: str | None = None
    slack_webhook_url: str | None = None
    risk_threshold: float = 0.5
    min_failures: int = 1
    include_evidence: bool = False


def should_notify(result: AnalysisResult, config: NotifyConfig) -> bool:
    """Check if a result warrants a notification."""
    return (
        result.risk_score >= config.risk_threshold
        and len(result.failures) >= config.min_failures
    )


def _build_payload(result: AnalysisResult, config: NotifyConfig) -> dict:
    """Build a generic webhook payload."""
    session = result.session
    failures_summary = [
        {
            "category": f.category.value,
            "subcategory": f.subcategory.value,
            "severity": f.severity.value,
            "description": f.description,
            **({"evidence": f.evidence[:2]} if config.include_evidence else {}),
        }
        for f in result.failures[:10]
    ]

    return {
        "event": "afa.high_risk_session",
        "session_id": session.session_id,
        "framework": session.framework.value,
        "model": session.model,
        "outcome": session.outcome.value,
        "risk_score": round(result.risk_score, 3),
        "failure_count": len(result.failures),
        "summary": result.summary,
        "failures": failures_summary,
    }


def _build_slack_payload(result: AnalysisResult, config: NotifyConfig) -> dict:
    """Build a Slack-formatted webhook payload."""
    session = result.session
    risk_pct = f"{result.risk_score:.0%}"
    failure_lines = "\n".join(
        f"  *{f.severity.value.upper()}*: {f.subcategory.value} — {f.description[:80]}"
        for f in result.failures[:5]
    )

    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"Agent Failure Alert — Risk {risk_pct}",
            },
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Session:*\n`{session.session_id[:24]}`"},
                {"type": "mrkdwn", "text": f"*Framework:*\n{session.framework.value}"},
                {"type": "mrkdwn", "text": f"*Risk Score:*\n{risk_pct}"},
                {"type": "mrkdwn", "text": f"*Failures:*\n{len(result.failures)}"},
            ],
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Top failures:*\n{failure_lines}",
            },
        },
    ]

    return {"blocks": blocks}


def _post_json(url: str, payload: dict) -> bool:
    """POST JSON to a URL. Returns True on success."""
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return 200 <= resp.status < 300
    except (urllib.error.URLError, OSError):
        return False


def send_notification(result: AnalysisResult, config: NotifyConfig) -> list[str]:
    """Send notifications for a high-risk result.

    Returns a list of destinations that were notified successfully.
    """
    sent: list[str] = []

    if config.webhook_url:
        payload = _build_payload(result, config)
        if _post_json(config.webhook_url, payload):
            sent.append("webhook")

    if config.slack_webhook_url:
        payload = _build_slack_payload(result, config)
        if _post_json(config.slack_webhook_url, payload):
            sent.append("slack")

    return sent


def notify_batch(batch: BatchAnalysisResult, config: NotifyConfig) -> int:
    """Send notifications for all high-risk results in a batch.

    Returns the number of notifications sent.
    """
    count = 0
    for result in batch.results:
        if should_notify(result, config):
            sent = send_notification(result, config)
            count += len(sent)
    return count
