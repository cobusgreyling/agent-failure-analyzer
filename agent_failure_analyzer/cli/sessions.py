from __future__ import annotations

from pathlib import Path

import click
from rich.table import Table

from ..analyzers.engine import AnalysisEngine
from ..taxonomy import (
    CATEGORY_DESCRIPTIONS,
    SUBCATEGORY_TO_CATEGORY,
)
from . import main
from ._helpers import (
    _filter_results,
    console,
)

# ── diff ──────────────────────────────────────────────────────────────

@main.command()
@click.argument("session_id")
def diff(session_id: str):
    """Show how a session changed between stored runs.

    Requires previous runs with --store. Shows risk delta,
    new failures, and resolved failures.
    """
    from ..storage import AnalysisStore

    store = AnalysisStore()
    result = store.get_session_diff(session_id)

    if result is None:
        console.print("[yellow]Need at least 2 stored runs for this session to diff.[/yellow]")
        store.close()
        return

    prev = result["previous"]
    curr = result["current"]

    # Header
    console.print(f"\n[bold]Session Diff:[/bold] {session_id}")
    console.print(f"  Previous: {prev['analyzed_at']}  |  Current: {curr['analyzed_at']}\n")

    # Risk delta
    delta = result["risk_delta"]
    delta_style = "red" if delta > 0 else "green" if delta < 0 else "dim"
    console.print(
        f"  Risk: {prev['risk_score']:.0%} -> {curr['risk_score']:.0%} "
        f"[{delta_style}]({delta:+.0%})[/{delta_style}]"
    )
    console.print(
        f"  Failures: {prev['failure_count']} -> {curr['failure_count']}"
    )

    if result["new_failures"]:
        console.print("\n  [bold red]New failures:[/bold red]")
        for f in result["new_failures"]:
            console.print(f"    [red]+ {f}[/red]")

    if result["resolved_failures"]:
        console.print("\n  [bold green]Resolved:[/bold green]")
        for f in result["resolved_failures"]:
            console.print(f"    [green]- {f}[/green]")

    if not result["changed"]:
        console.print("  [dim]No changes detected.[/dim]")

    console.print()
    store.close()



# ── replay ────────────────────────────────────────────────────────────

@main.command()
@click.argument("path", type=click.Path(exists=True))
def replay(path: str):
    """Step through session events interactively.

    Navigate with n/p (next/prev), arrow keys, q to quit, a for all.
    """
    from ..replay import SessionReplay

    engine = AnalysisEngine()
    results = engine.analyze_file(path)

    if not results:
        console.print("[yellow]No sessions found.[/yellow]")
        return

    viewer = SessionReplay(results[0], console)
    viewer.run()



# ── remediate ────────────────────────────────────────────────────────

@main.command()
@click.argument("path", type=click.Path(exists=True))
@click.option(
    "--min-severity", "-s",
    type=click.Choice(["info", "low", "medium", "high", "critical"]),
    default="low", help="Minimum severity for suggestions.",
)
def remediate(path: str, min_severity: str):
    """Show remediation suggestions for detected failures.

    Analyzes the session and provides concrete fix suggestions
    for each failure found.
    """
    from ..remediation import get_remediation

    engine = AnalysisEngine()
    results = engine.analyze_file(path)
    _filter_results(results, min_severity, 0.0)

    if not results:
        console.print("[yellow]No sessions found.[/yellow]")
        return

    for result in results:
        console.print(
            f"\n[bold]Session:[/bold] {result.session.session_id}"
        )
        if not result.failures:
            console.print("  [green]No failures — no remediation needed.[/green]")
            continue

        for i, f in enumerate(result.failures, 1):
            console.print(
                f"\n  [bold]{i}. [{f.severity.value.upper()}] "
                f"{f.subcategory.value}[/bold]"
            )
            console.print(f"     {f.description[:80]}")
            suggestions = get_remediation(f.subcategory)
            for s in suggestions:
                console.print(f"     [green]→[/green] {s}")



# ── explain ──────────────────────────────────────────────────────────

