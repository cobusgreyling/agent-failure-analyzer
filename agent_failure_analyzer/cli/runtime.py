from __future__ import annotations

import sys
import time
from pathlib import Path

import click

from ..analyzers.engine import AnalysisEngine
from ..reports.terminal_report import TerminalReporter
from . import main
from ._helpers import (
    console,
)

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
                                from ..storage import AnalysisStore
                                db = AnalysisStore()
                                for r in results:
                                    db.save_result(r)
                                db.close()
                    except Exception as e:
                        console.print(f"  [red]Error parsing {cf.name}: {e}[/red]")

    except KeyboardInterrupt:
        console.print("\n[dim]Stopped watching.[/dim]")



# ── tui ───────────────────────────────────────────────────────────────

@main.command()
@click.argument("path", type=click.Path(exists=True))
def tui(path: str):
    """Launch the interactive terminal UI for browsing results.

    Navigate sessions with arrow keys, Enter to view details, q to quit.
    """
    from ..tui import InteractiveTUI

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
    try:
        import uvicorn

        from ..dashboard.app import create_app
    except ImportError as exc:
        console.print(
            f"[bold red]Dashboard dependencies not installed:[/bold red] {exc.name}\n"
            "Install with: [cyan]pip install agent-failure-analyzer[dashboard][/cyan]"
        )
        sys.exit(1)

    app = create_app(Path(path))
    console.print(f"[bold green]Dashboard running at http://{host}:{port}[/bold green]")
    uvicorn.run(app, host=host, port=port, log_level="warning")



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
    from ..stream import stream_analyze

    stream_analyze(console=console, alert_severity=alert_severity)


