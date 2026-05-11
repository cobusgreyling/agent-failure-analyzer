"""
Interactive TUI for browsing analysis results.

Uses Rich's Live display to provide a keyboard-navigable interface
for exploring sessions, failures, and evidence.
"""

from __future__ import annotations

import sys

from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .models import BatchAnalysisResult
from .reports.terminal_report import SEVERITY_COLORS, _risk_color


class InteractiveTUI:
    """Interactive terminal UI for browsing analysis results."""

    def __init__(self, batch: BatchAnalysisResult, console: Console | None = None) -> None:
        self.batch = batch
        self.console = console or Console()
        self.results = sorted(batch.results, key=lambda r: r.risk_score, reverse=True)
        self.selected_idx = 0
        self.detail_mode = False
        self.scroll_offset = 0

    def _build_session_list(self) -> Table:
        """Build the session list table."""
        table = Table(
            title=f"Sessions ({len(self.results)} total)",
            border_style="blue",
            expand=True,
        )
        table.add_column("#", width=3, style="dim")
        table.add_column("Session ID", width=24)
        table.add_column("Framework", width=12)
        table.add_column("Risk", width=8, justify="right")
        table.add_column("Failures", width=8, justify="right")
        table.add_column("Outcome", width=12)

        visible_start = max(0, self.selected_idx - 15)
        visible_end = min(len(self.results), visible_start + 30)

        for i in range(visible_start, visible_end):
            r = self.results[i]
            is_selected = i == self.selected_idx
            style = "bold white on blue" if is_selected else ""
            risk_color = _risk_color(r.risk_score)

            table.add_row(
                str(i + 1),
                r.session.session_id[:24],
                r.session.framework.value,
                Text(f"{r.risk_score:.0%}", style=risk_color),
                str(len(r.failures)),
                r.session.outcome.value,
                style=style,
            )

        return table

    def _build_detail_panel(self) -> Panel:
        """Build the detail panel for the selected session."""
        if not self.results:
            return Panel("No sessions", title="Detail")

        result = self.results[self.selected_idx]
        session = result.session

        lines: list[str] = []
        lines.append(f"[bold]Session:[/bold] {session.session_id}")
        lines.append(f"[bold]Framework:[/bold] {session.framework.value}")
        lines.append(f"[bold]Model:[/bold] {session.model or 'unknown'}")
        lines.append(f"[bold]Outcome:[/bold] {session.outcome.value}")
        lines.append(f"[bold]Events:[/bold] {len(session.events)}")
        if session.total_tokens:
            lines.append(f"[bold]Tokens:[/bold] {session.total_tokens:,}")
        risk_color = _risk_color(result.risk_score)
        lines.append(f"[bold]Risk:[/bold] [{risk_color}]{result.risk_score:.0%}[/{risk_color}]")
        lines.append("")

        if result.failures:
            lines.append(f"[bold]{len(result.failures)} Failure(s):[/bold]")
            visible_failures = result.failures[self.scroll_offset:self.scroll_offset + 10]
            for i, f in enumerate(visible_failures, self.scroll_offset + 1):
                sev_style = SEVERITY_COLORS.get(f.severity, "")
                lines.append(
                    f"  {i}. [{sev_style}]{f.severity.value.upper()}[/{sev_style}] "
                    f"{f.subcategory.value}"
                )
                lines.append(f"     {f.description[:80]}")
                if f.evidence:
                    lines.append(f"     [dim]{f.evidence[0][:100]}[/dim]")
            if len(result.failures) > self.scroll_offset + 10:
                lines.append(
                    f"  [dim]... {len(result.failures) - self.scroll_offset - 10} more "
                    f"(scroll with j/k)[/dim]"
                )
        else:
            lines.append("[green]No failures detected.[/green]")

        return Panel(
            "\n".join(lines),
            title=f"Session {self.selected_idx + 1} of {len(self.results)}",
            border_style="yellow" if result.failures else "green",
        )

    def _build_help_bar(self) -> Text:
        """Build the bottom help bar."""
        help_text = Text()
        keys = [
            ("Up/Down", "navigate"),
            ("Enter", "toggle detail"),
            ("j/k", "scroll failures"),
            ("q", "quit"),
        ]
        for key, desc in keys:
            help_text.append(f" {key} ", style="bold white on dark_green")
            help_text.append(f" {desc}  ", style="dim")
        return help_text

    def _build_layout(self) -> Layout:
        """Build the full layout."""
        layout = Layout()

        if self.detail_mode:
            layout.split_column(
                Layout(self._build_detail_panel(), name="main", ratio=9),
                Layout(self._build_help_bar(), name="help", size=1),
            )
        else:
            layout.split_column(
                Layout(self._build_session_list(), name="main", ratio=9),
                Layout(self._build_help_bar(), name="help", size=1),
            )

        return layout

    def run(self) -> None:
        """Run the interactive TUI."""
        if not self.results:
            self.console.print("[yellow]No sessions to display.[/yellow]")
            return

        self.console.print("[bold]Agent Failure Analyzer — Interactive Mode[/bold]")
        self.console.print(
            "[dim]Press 'q' to quit, Enter to view details,"
            " arrows to navigate[/dim]\n"
        )

        # Print the session list (non-interactive fallback for environments
        # where raw terminal input isn't available)
        try:
            import termios
            import tty

            fd = sys.stdin.fileno()
            old_settings = termios.tcgetattr(fd)
        except (ImportError, OSError, termios.error):
            # No raw terminal available — print static view
            self.console.print(self._build_session_list())
            self.console.print()
            self.console.print(self._build_detail_panel())
            return

        try:
            tty.setraw(fd)
            with Live(self._build_layout(), console=self.console, refresh_per_second=10) as live:
                while True:
                    ch = sys.stdin.read(1)

                    if ch == "q":
                        break
                    elif ch == "\x1b":  # Escape sequence
                        seq = sys.stdin.read(2)
                        if seq == "[A":  # Up
                            if self.detail_mode:
                                self.scroll_offset = max(0, self.scroll_offset - 1)
                            else:
                                self.selected_idx = max(0, self.selected_idx - 1)
                        elif seq == "[B":  # Down
                            if self.detail_mode:
                                self.scroll_offset += 1
                            else:
                                self.selected_idx = min(
                                    len(self.results) - 1, self.selected_idx + 1
                                )
                    elif ch == "\r":  # Enter
                        self.detail_mode = not self.detail_mode
                        self.scroll_offset = 0
                    elif ch == "j":
                        self.scroll_offset += 1
                    elif ch == "k":
                        self.scroll_offset = max(0, self.scroll_offset - 1)

                    live.update(self._build_layout())
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