@main.command()
@click.argument("path", type=click.Path(exists=True))
@click.argument("failure_index", type=int)
@click.option(
    "--session-index", "-s", type=int, default=0,
    help="Session index when file contains multiple sessions (0-based).",
)
def explain(path: str, failure_index: int, session_index: int):
    """Show a detailed explanation and remediation for a specific failure.

    FAILURE_INDEX is the 1-based index of the failure from the analysis report.

    \b
    Example:
        afa analyze session.jsonl          # see numbered failures
        afa explain session.jsonl 1        # explain failure #1 in detail
    """
    from ..remediation import get_remediation

    engine = AnalysisEngine()
    results = engine.analyze_file(path)

    if not results:
        console.print("[yellow]No sessions found.[/yellow]")
        return

    if session_index >= len(results):
        console.print(
            f"[red]Session index {session_index} out of range "
            f"(file has {len(results)} session(s)).[/red]"
        )
        return

    result = results[session_index]

    if not result.failures:
        console.print("[green]No failures detected in this session.[/green]")
        return

    if failure_index < 1 or failure_index > len(result.failures):
        console.print(
            f"[red]Failure index {failure_index} out of range "
            f"(session has {len(result.failures)} failure(s), use 1-{len(result.failures)}).[/red]"
        )
        return

    failure = result.failures[failure_index - 1]
    category = SUBCATEGORY_TO_CATEGORY.get(failure.subcategory, failure.category)
    category_desc = CATEGORY_DESCRIPTIONS.get(category, "")
    suggestions = get_remediation(failure.subcategory)

    # Header
    console.print(f"\n[bold]Failure #{failure_index} — Detailed Explanation[/bold]")
    console.print(f"  Session: {result.session.session_id}")
    console.print()

    # Classification
    sev_colors = {
        "critical": "bold red", "high": "red", "medium": "yellow",
        "low": "cyan", "info": "dim",
    }
    sev_style = sev_colors.get(failure.severity.value, "")
    console.print(f"  [bold]Category:[/bold]     {category.value}")
    console.print(f"  [bold]Subcategory:[/bold]  {failure.subcategory.value}")
    sev_upper = failure.severity.value.upper()
    console.print(f"  [bold]Severity:[/bold]     [{sev_style}]{sev_upper}[/{sev_style}]")
    console.print(f"  [bold]Confidence:[/bold]   {failure.confidence:.0%}")
    console.print()

    # Description
    console.print("  [bold]What happened:[/bold]")
    console.print(f"    {failure.description}")
    console.print()

    # Category context
    if category_desc:
        console.print(f"  [bold]About {category.value}:[/bold]")
        console.print(f"    {category_desc}")
        console.print()

    # Evidence
    if failure.evidence:
        console.print("  [bold]Evidence:[/bold]")
        for i, ev in enumerate(failure.evidence, 1):
            console.print(f"    {i}. {ev[:120]}")
        console.print()

    # Event context
    if failure.event_indices:
        console.print(f"  [bold]Related events:[/bold] (indices {failure.event_indices})")
        for idx in failure.event_indices[:5]:
            if 0 <= idx < len(result.session.events):
                evt = result.session.events[idx]
                label = evt.event_type.value
                snippet = evt.content[:80] if evt.content else ""
                tool = f" ({evt.tool_name})" if evt.tool_name else ""
                console.print(f"    [{idx}] {label}{tool}: {snippet}")
        console.print()

    # Remediation
    console.print("  [bold]How to fix:[/bold]")
    for s in suggestions:
        console.print(f"    [green]\u2192[/green] {s}")
    console.print()



# ── fingerprint ──────────────────────────────────────────────────────

@main.command()
@click.argument("path", type=click.Path(exists=True))
@click.option(
    "--json-output", "-o", type=click.Path(),
    help="Write deduplicated results as JSON.",
)
def fingerprint(path: str, json_output: str | None):
    """Deduplicate failures using stable fingerprints.

    Groups identical failures across sessions and shows occurrence counts.
    """
    from ..fingerprint import deduplicate_failures

    engine = AnalysisEngine()
    p = Path(path)

    if p.is_dir():
        batch = engine.analyze_directory(p)
        results = batch.results
    else:
        results = engine.analyze_file(p)

    dedup = deduplicate_failures(results)

    table = Table(title="Deduplicated Failures", border_style="blue")
    table.add_column("Fingerprint", style="dim", width=18)
    table.add_column("Subcategory", width=25)
    table.add_column("Severity", width=10)
    table.add_column("Count", justify="right", width=7)
    table.add_column("Sessions", justify="right", width=10)

    # Sort by occurrence count
    sorted_fps = sorted(
        dedup.occurrence_count.items(),
        key=lambda x: x[1],
        reverse=True,
    )

    for fp, count in sorted_fps[:20]:
        failure = dedup.unique_fingerprints[fp]
        session_count = len(set(dedup.session_map.get(fp, [])))
        table.add_row(
            fp,
            failure.subcategory.value,
            failure.severity.value.upper(),
            str(count),
            str(session_count),
        )

    console.print(table)
    console.print(
        f"\n[dim]{len(dedup.unique_fingerprints)} unique failures "
        f"from {sum(dedup.occurrence_count.values())} total[/dim]"
    )

    if json_output:
        import json as json_mod
        output_data = {
            "unique_count": len(dedup.unique_fingerprints),
            "total_count": sum(dedup.occurrence_count.values()),
            "failures": [
                {
                    "fingerprint": fp,
                    "subcategory": dedup.unique_fingerprints[fp].subcategory.value,
                    "severity": dedup.unique_fingerprints[fp].severity.value,
                    "description": dedup.unique_fingerprints[fp].description,
                    "occurrences": dedup.occurrence_count[fp],
                    "sessions": len(set(dedup.session_map.get(fp, []))),
                }
                for fp, _ in sorted_fps
            ],
        }
        Path(json_output).write_text(json_mod.dumps(output_data, indent=2))
        console.print(f"[green]Written to {json_output}[/green]")


