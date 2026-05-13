"""Shared helpers for CLI commands.

Lives outside ``__init__`` so submodules can import from it without
inducing a circular import with the click ``main`` group.
"""

from __future__ import annotations

from rich.console import Console
from rich.table import Table
from rich.text import Text

console = Console()


def _filter_results(results, min_severity: str, min_confidence: float):
    """Filter failures by severity and confidence thresholds."""
    severity_order = ["info", "low", "medium", "high", "critical"]
    min_sev_idx = severity_order.index(min_severity)

    for result in results:
        result.failures = [
            f for f in result.failures
            if severity_order.index(f.severity.value) >= min_sev_idx
            and f.confidence >= min_confidence
        ]
    return results


def _print_cost_summary(results: list) -> None:
    """Print cost waste estimation for results."""
    from ..cost import estimate_waste

    table = Table(title="Cost Waste Estimation", border_style="yellow")
    table.add_column("Session", width=24)
    table.add_column("Total Tokens", justify="right", width=14)
    table.add_column("Wasted Tokens", justify="right", width=14)
    table.add_column("Waste %", justify="right", width=9)
    table.add_column("Est. Wasted $", justify="right", width=12)

    total_wasted_usd = 0.0
    for r in results:
        est = estimate_waste(r)
        total_wasted_usd += est.estimated_wasted_cost_usd
        if est.wasted_tokens > 0:
            waste_style = "red" if est.waste_ratio > 0.5 else "yellow"
            table.add_row(
                r.session.session_id[:24],
                f"{est.total_tokens:,}",
                Text(f"{est.wasted_tokens:,}", style=waste_style),
                Text(f"{est.waste_ratio:.0%}", style=waste_style),
                f"${est.estimated_wasted_cost_usd:.4f}",
            )

    if total_wasted_usd > 0:
        console.print(table)
        console.print(f"  [bold]Total estimated waste: ${total_wasted_usd:.4f}[/bold]\n")


def _store_batch(batch) -> None:
    """Store a batch of results to SQLite."""
    from ..storage import AnalysisStore
    db = AnalysisStore()
    db.save_batch(batch)
    console.print(f"[dim]Stored {batch.total_sessions} result(s) to {db.db_path}[/dim]")
    db.close()


def _send_notifications(
    results: list, webhook: str | None, slack: str | None, threshold: float
) -> None:
    """Send webhook/Slack notifications for high-risk results."""
    from ..models import BatchAnalysisResult
    from ..notify import NotifyConfig, notify_batch, should_notify

    config = NotifyConfig(
        webhook_url=webhook,
        slack_webhook_url=slack,
        risk_threshold=threshold,
    )

    high_risk = [r for r in results if should_notify(r, config)]
    if not high_risk:
        return

    # Build a minimal batch for notify_batch
    batch = BatchAnalysisResult(results=high_risk, total_sessions=len(high_risk))
    count = notify_batch(batch, config)
    if count:
        console.print(
            f"[dim]Sent {count} notification(s) for"
            f" {len(high_risk)} high-risk session(s)[/dim]"
        )
