"""
CLI for Agent Failure Analyzer.

Commands:
    afa analyze <path>          Analyze log file(s) for failures
    afa ingest --claude-code    Auto-discover and analyze Claude Code sessions
    afa check <path>            CI gate — exit non-zero if risk exceeds threshold
    afa compare <a> <b>         Compare two sessions side-by-side
    afa trend                   Show failure trends over time (requires prior --store runs)
    afa watch <path>            Monitor directory and re-analyze on changes
    afa taxonomy                Show the failure taxonomy
    afa dashboard <path>        Launch the web dashboard
    afa replay <path>           Step through session events interactively
    afa remediate <path>        Show fix suggestions for detected failures
    afa correlate <path>        Detect cross-session failure patterns
    afa anonymize <path>        Strip PII and secrets from logs
    afa stream                  Real-time streaming analysis from stdin
    afa heatmap <path>          Show failure time-of-day heatmap
    afa framework-compare <p>   Compare failure patterns across frameworks
    afa budget <path>           Token budget advisor
    afa fingerprint <path>      Deduplicate failures with stable hashes
    afa github-issues <path>    Export failures as GitHub issues
"""

from __future__ import annotations

import sys
import time
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
)

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


@click.group()
@click.version_option(version=__version__, prog_name="afa")
def main():
    """Agent Failure Analyzer — classify and diagnose AI agent session failures."""


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
            from .reports.csv_report import CSVReporter
            csv_reporter = CSVReporter()
            if output:
                csv_reporter.write_batch(batch, output)
                console.print(f"[green]CSV report written to {output}[/green]")
            else:
                click.echo(csv_reporter.batch_to_csv(batch))
        elif format == "html":
            from .reports.html_report import HTMLReporter
            html_reporter = HTMLReporter()
            if output:
                html_reporter.write_batch(batch, output)
                console.print(f"[green]HTML report written to {output}[/green]")
            else:
                click.echo(html_reporter.batch_to_html(batch))
        elif format == "markdown":
            from .reports.markdown_report import MarkdownReporter
            md_reporter = MarkdownReporter()
            if output:
                md_reporter.write_batch(batch, output)
                console.print(f"[green]Markdown report written to {output}[/green]")
            else:
                click.echo(md_reporter.batch_to_markdown(batch))
        elif format == "pdf":
            from .reports.pdf_report import PDFReporter
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
            from .storage import AnalysisStore
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
            from .reports.csv_report import CSVReporter
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
            from .reports.html_report import HTMLReporter
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
            from .reports.markdown_report import MarkdownReporter
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
            from .reports.pdf_report import PDFReporter
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
    from .ingest import discover_claude_code_sessions

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
    from .storage import AnalysisStore

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


# ── diff ──────────────────────────────────────────────────────────────

@main.command()
@click.argument("session_id")
def diff(session_id: str):
    """Show how a session changed between stored runs.

    Requires previous runs with --store. Shows risk delta,
    new failures, and resolved failures.
    """
    from .storage import AnalysisStore

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


# ── watch ─────────────────────────────────────────────────────────────

@main.command()
@click.argument("path", type=click.Path(exists=True))
@click.option("--interval", "-i", type=int, default=5, help="Poll interval in seconds.")
@click.option("--store", is_flag=True, default=False, help="Persist results to SQLite.")
def watch(path: str, interval: int, store: bool):
    """Monitor a directory and re-analyze when files change.

    Watches for new or modified .json/.jsonl files.
    """
    p = Path(path)
    if not p.is_dir():
        console.print("[red]Watch requires a directory path.[/red]")
        return

    console.print(f"[bold]Watching:[/bold] {p} (every {interval}s)")
    console.print("[dim]Press Ctrl+C to stop[/dim]\n")

    seen: dict[Path, float] = {}
    engine = AnalysisEngine()

    # Initial scan
    for f in p.rglob("*"):
        if f.is_file() and f.suffix in (".json", ".jsonl"):
            seen[f] = f.stat().st_mtime

    try:
        while True:
            time.sleep(interval)
            changed: list[Path] = []

            for f in p.rglob("*"):
                if not f.is_file() or f.suffix not in (".json", ".jsonl"):
                    continue
                mtime = f.stat().st_mtime
                if f not in seen or seen[f] < mtime:
                    changed.append(f)
                    seen[f] = mtime

            if changed:
                console.print(
                    f"\n[bold yellow]Changes detected:"
                    f"[/bold yellow] {len(changed)} file(s)"
                )
                for cf in changed:
                    console.print(f"  [dim]{cf.name}[/dim]")

                for cf in changed:
                    try:
                        results = engine.analyze_file(cf)
                        if results:
                            term_reporter = TerminalReporter(console)
                            for r in results:
                                term_reporter.print_session(r)
                            if store:
                                from .storage import AnalysisStore
                                db = AnalysisStore()
                                for r in results:
                                    db.save_result(r)
                                db.close()
                    except Exception as e:
                        console.print(f"  [red]Error parsing {cf.name}: {e}[/red]")

    except KeyboardInterrupt:
        console.print("\n[dim]Stopped watching.[/dim]")


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


