from __future__ import annotations

import sys
from pathlib import Path

import click

from ..analyzers.engine import AnalysisEngine
from ..reports.json_report import JSONReporter
from ..reports.terminal_report import TerminalReporter
from . import main
from ._helpers import (
    _filter_results,
    _print_cost_summary,
    _send_notifications,
    _store_batch,
    console,
)

# ── analyze ───────────────────────────────────────────────────────────

@main.command()
@click.argument("path", type=click.Path(exists=True))
@click.option(
    "--format", "-f",
    type=click.Choice(["terminal", "json", "csv", "html", "markdown", "pdf"]),
    default="terminal", help="Output format.",
)
@click.option("--output", "-o", type=click.Path(), help="Output file path.")
@click.option(
    "--min-severity", "-s",
    type=click.Choice(["info", "low", "medium", "high", "critical"]),
    default="info", help="Minimum severity to display.",
)
@click.option(
    "--min-confidence", "-c", type=float, default=0.0,
    help="Minimum confidence threshold (0.0-1.0).",
)
@click.option("--llm", is_flag=True, default=False, help="Use LLM classification.")
@click.option(
    "--llm-auto", is_flag=True, default=False,
    help="Use LLM only when heuristics are uncertain.",
)
@click.option("--llm-model", default="claude-sonnet-4-6", help="LLM model.")
@click.option(
    "--store", is_flag=True, default=False,
    help="Persist results to SQLite for trend tracking.",
)
@click.option("--cost", is_flag=True, default=False, help="Show cost estimation.")
@click.option(
    "--notify-webhook", envvar="AFA_WEBHOOK_URL",
    help="Webhook URL for high-risk alerts.",
)
@click.option(
    "--notify-slack", envvar="AFA_SLACK_WEBHOOK_URL",
    help="Slack webhook URL for alerts.",
)
@click.option(
    "--notify-threshold", type=float, default=0.5,
    help="Risk threshold for notifications (0.0-1.0).",
)
def analyze(path: str, format: str, output: str | None, min_severity: str,
            min_confidence: float, llm: bool, llm_auto: bool, llm_model: str,
            store: bool, cost: bool, notify_webhook: str | None,
            notify_slack: str | None, notify_threshold: float):
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
        _filter_results(batch.results, min_severity, min_confidence)
        console.print(f"[dim]Found {batch.total_sessions} session(s)[/dim]\n")

        if cost:
            _print_cost_summary(batch.results)

        if store:
            _store_batch(batch)

        if notify_webhook or notify_slack:
            _send_notifications(batch.results, notify_webhook, notify_slack, notify_threshold)

        if format == "json":
            json_reporter = JSONReporter()
            if output:
                json_reporter.write_batch(batch, output)
                console.print(f"[green]Report written to {output}[/green]")
            else:
                import json as json_mod
                click.echo(json_mod.dumps(json_reporter.batch_to_dict(batch), indent=2))
        elif format == "csv":
            from ..reports.csv_report import CSVReporter
            csv_reporter = CSVReporter()
            if output:
                csv_reporter.write_batch(batch, output)
                console.print(f"[green]CSV report written to {output}[/green]")
            else:
                click.echo(csv_reporter.batch_to_csv(batch))
        elif format == "html":
            from ..reports.html_report import HTMLReporter
            html_reporter = HTMLReporter()
            if output:
                html_reporter.write_batch(batch, output)
                console.print(f"[green]HTML report written to {output}[/green]")
            else:
                click.echo(html_reporter.batch_to_html(batch))
        elif format == "markdown":
            from ..reports.markdown_report import MarkdownReporter
            md_reporter = MarkdownReporter()
            if output:
                md_reporter.write_batch(batch, output)
                console.print(f"[green]Markdown report written to {output}[/green]")
            else:
                click.echo(md_reporter.batch_to_markdown(batch))
        elif format == "pdf":
            from ..reports.pdf_report import PDFReporter
            pdf_reporter = PDFReporter()
            out = output or "report.pdf"
            pdf_reporter.write_batch(batch, out)
            console.print(f"[green]PDF report written to {out}[/green]")
        else:
            term_reporter = TerminalReporter(console)
            term_reporter.print_batch(batch)
    else:
        console.print(f"[bold]Analyzing:[/bold] {p}")
        results = engine.analyze_file(p)
        _filter_results(results, min_severity, min_confidence)
        console.print(f"[dim]Found {len(results)} session(s)[/dim]\n")

        if not results:
            console.print("[yellow]No sessions found in file.[/yellow]")
            return

        if cost:
            _print_cost_summary(results)

        if store:
            from ..storage import AnalysisStore
            db = AnalysisStore()
            for r in results:
                db.save_result(r)
            console.print(f"[dim]Stored {len(results)} result(s)[/dim]")

        if format == "json":
            json_reporter = JSONReporter()
            if len(results) == 1:
                if output:
                    json_reporter.write_session(results[0], output)
                    console.print(f"[green]Report written to {output}[/green]")
                else:
                    import json as json_mod
                    click.echo(json_mod.dumps(json_reporter.session_to_dict(results[0]), indent=2))
            else:
                batch = engine.analyze_sessions([r.session for r in results])
                if output:
                    json_reporter.write_batch(batch, output)
                    console.print(f"[green]Report written to {output}[/green]")
                else:
                    import json as json_mod
                    click.echo(json_mod.dumps(json_reporter.batch_to_dict(batch), indent=2))
        elif format == "csv":
            from ..reports.csv_report import CSVReporter
            csv_reporter = CSVReporter()
            if output:
                if len(results) == 1:
                    csv_reporter.write_session(results[0], output)
                else:
                    batch = engine.analyze_sessions([r.session for r in results])
                    csv_reporter.write_batch(batch, output)
                console.print(f"[green]CSV report written to {output}[/green]")
            else:
                if len(results) == 1:
                    import csv as csv_mod
                    import io
                    buf = io.StringIO()
                    w = csv_mod.writer(buf)
                    w.writerow(csv_reporter.HEADERS)
                    w.writerows(csv_reporter.result_to_rows(results[0]))
                    click.echo(buf.getvalue())
                else:
                    batch = engine.analyze_sessions([r.session for r in results])
                    click.echo(csv_reporter.batch_to_csv(batch))
        elif format == "html":
            from ..reports.html_report import HTMLReporter
            html_reporter = HTMLReporter()
            if output:
                if len(results) == 1:
                    html_reporter.write_session(results[0], output)
                else:
                    batch = engine.analyze_sessions([r.session for r in results])
                    html_reporter.write_batch(batch, output)
                console.print(f"[green]HTML report written to {output}[/green]")
            else:
                if len(results) == 1:
                    click.echo(html_reporter.session_to_html(results[0]))
                else:
                    batch = engine.analyze_sessions([r.session for r in results])
                    click.echo(html_reporter.batch_to_html(batch))
        elif format == "markdown":
            from ..reports.markdown_report import MarkdownReporter
            md_reporter = MarkdownReporter()
            if output:
                if len(results) == 1:
                    md_reporter.write_session(results[0], output)
                else:
                    batch = engine.analyze_sessions([r.session for r in results])
                    md_reporter.write_batch(batch, output)
                console.print(f"[green]Markdown report written to {output}[/green]")
            else:
                if len(results) == 1:
                    click.echo(md_reporter.session_to_markdown(results[0]))
                else:
                    batch = engine.analyze_sessions([r.session for r in results])
                    click.echo(md_reporter.batch_to_markdown(batch))
        elif format == "pdf":
            from ..reports.pdf_report import PDFReporter
            pdf_reporter = PDFReporter()
            out = output or "report.pdf"
            if len(results) == 1:
                pdf_reporter.write_session(results[0], out)
            else:
                batch = engine.analyze_sessions([r.session for r in results])
                pdf_reporter.write_batch(batch, out)
            console.print(f"[green]PDF report written to {out}[/green]")
        else:
            term_reporter = TerminalReporter(console)
            for result in results:
                term_reporter.print_session(result)



