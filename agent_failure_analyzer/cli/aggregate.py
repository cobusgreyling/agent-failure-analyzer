from __future__ import annotations

from pathlib import Path

import click
from rich.table import Table
from rich.text import Text

from ..analyzers.engine import AnalysisEngine
from ..taxonomy import (
    CATEGORY_DESCRIPTIONS,
    SUBCATEGORY_TO_CATEGORY,
    FailureCategory,
)
from . import main
from ._helpers import (
    console,
)

# ── compare ───────────────────────────────────────────────────────────

@main.command()
@click.argument("file_a", type=click.Path(exists=True))
@click.argument("file_b", type=click.Path(exists=True))
def compare(file_a: str, file_b: str):
    """Compare two session files side-by-side.

    Shows what changed between two runs — new failures, resolved failures,
    risk score changes.
    """
    engine = AnalysisEngine()
    results_a = engine.analyze_file(file_a)
    results_b = engine.analyze_file(file_b)

    if not results_a or not results_b:
        console.print("[yellow]Both files must contain at least one session.[/yellow]")
        return

    a = results_a[0]
    b = results_b[0]

    # Header
    table = Table(title="Session Comparison", border_style="blue")
    table.add_column("Metric", style="bold", width=20)
    table.add_column(f"A: {a.session.session_id[:20]}", width=30)
    table.add_column(f"B: {b.session.session_id[:20]}", width=30)
    table.add_column("Delta", width=15)

    # Risk
    risk_delta = b.risk_score - a.risk_score
    delta_style = "red" if risk_delta > 0 else "green" if risk_delta < 0 else "dim"
    table.add_row(
        "Risk Score",
        f"{a.risk_score:.0%}",
        f"{b.risk_score:.0%}",
        Text(f"{risk_delta:+.0%}", style=delta_style),
    )

    # Failures
    fa_count = len(a.failures)
    fb_count = len(b.failures)
    f_delta = fb_count - fa_count
    delta_style = "red" if f_delta > 0 else "green" if f_delta < 0 else "dim"
    table.add_row(
        "Failures", str(fa_count), str(fb_count),
        Text(f"{f_delta:+d}", style=delta_style),
    )

    # Outcome
    table.add_row("Outcome", a.session.outcome.value, b.session.outcome.value, "")

    # Events
    ea = len(a.session.events)
    eb = len(b.session.events)
    table.add_row("Events", str(ea), str(eb), f"{eb - ea:+d}")

    # Tokens
    ta = a.session.total_tokens or 0
    tb = b.session.total_tokens or 0
    token_delta = f"{tb - ta:+,}" if ta or tb else ""
    table.add_row(
        "Tokens",
        f"{ta:,}" if ta else "-",
        f"{tb:,}" if tb else "-",
        token_delta,
    )

    console.print(table)
    console.print()

    # Failure diff
    a_subcats = {f.subcategory.value for f in a.failures}
    b_subcats = {f.subcategory.value for f in b.failures}

    new_failures = b_subcats - a_subcats
    resolved = a_subcats - b_subcats
    common = a_subcats & b_subcats

    if new_failures:
        console.print("[bold red]New failures in B:[/bold red]")
        for sub in sorted(new_failures):
            console.print(f"  [red]+ {sub}[/red]")

    if resolved:
        console.print("[bold green]Resolved in B:[/bold green]")
        for sub in sorted(resolved):
            console.print(f"  [green]- {sub}[/green]")

    if common:
        console.print("[dim]Unchanged failures:[/dim]")
        for sub in sorted(common):
            console.print(f"  [dim]= {sub}[/dim]")

    if not new_failures and not resolved:
        console.print("[dim]No change in failure types.[/dim]")



# ── trend ─────────────────────────────────────────────────────────────

