from __future__ import annotations

from pathlib import Path

import click

from ..analyzers.engine import AnalysisEngine
from . import main
from ._helpers import (
    console,
)

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

    from ..anonymizer import anonymize_session

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
    from ..github_export import export_failures_to_issues

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