# ── ingest ────────────────────────────────────────────────────────────

@main.command()
@click.option(
    "--claude-code", "source", flag_value="claude_code", default=True,
    help="Ingest Claude Code sessions from ~/.claude/projects/.",
)
@click.option("--path", type=click.Path(exists=True), help="Additional directory.")
@click.option("--store", is_flag=True, default=False, help="Persist to SQLite.")
@click.option(
    "--min-confidence", "-c", type=float, default=0.0,
    help="Minimum confidence threshold.",
)
def ingest(source: str, path: str | None, store: bool, min_confidence: float):
    """Auto-discover and analyze agent sessions from known locations."""
    from ..ingest import discover_claude_code_sessions

    console.print("[bold]Discovering Claude Code sessions...[/bold]")
    session_files = discover_claude_code_sessions()

    if path:
        extra = [p for p in Path(path).rglob("*") if p.suffix in (".json", ".jsonl")]
        session_files.extend(extra)

    if not session_files:
        console.print("[yellow]No session files found.[/yellow]")
        console.print("[dim]Searched: ~/.claude/projects/[/dim]")
        return

    console.print(f"[dim]Found {len(session_files)} log file(s)[/dim]")

    engine = AnalysisEngine()
    all_results = []
    for sf in session_files:
        try:
            results = engine.analyze_file(sf)
            _filter_results(results, "info", min_confidence)
            all_results.extend(results)
        except Exception:
            continue

    if not all_results:
        console.print("[yellow]No sessions could be parsed.[/yellow]")
        return

    batch = engine.analyze_sessions([r.session for r in all_results])
    console.print()

    if store:
        _store_batch(batch)

    term_reporter = TerminalReporter(console)
    term_reporter.print_batch(batch)



# ── check ─────────────────────────────────────────────────────────────

@main.command()
@click.argument("path", type=click.Path(exists=True))
@click.option(
    "--max-risk", type=float, default=0.5,
    help="Maximum acceptable risk score (0.0-1.0).",
)
@click.option(
    "--max-failures", type=int, default=None,
    help="Maximum acceptable total failures.",
)
@click.option(
    "--min-confidence", "-c", type=float, default=0.0,
    help="Minimum confidence threshold.",
)
def check(path: str, max_risk: float, max_failures: int | None, min_confidence: float):
    """CI quality gate — exit non-zero if thresholds are exceeded.

    Use in CI pipelines to fail builds when agent sessions have too many failures.
    """
    engine = AnalysisEngine()
    p = Path(path)

    if p.is_dir():
        batch = engine.analyze_directory(p)
        results = batch.results
    else:
        results = engine.analyze_file(p)

    _filter_results(results, "info", min_confidence)

    # Check thresholds
    violations = []
    for r in results:
        if r.risk_score > max_risk:
            violations.append(
                f"Session {r.session.session_id}: risk {r.risk_score:.0%} > {max_risk:.0%}"
            )

    total_failures = sum(len(r.failures) for r in results)
    if max_failures is not None and total_failures > max_failures:
        violations.append(
            f"Total failures {total_failures} > {max_failures}"
        )

    if violations:
        console.print("[bold red]FAIL[/bold red] — threshold exceeded:")
        for v in violations:
            console.print(f"  [red]{v}[/red]")
        sys.exit(1)
    else:
        console.print(
            f"[bold green]PASS[/bold green] — "
            f"{len(results)} session(s), {total_failures} failure(s), "
            f"all within thresholds"
        )
        sys.exit(0)


