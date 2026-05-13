"""
CLI for Agent Failure Analyzer.

Commands:
    afa analyze <path>          Analyze log file(s) for failures
    afa ingest --claude-code    Auto-discover and analyze Claude Code sessions
    afa check <path>            CI gate — exit non-zero if risk exceeds threshold
    afa compare <a> <b>         Compare two sessions side-by-side
    afa trend                   Show failure trends over time
    afa watch <path>            Monitor directory and re-analyze on changes
    afa taxonomy                Show the failure taxonomy
    afa dashboard <path>        Launch the web dashboard
    afa replay <path>           Step through session events interactively
    afa explain <path> <N>      Detailed explanation of failure #N
    afa remediate <path>        Show fix suggestions for detected failures
    afa correlate <path>        Detect cross-session failure patterns
    afa anonymize <path>        Strip PII and secrets from logs
    afa stream                  Real-time streaming analysis from stdin
    afa heatmap <path>          Show failure time-of-day heatmap
    afa framework-compare <p>   Compare failure patterns across frameworks
    afa budget <path>           Token budget advisor
    afa fingerprint <path>      Deduplicate failures with stable hashes
    afa github-issues <path>    Export failures as GitHub issues
    afa diff <session-id>       Show differences between stored runs
    afa tui <path>              Interactive TUI report viewer
    afa completions <shell>     Generate shell completion script
    afa benchmark               Run classifier benchmark
"""

from __future__ import annotations

import click

from .. import __version__


@click.group()
@click.version_option(version=__version__, prog_name="afa")
def main():
    """Agent Failure Analyzer — classify and diagnose AI agent session failures."""


# Register subcommands by importing each submodule for its decorator side effects.
from . import aggregate, analysis, runtime, sessions, utilities  # noqa: E402,F401

if __name__ == "__main__":
    main()