# ── tui ───────────────────────────────────────────────────────────────

@main.command()
@click.argument("path", type=click.Path(exists=True))
def tui(path: str):
    """Launch the interactive terminal UI for browsing results.

    Navigate sessions with arrow keys, Enter to view details, q to quit.
    """
    from .tui import InteractiveTUI

    engine = AnalysisEngine()
    p = Path(path)

    if p.is_dir():
        batch = engine.analyze_directory(p)
    else:
        results = engine.analyze_file(p)
        batch = engine.analyze_sessions([r.session for r in results])

    viewer = InteractiveTUI(batch, console)
    viewer.run()


# ── dashboard ─────────────────────────────────────────────────────────

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


# ── completions ───────────────────────────────────────────────────────

@main.command()
@click.argument("shell", type=click.Choice(["bash", "zsh", "fish"]))
def completions(shell: str):
    """Generate shell completion script.

    Print the completion script to stdout. Source it in your shell config:

    \b
        # Bash (~/.bashrc)
        eval "$(afa completions bash)"
    \b
        # Zsh (~/.zshrc)
        eval "$(afa completions zsh)"
    \b
        # Fish (~/.config/fish/completions/afa.fish)
        afa completions fish > ~/.config/fish/completions/afa.fish
    """
    import os

    os.environ["_AFA_COMPLETE"] = f"{shell}_source"
    try:
        # Click's built-in completion generation
        main.main(standalone_mode=False)
    except SystemExit:
        pass
    finally:
        os.environ.pop("_AFA_COMPLETE", None)


# ── benchmark ─────────────────────────────────────────────────────────

@main.command()
@click.option("--json-output", "-o", type=click.Path(), help="Write metrics as JSON.")
def benchmark(json_output: str | None):
    """Run the classifier benchmark against hand-labeled samples.

    Measures precision, recall, and F1 against the expected failures
    defined in benchmarks/labels.json.
    """
    from benchmarks.run_benchmark import run_benchmark

    console.print("[bold]Running classifier benchmark...[/bold]\n")
    metrics = run_benchmark(verbose=True)

    if json_output:
        import json as json_mod
        Path(json_output).write_text(json_mod.dumps(metrics, indent=2))
        console.print(f"\n[green]Metrics written to {json_output}[/green]")


# ── replay ────────────────────────────────────────────────────────────

@main.command()
@click.argument("path", type=click.Path(exists=True))
def replay(path: str):
    """Step through session events interactively.

    Navigate with n/p (next/prev), arrow keys, q to quit, a for all.
    """
    from .replay import SessionReplay

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
    from .remediation import get_remediation

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


# ── correlate ────────────────────────────────────────────────────────

