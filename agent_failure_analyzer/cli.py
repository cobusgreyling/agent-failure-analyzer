"""
CLI for Agent Failure Analyzer.

Usage:
    afa analyze <path>          Analyze a log file or directory
    afa report <path> -o out    Generate a JSON report
    afa taxonomy                Show the failure taxonomy
    afa dashboard <path>        Launch the web dashboard
"""

from __future__ import annotations

from pathlib import Path

import click
from rich.console import Console
from rich.table import Table
from rich.text import Text

from . import __version__
from .analyzers.engine import AnalysisEngine
from .reports.json_report import JSONReporter
from .reports.terminal_report import TerminalReporter
from .taxonomy import (
    CATEGORY_DESCRIPTIONS,
    SUBCATEGORY_TO_CATEGORY,
    FailureCategory,
    FailureSubcategory,
)

console = Console()


@click.group()
@click.version_option(version=__version__, prog_name="afa")
def main():
    """Agent Failure Analyzer — classify and diagnose AI agent session failures."""


@main.command()
@click.argument("path", type=click.Path(exists=True))
@click.option(
    "--format", "-f",
    type=click.Choice(["terminal", "json"]),
    default="terminal",
    help="Output format.",
)
@click.option("--output", "-o", type=click.Path(), help="Output file path (for JSON format).")
@click.option("--min-severity", "-s", type=click.Choice(["info", "low", "medium", "high", "critical"]), default="info", help="Minimum severity to display.")
@click.option("--llm", is_flag=True, default=False, help="Use Claude LLM for deeper classification (requires ANTHROPIC_API_KEY).")
@click.option("--llm-auto", is_flag=True, default=False, help="Use LLM only for sessions where heuristics are uncertain.")
@click.option("--llm-model", default="claude-sonnet-4-6", help="Model for LLM classification.")
def analyze(path: str, format: str, output: str | None, min_severity: str, llm: bool, llm_auto: bool, llm_model: str):
    """Analyze agent session log(s) for failures.

    PATH can be a single log file (.json, .jsonl) or a directory of logs.
    """
    if llm or llm_auto:
        console.print("[dim]LLM classification enabled[/dim]")
    engine = AnalysisEngine(use_llm=llm, llm_auto=llm_auto, llm_model=llm_model)
    p = Path(path)

    if p.is_dir():
        console.print(f"[bold]Scanning directory:[/bold] {p}")
        batch = engine.analyze_directory(p)
        console.print(f"[dim]Found {batch.total_sessions} session(s)[/dim]\n")

        if format == "json":
            reporter = JSONReporter()
            if output:
                reporter.write_batch(batch, output)
                console.print(f"[green]Report written to {output}[/green]")
            else:
                import json
                click.echo(json.dumps(reporter.batch_to_dict(batch), indent=2))
        else:
            reporter = TerminalReporter(console)
            reporter.print_batch(batch)
    else:
        console.print(f"[bold]Analyzing:[/bold] {p}")
        results = engine.analyze_file(p)
        console.print(f"[dim]Found {len(results)} session(s)[/dim]\n")

        if not results:
            console.print("[yellow]No sessions found in file.[/yellow]")
            return

        if format == "json":
            reporter = JSONReporter()
            if len(results) == 1:
                if output:
                    reporter.write_session(results[0], output)
                    console.print(f"[green]Report written to {output}[/green]")
                else:
                    import json
                    click.echo(json.dumps(reporter.session_to_dict(results[0]), indent=2))
            else:
                batch = engine.analyze_sessions([r.session for r in results])
                if output:
                    reporter.write_batch(batch, output)
                    console.print(f"[green]Report written to {output}[/green]")
                else:
                    import json
                    click.echo(json.dumps(reporter.batch_to_dict(batch), indent=2))
        else:
            term_reporter = TerminalReporter(console)
            for result in results:
                term_reporter.print_session(result)


@main.command()
def taxonomy():
    """Display the full failure taxonomy."""
    table = Table(title="Agent Failure Taxonomy", border_style="blue")
    table.add_column("Category", style="bold", width=25)
    table.add_column("Subcategories", width=35)
    table.add_column("Description")

    # Group subcategories by category
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


@main.command()
@click.argument("path", type=click.Path(exists=True))
@click.option("--host", default="127.0.0.1", help="Dashboard host.")
@click.option("--port", "-p", default=8080, help="Dashboard port.")
def dashboard(path: str, host: str, port: int):
    """Launch the web dashboard for analyzing logs.

    PATH is a directory of log files or a single log file.
    """
    from .dashboard.app import create_app

    app = create_app(Path(path))
    console.print(f"[bold green]Dashboard running at http://{host}:{port}[/bold green]")

    import uvicorn
    uvicorn.run(app, host=host, port=port, log_level="warning")


if __name__ == "__main__":
    main()