@main.command()
@click.option("--days", "-d", type=int, default=30, help="Number of days to show.")
def trend(days: int):
    """Show failure trends over time.

    Requires previous runs with --store flag to populate the database.
    """
    from ..storage import AnalysisStore

    store = AnalysisStore()
    total = store.get_total_runs()

    if total == 0:
        console.print("[yellow]No stored analysis runs found.[/yellow]")
        console.print("[dim]Run 'afa analyze <path> --store' first to populate the database.[/dim]")
        return

    console.print(f"[bold]Failure Trends[/bold] (last {days} days, {total} total runs)\n")

    # Daily trend
    daily = store.get_trend(days)
    if daily:
        trend_table = Table(title="Daily Summary", border_style="blue")
        trend_table.add_column("Date", width=12)
        trend_table.add_column("Sessions", justify="right", width=10)
        trend_table.add_column("Failed", justify="right", width=10)
        trend_table.add_column("Failures", justify="right", width=10)
        trend_table.add_column("Avg Risk", justify="right", width=10)
        trend_table.add_column("Trend", width=20)

        max_failures = max((d["total_failures"] or 0) for d in daily) or 1
        for d in daily:
            failures = d["total_failures"] or 0
            bar_len = int(failures / max_failures * 15)
            risk = d["avg_risk"] or 0
            risk_style = "red" if risk > 0.5 else "yellow" if risk > 0.3 else "green"
            trend_table.add_row(
                d["day"],
                str(d["total_sessions"]),
                str(d["failed_sessions"]),
                str(failures),
                Text(f"{risk:.0%}", style=risk_style),
                Text("█" * bar_len, style=risk_style),
            )

        console.print(trend_table)
        console.print()

    # Top failures
    top = store.get_top_failures(days)
    if top:
        top_table = Table(title="Top Failure Types", border_style="magenta")
        top_table.add_column("#", width=3, style="dim")
        top_table.add_column("Subcategory", width=30)
        top_table.add_column("Count", justify="right", width=7)

        for i, entry in enumerate(top, 1):
            top_table.add_row(str(i), entry["subcategory"], str(entry["count"]))

        console.print(top_table)
        console.print()

    # Framework stats
    fw = store.get_framework_stats(days)
    if fw:
        fw_table = Table(title="By Framework", border_style="cyan")
        fw_table.add_column("Framework", width=15)
        fw_table.add_column("Sessions", justify="right", width=10)
        fw_table.add_column("Failed", justify="right", width=10)
        fw_table.add_column("Avg Risk", justify="right", width=10)

        for entry in fw:
            risk = entry["avg_risk"] or 0
            fw_table.add_row(
                entry["framework"],
                str(entry["sessions"]),
                str(entry["failed"]),
                f"{risk:.0%}",
            )

        console.print(fw_table)

    store.close()



# ── taxonomy ──────────────────────────────────────────────────────────

@main.command()
def taxonomy():
    """Display the full failure taxonomy."""
    table = Table(title="Agent Failure Taxonomy", border_style="blue")
    table.add_column("Category", style="bold", width=25)
    table.add_column("Subcategories", width=35)
    table.add_column("Description")

    cat_subs: dict[FailureCategory, list[str]] = {}
    for sub, cat in SUBCATEGORY_TO_CATEGORY.items():
        cat_subs.setdefault(cat, []).append(sub.value)

    for cat in FailureCategory:
        subs = cat_subs.get(cat, [])
        desc = CATEGORY_DESCRIPTIONS.get(cat, "")
        table.add_row(
            cat.value,
            "\n".join(subs),
            desc,
        )

    console.print(table)



# ── correlate ────────────────────────────────────────────────────────

