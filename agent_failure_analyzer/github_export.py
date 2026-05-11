"""
Export failures to GitHub Issues.

Creates GitHub issues for high-severity failures found during analysis.
Requires: GITHUB_TOKEN environment variable or gh CLI authentication.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass

from .models import AnalysisResult, FailureInstance
from .remediation import get_remediation
from .taxonomy import Severity


@dataclass
class GitHubIssueResult:
    """Result of creating a GitHub issue."""

    success: bool
    issue_number: int | None = None
    issue_url: str | None = None
    error: str | None = None


def _build_issue_body(result: AnalysisResult, failure: FailureInstance) -> str:
    """Build a Markdown issue body for a failure."""
    session = result.session
    remediation = get_remediation(failure.subcategory)

    lines = [
        f"## Failure: {failure.subcategory.value}",
        "",
        f"**Category:** {failure.category.value}",
        f"**Severity:** {failure.severity.value.upper()}",
        f"**Confidence:** {failure.confidence:.0%}",
        f"**Session:** `{session.session_id}`",
        f"**Framework:** {session.framework.value}",
        f"**Model:** {session.model or 'unknown'}",
        f"**Risk Score:** {result.risk_score:.0%}",
        "",
        "### Description",
        "",
        failure.description,
        "",
    ]

    if failure.evidence:
        lines.append("### Evidence")
        lines.append("")
        for ev in failure.evidence[:3]:
            cleaned = ev[:300].replace("`", "'")
            lines.append(f"```\n{cleaned}\n```")
        lines.append("")

    if remediation:
        lines.append("### Suggested Remediation")
        lines.append("")
        for r in remediation:
            lines.append(f"- {r}")
        lines.append("")

    lines.append("---")
    lines.append("*Created by [Agent Failure Analyzer](https://github.com/cobusgreyling/agent-failure-analyzer)*")

    return "\n".join(lines)


def _severity_to_label(severity: Severity) -> str:
    """Map severity to a GitHub label."""
    return {
        Severity.CRITICAL: "critical",
        Severity.HIGH: "high-priority",
        Severity.MEDIUM: "medium-priority",
        Severity.LOW: "low-priority",
        Severity.INFO: "info",
    }.get(severity, "bug")


def create_issue(
    result: AnalysisResult,
    failure: FailureInstance,
    repo: str,
    token: str | None = None,
    labels: list[str] | None = None,
    dry_run: bool = False,
) -> GitHubIssueResult:
    """Create a GitHub issue for a failure.

    Args:
        result: The analysis result containing the failure.
        failure: The specific failure to report.
        repo: GitHub repo in 'owner/repo' format.
        token: GitHub API token (falls back to GITHUB_TOKEN env var).
        labels: Additional labels to apply.
        dry_run: If True, print the issue without creating it.
    """
    token = token or os.environ.get("GITHUB_TOKEN", "")
    if not token and not dry_run:
        return GitHubIssueResult(
            success=False,
            error="No GitHub token. Set GITHUB_TOKEN or pass --token.",
        )

    title = (
        f"[AFA] {failure.severity.value.upper()}: "
        f"{failure.subcategory.value} in {result.session.session_id[:20]}"
    )
    body = _build_issue_body(result, failure)

    all_labels = [
        "agent-failure",
        _severity_to_label(failure.severity),
        failure.category.value,
    ]
    if labels:
        all_labels.extend(labels)

    if dry_run:
        return GitHubIssueResult(
            success=True,
            issue_number=0,
            issue_url=f"https://github.com/{repo}/issues/new (dry-run)",
            error=f"Title: {title}\nLabels: {all_labels}",
        )

    url = f"https://api.github.com/repos/{repo}/issues"
    payload = json.dumps({
        "title": title,
        "body": body,
        "labels": all_labels,
    }).encode()

    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read())
            return GitHubIssueResult(
                success=True,
                issue_number=data.get("number"),
                issue_url=data.get("html_url"),
            )
    except urllib.error.HTTPError as e:
        error_body = e.read().decode() if e.fp else str(e)
        return GitHubIssueResult(success=False, error=f"HTTP {e.code}: {error_body[:200]}")
    except Exception as e:
        return GitHubIssueResult(success=False, error=str(e))


def export_failures_to_issues(
    result: AnalysisResult,
    repo: str,
    token: str | None = None,
    min_severity: str = "high",
    dry_run: bool = False,
) -> list[GitHubIssueResult]:
    """Export all qualifying failures from a result as GitHub issues."""
    severity_order = ["info", "low", "medium", "high", "critical"]
    min_idx = severity_order.index(min_severity)

    results = []
    for failure in result.failures:
        sev_idx = severity_order.index(failure.severity.value)
        if sev_idx >= min_idx:
            issue_result = create_issue(
                result, failure, repo, token=token, dry_run=dry_run,
            )
            results.append(issue_result)

    return results
