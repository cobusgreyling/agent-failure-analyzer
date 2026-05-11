"""Rich terminal report output."""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from ..models import AnalysisResult, BatchAnalysisResult
from ..taxonomy import CATEGORY_DESCRIPTIONS, Severity


SEVERITY_COLORS = {
    Severity.CRITICAL: "bold red",
    Severity.HIGH: "red",
    Severity.MEDIUM: "yellow",
    Severity.LOW: "cyan",
    Severity.INFO: "dim",
}

RISK_COLORS = [
    (0.0, "green"),
    (0.3, "yellow"),
    (0.6, "red"),
    (0.8, "bold red"),
]


def _risk_color(score: float) -> str:
    color = "green"
    for threshold, c in RISK_COLORS:
        if score >= threshold:
            color = c
    return color


class TerminalReporter:
    """Render analysis results to the terminal using Rich."""

    def __init__(self, console: Console | None = None) -> None:
        self.console = console or Console()

    def print_session(self, result: AnalysisResult) -> None:
        """Print a single session analysis."""
        session = result.session
        c = self.console

        # Header
        risk_color = _risk_color(result.risk_score)
        header = Text()
        header.append("Session: ", style="bold")
        header.append(session.session_id, style="bold cyan")
        header.append("  |  Framework: ", style="dim")
        header.append(session.framework.value, style="bold")
        header.append("  |  Risk: ", style="dim")
        header.append(f"{result.risk_score:.0%}", style=risk_color)

        c.print(Panel(header, border_style="blue"))

        # Session metadata
        meta_table = Table(show_header=False, box=None, padding=(0, 2))
        meta_table.add_column("Key", style="dim")
        meta_table.add_column("Value")

        if session.model:
            meta_table.add_row("Model", session.model)
        if session.total_turns is not None:
            meta_table.add_row("Turns", str(session.total_turns))
        if session.total_tokens is not None:
            meta_table.add_row("Tokens", f"{session.total_tokens:,}")
        meta_table.add_row("Events", str(len(session.events)))
        meta_table.add_row("Outcome", session.outcome.value)

        c.print(meta_table)
        c.print()

        if not result.failures:
            c.print("  [green]No failures detected.[/green]")
            c.print()
            return

        # Failures table
        fail_table = Table(title=f"{len(result.failures)} Failure(s)", border_style="red")
        fail_table.add_column("#", style="dim", width=3)
        fail_table.add_column("Severity", width=10)
        fail_table.add_column("Category", width=22)
        fail_table.add_column("Subcategory", width=28)
        fail_table.add_column("Description")
        fail_table.add_column("Conf", width=5, justify="right")

        for idx, failure in enumerate(result.failures, 1):
            sev_style = SEVERITY_COLORS.get(failure.severity, "")
            fail_table.add_row(
                str(idx),
                Text(failure.severity.value.upper(), style=sev_style),
                failure.category.value,
                failure.subcategory.value,
                failure.description[:80],
                f"{failure.confidence:.0%}",
            )

        c.print(fail_table)
        c.print()

        # Evidence details (top 5 failures)
        for idx, failure in enumerate(result.failures[:5], 1):
            if failure.evidence:
                c.print(f"  [dim]#{idx} Evidence:[/dim]")
                for ev in failure.evidence[:3]:
                    c.print(f"    [dim]{ev[:120]}[/dim]")
                c.print()

    def print_batch(self, batch: BatchAnalysisResult) -> None:
        """Print batch analysis summary."""
        c = self.console

        # Header
        c.print(Panel(
            Text.assemble(
                ("Agent Failure Analysis Report", "bold"),
                f"\n{batch.total_sessions} sessions analyzed",
            ),
            border_style="blue",
        ))

        # Overview stats
        overview = Table(show_header=False, box=None, padding=(0, 3))
        overview.add_column("Key", style="bold")
        overview.add_column("Value")
        overview.add_row("Total Sessions", str(batch.total_sessions))
        overview.add_row(
            "Failed Sessions",
            Text(str(batch.failed_sessions), style="red" if batch.failed_sessions else "green"),
        )
        total_failures = sum(len(r.failures) for r in batch.results)
        overview.add_row("Total Failures", str(total_failures))
        if batch.total_sessions > 0:
            fail_rate = batch.failed_sessions / batch.total_sessions
            overview.add_row(
                "Failure Rate",
                Text(f"{fail_rate:.0%}", style="red" if fail_rate > 0.3 else "green"),
            )
        c.print(overview)
        c.print()

        # Category distribution
        if batch.category_counts:
            cat_table = Table(title="Failures by Category", border_style="yellow")
            cat_table.add_column("Category", width=25)
            cat_table.add_column("Count", justify="right", width=7)
            cat_table.add_column("Description")

            for cat, count in sorted(
                batch.category_counts.items(), key=lambda x: x[1], reverse=True
            ):
                desc = ""
                from ..taxonomy import FailureCategory
                for fc in FailureCategory:
                    if fc.value == cat:
                        desc = CATEGORY_DESCRIPTIONS.get(fc, "")
                        break
                cat_table.add_row(cat, str(count), desc[:60])

            c.print(cat_table)
            c.print()

        # Severity distribution
        if batch.severity_counts:
            sev_table = Table(title="Failures by Severity", border_style="red")
            sev_table.add_column("Severity", width=12)
            sev_table.add_column("Count", justify="right", width=7)
            sev_table.add_column("Bar", width=30)

            max_count = max(batch.severity_counts.values()) if batch.severity_counts else 1
            severity_order = ["critical", "high", "medium", "low", "info"]
            for sev in severity_order:
                count = batch.severity_counts.get(sev, 0)
                if count > 0:
                    bar_len = int(count / max_count * 25)
                    sev_enum = Severity(sev)
                    color = SEVERITY_COLORS.get(sev_enum, "")
                    sev_table.add_row(
                        Text(sev.upper(), style=color),
                        str(count),
                        Text("█" * bar_len, style=color),
                    )

            c.print(sev_table)
            c.print()

        # Top failure subcategories
        if batch.top_failures:
            top_table = Table(title="Top Failure Types", border_style="magenta")
            top_table.add_column("#", style="dim", width=3)
            top_table.add_column("Subcategory", width=30)
            top_table.add_column("Count", justify="right", width=7)

            for idx, (subcat, count) in enumerate(batch.top_failures[:10], 1):
                top_table.add_row(str(idx), subcat, str(count))

            c.print(top_table)
            c.print()

        # Framework distribution
        if batch.framework_counts:
            fw_table = Table(title="Sessions by Framework", border_style="cyan")
            fw_table.add_column("Framework", width=20)
            fw_table.add_column("Sessions", justify="right", width=10)

            for fw, count in sorted(
                batch.framework_counts.items(), key=lambda x: x[1], reverse=True
            ):
                fw_table.add_row(fw, str(count))

            c.print(fw_table)
            c.print()

        # Per-session summaries (riskiest first)
        risky = sorted(batch.results, key=lambda r: r.risk_score, reverse=True)
        if risky and any(r.failures for r in risky):
            c.print(Panel("Session Details (by risk)", border_style="red"))
            for r in risky[:10]:
                if r.failures:
                    self.print_session(r)