@main.command()
@click.argument("path", type=click.Path(exists=True))
def correlate(path: str):
    """Detect cross-session failure patterns.

    Analyzes multiple sessions to find recurring failures,
    co-occurring issues, and framework-specific problems.
    """
    from ..correlation import correlate as run_correlation

    engine = AnalysisEngine()
    p = Path(path)

    if p.is_dir():
        batch = engine.analyze_directory(p)
    else:
        results = engine.analyze_file(p)
        batch = engine.analyze_sessions([r.session for r in results])

    report = run_correlation(batch)

    console.print(
        f"\n[bold]Correlation Analysis:[/bold] "
        f"{report.total_sessions} sessions\n"
    )

    if not report.patterns:
        console.print("[green]No cross-session patterns detected.[/green]")
        return

    for i, pat in enumerate(report.patterns, 1):
        console.print(
            f"  [bold]{i}.[/bold] [{pat.pattern_type}] {pat.description}"
        )
        if pat.affected_sessions:
            console.print(
                f"     [dim]Sessions: "
                f"{', '.join(pat.affected_sessions[:5])}"
                f"{'...' if len(pat.affected_sessions) > 5 else ''}[/dim]"
            )

    if report.co_occurrence_matrix:
        console.print("\n[bold]Co-occurrence pairs:[/bold]")
        shown = set()
        for a, neighbors in report.co_occurrence_matrix.items():
            for b, cnt in neighbors.items():
                pair = tuple(sorted([a, b]))
                if pair not in shown:
                    shown.add(pair)
                    console.print(f"  {pair[0]} ↔ {pair[1]}: {cnt}")



# ── heatmap ──────────────────────────────────────────────────────────

@main.command()
@click.argument("path", type=click.Path(exists=True))
def heatmap(path: str):
    """Show failure heatmap by time of day and day of week.

    Reveals temporal patterns — when failures are most likely to occur.
    """
    from ..heatmap import build_heatmap, print_heatmap

    engine = AnalysisEngine()
    p = Path(path)

    if p.is_dir():
        batch = engine.analyze_directory(p)
    else:
        results = engine.analyze_file(p)
        batch = engine.analyze_sessions([r.session for r in results])

    data = build_heatmap(batch)
    print_heatmap(data, console)



# ── framework-compare ────────────────────────────────────────────────

@main.command("framework-compare")
@click.argument("path", type=click.Path(exists=True))
def framework_compare(path: str):
    """Compare failure patterns across agent frameworks.

    Analyzes sessions from multiple frameworks and shows which
    performs best on failure rate, risk, and token usage.
    """
    from ..framework_compare import compare_frameworks, print_comparison

    engine = AnalysisEngine()
    p = Path(path)

    if p.is_dir():
        batch = engine.analyze_directory(p)
    else:
        results = engine.analyze_file(p)
        batch = engine.analyze_sessions([r.session for r in results])

    report = compare_frameworks(batch)
    print_comparison(report, console)



# ── budget ───────────────────────────────────────────────────────────

@main.command()
@click.argument("path", type=click.Path(exists=True))
def budget(path: str):
    """Analyze token usage and recommend optimal budgets.

    Shows token statistics and suggests budget settings
    based on actual usage patterns.
    """
    from ..budget import analyze_budget

    engine = AnalysisEngine()
    p = Path(path)

    if p.is_dir():
        batch = engine.analyze_directory(p)
    else:
        results = engine.analyze_file(p)
        batch = engine.analyze_sessions([r.session for r in results])

    advice = analyze_budget(batch)

    table = Table(title="Token Budget Analysis", border_style="blue")
    table.add_column("Metric", style="bold", width=25)
    table.add_column("Value", justify="right", width=15)

    table.add_row("Average Tokens", f"{advice.avg_tokens:,}")
    table.add_row("Median Tokens", f"{advice.median_tokens:,}")
    table.add_row("P95 Tokens", f"{advice.p95_tokens:,}")
    table.add_row("Max Tokens", f"{advice.max_tokens:,}")
    table.add_row(
        "Recommended Budget",
        Text(f"{advice.recommended_budget:,}", style="bold green"),
    )
    table.add_row("Token Waste", f"{advice.waste_ratio:.0%}")
    console.print(table)

    if advice.per_framework:
        console.print("\n[bold]Per-Framework:[/bold]")
        for fw, stats in advice.per_framework.items():
            console.print(
                f"  {fw}: avg={stats['avg']:,}  "
                f"p95={stats['p95']:,}  "
                f"({stats['sessions']} sessions)"
            )

    if advice.suggestions:
        console.print("\n[bold]Suggestions:[/bold]")
        for s in advice.suggestions:
            console.print(f"  [green]→[/green] {s}")


