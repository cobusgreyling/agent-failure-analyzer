"""
Comparative framework report.

Compares failure patterns, risk scores, and token usage across
different agent frameworks to identify which frameworks perform best.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from rich.console import Console
from rich.table import Table
from rich.text import Text

from .models import BatchAnalysisResult


@dataclass
class FrameworkStats:
    """Aggregated stats for a single framework."""

    name: str = ""
    session_count: int = 0
    failure_count: int = 0
    avg_risk: float = 0.0
    avg_failures_per_session: float = 0.0
    avg_tokens: int = 0
    top_failures: list[tuple[str, int]] = field(default_factory=list)
    severity_dist: dict[str, int] = field(default_factory=dict)


@dataclass
class ComparisonReport:
    """Cross-framework comparison results."""

    frameworks: list[FrameworkStats] = field(default_factory=list)
    best_framework: str = ""
    worst_framework: str = ""
    total_sessions: int = 0


def compare_frameworks(batch: BatchAnalysisResult) -> ComparisonReport:
    """Build a cross-framework comparison from batch results."""
    report = ComparisonReport(total_sessions=batch.total_sessions)

    # Group by framework
    fw_results: dict[str, list] = {}
    for r in batch.results:
        fw = r.session.framework.value
        fw_results.setdefault(fw, []).append(r)

    if len(fw_results) < 1:
        return report

    for fw_name, results in fw_results.items():
        stats = FrameworkStats(name=fw_name, session_count=len(results))

        total_risk = 0.0
        total_failures = 0
        total_tokens = 0
        subcat_counts: Counter[str] = Counter()
        sev_counts: Counter[str] = Counter()

        for r in results:
            total_risk += r.risk_score
            total_failures += len(r.failures)
            total_tokens += r.session.total_tokens or 0
            for f in r.failures:
                subcat_counts[f.subcategory.value] += 1
                sev_counts[f.severity.value] += 1

        stats.failure_count = total_failures
        stats.avg_risk = total_risk / len(results)
        stats.avg_failures_per_session = total_failures / len(results)
        stats.avg_tokens = total_tokens // len(results) if total_tokens > 0 else 0
        stats.top_failures = subcat_counts.most_common(5)
        stats.severity_dist = dict(sev_counts)

        report.frameworks.append(stats)

    # Sort by average risk
    report.frameworks.sort(key=lambda f: f.avg_risk)

    if report.frameworks:
        report.best_framework = report.frameworks[0].name
        report.worst_framework = report.frameworks[-1].name

    return report


def print_comparison(report: ComparisonReport, console: Console | None = None) -> None:
    """Print the framework comparison to the terminal."""
    console = console or Console()

    if not report.frameworks:
        console.print("[yellow]No framework data to compare.[/yellow]")
        return

    # Summary table
    table = Table(title="Framework Comparison", border_style="blue")
    table.add_column("Framework", style="bold", width=15)
    table.add_column("Sessions", justify="right", width=10)
    table.add_column("Failures", justify="right", width=10)
    table.add_column("Avg/Session", justify="right", width=12)
    table.add_column("Avg Risk", justify="right", width=10)
    table.add_column("Avg Tokens", justify="right", width=12)

    for fw in report.frameworks:
        risk_style = "red" if fw.avg_risk > 0.5 else "yellow" if fw.avg_risk > 0.3 else "green"
        table.add_row(
            fw.name,
            str(fw.session_count),
            str(fw.failure_count),
            f"{fw.avg_failures_per_session:.1f}",
            Text(f"{fw.avg_risk:.0%}", style=risk_style),
            f"{fw.avg_tokens:,}" if fw.avg_tokens > 0 else "-",
        )

    console.print(table)
    console.print()

    # Top failures per framework
    for fw in report.frameworks:
        if fw.top_failures:
            console.print(f"[bold]{fw.name}[/bold] top failures:")
            for sub, cnt in fw.top_failures[:3]:
                console.print(f"  {sub}: {cnt}")
            console.print()

    if len(report.frameworks) > 1:
        console.print(
            f"[green]Best:[/green] {report.best_framework}  |  "
            f"[red]Worst:[/red] {report.worst_framework}"
        )