@main.command()
@click.argument("path", type=click.Path(exists=True))
def correlate(path: str):
    """Detect cross-session failure patterns.

    Analyzes multiple sessions to find recurring failures,
    co-occurring issues, and framework-specific problems.
    """
    from .correlation import correlate as run_correlation

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

    for i, p in enumerate(report.patterns, 1):
        console.print(
            f"  [bold]{i}.[/bold] [{p.pattern_type}] {p.description}"
        )
        if p.affected_sessions:
            console.print(
                f"     [dim]Sessions: "
                f"{', '.join(p.affected_sessions[:5])}"
                f"{'...' if len(p.affected_sessions) > 5 else ''}[/dim]"
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


# ── anonymize ────────────────────────────────────────────────────────

@main.command()
@click.argument("path", type=click.Path(exists=True))
@click.option("--output", "-o", type=click.Path(), help="Output file path.")
@click.option(
    "--no-paths", is_flag=True, default=False,
    help="Skip home directory path redaction.",
)
def anonymize(path: str, output: str | None, no_paths: bool):
    """Strip PII, API keys, and secrets from log files.

    Outputs the anonymized JSON to stdout or a file.
    """
    import json as json_mod

    from .anonymizer import anonymize_session

    engine = AnalysisEngine()
    p = Path(path)

    sessions = engine.parser.parse(p)
    if not sessions:
        console.print("[yellow]No sessions found.[/yellow]")
        return

    anonymized = []
    total_redactions = 0
    for session in sessions:
        clean, stats = anonymize_session(session, redact_paths=not no_paths)
        anonymized.append(clean.model_dump(mode="json"))
        total_redactions += stats.total_redactions

    result = json_mod.dumps(anonymized, indent=2, default=str)

    if output:
        Path(output).write_text(result)
        console.print(
            f"[green]Anonymized {len(sessions)} session(s) → {output}[/green]"
        )
    else:
        click.echo(result)

    console.print(
        f"[dim]{total_redactions} redaction(s) applied[/dim]"
    )


# ── stream ───────────────────────────────────────────────────────────

@main.command()
@click.option(
    "--alert-severity", "-s",
    type=click.Choice(["info", "low", "medium", "high", "critical"]),
    default="medium", help="Minimum severity for real-time alerts.",
)
def stream(alert_severity: str):
    """Real-time streaming analysis from stdin.

    Pipe agent log events (JSONL) into this command for live failure detection:

    \b
        cat events.jsonl | afa stream
        tail -f /var/log/agent.jsonl | afa stream --alert-severity high
    """
    from .stream import stream_analyze

    stream_analyze(console=console, alert_severity=alert_severity)


# ── heatmap ──────────────────────────────────────────────────────────

@main.command()
@click.argument("path", type=click.Path(exists=True))
def heatmap(path: str):
    """Show failure heatmap by time of day and day of week.

    Reveals temporal patterns — when failures are most likely to occur.
    """
    from .heatmap import build_heatmap, print_heatmap

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
    from .framework_compare import compare_frameworks, print_comparison

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
    from .budget import analyze_budget

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
    from .fingerprint import deduplicate_failures

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


# ── github-issues ────────────────────────────────────────────────────

@main.command("github-issues")
@click.argument("path", type=click.Path(exists=True))
@click.option("--repo", "-r", required=True, help="GitHub repo (owner/repo).")
@click.option(
    "--token", envvar="GITHUB_TOKEN",
    help="GitHub API token (or set GITHUB_TOKEN env var).",
)
@click.option(
    "--min-severity", "-s",
    type=click.Choice(["info", "low", "medium", "high", "critical"]),
    default="high", help="Minimum severity to export.",
)
@click.option(
    "--dry-run", is_flag=True, default=False,
    help="Preview issues without creating them.",
)
def github_issues(path: str, repo: str, token: str | None,
                  min_severity: str, dry_run: bool):
    """Export high-severity failures as GitHub issues.

    Creates one issue per qualifying failure with description,
    evidence, and remediation suggestions.
    """
    from .github_export import export_failures_to_issues

    engine = AnalysisEngine()
    results = engine.analyze_file(path)

    if not results:
        console.print("[yellow]No sessions found.[/yellow]")
        return

    total_created = 0
    for result in results:
        issue_results = export_failures_to_issues(
            result, repo, token=token,
            min_severity=min_severity, dry_run=dry_run,
        )
        for ir in issue_results:
            if ir.success:
                total_created += 1
                if dry_run:
                    console.print(f"  [dim][dry-run] {ir.error}[/dim]")
                else:
                    console.print(
                        f"  [green]Created #{ir.issue_number}:[/green] "
                        f"{ir.issue_url}"
                    )
            else:
                console.print(f"  [red]Error: {ir.error}[/red]")

    label = "previewed" if dry_run else "created"
    console.print(f"\n[bold]{total_created} issue(s) {label}[/bold]")


# ── helpers ───────────────────────────────────────────────────────────

def _print_cost_summary(results: list) -> None:
    """Print cost waste estimation for results."""
    from .cost import estimate_waste

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
    from .storage import AnalysisStore
    db = AnalysisStore()
    db.save_batch(batch)
    console.print(f"[dim]Stored {batch.total_sessions} result(s) to {db.db_path}[/dim]")
    db.close()


def _send_notifications(
    results: list, webhook: str | None, slack: str | None, threshold: float
) -> None:
    """Send webhook/Slack notifications for high-risk results."""
    from .models import BatchAnalysisResult
    from .notify import NotifyConfig, notify_batch, should_notify

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


if __name__ == "__main__":
    main()
