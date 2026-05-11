"""
Session replay viewer.

Step through events in an analyzed session one at a time,
showing what happened at each turn with failure annotations.
"""

from __future__ import annotations

import sys

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from .models import AnalysisResult, EventType
from .reports.terminal_report import SEVERITY_COLORS

_EVENT_STYLES = {
    EventType.USER_MESSAGE: ("bold cyan", "USER"),
    EventType.ASSISTANT_MESSAGE: ("bold green", "ASSISTANT"),
    EventType.TOOL_CALL: ("bold yellow", "TOOL CALL"),
    EventType.TOOL_RESULT: ("yellow", "TOOL RESULT"),
    EventType.ERROR: ("bold red", "ERROR"),
    EventType.SYSTEM: ("dim", "SYSTEM"),
    EventType.THINKING: ("italic dim", "THINKING"),
}


class SessionReplay:
    """Interactive step-by-step replay of a session."""

    def __init__(
        self,
        result: AnalysisResult,
        console: Console | None = None,
    ) -> None:
        self.result = result
        self.session = result.session
        self.console = console or Console()
        self.events = self.session.events
        self.current = 0

        # Build failure index: event_index -> list of failures
        self._failure_map: dict[int, list] = {}
        for f in result.failures:
            for idx in f.event_indices:
                self._failure_map.setdefault(idx, []).append(f)

    def _render_event(self, idx: int) -> Panel:
        """Render a single event as a Rich panel."""
        event = self.events[idx]
        style, label = _EVENT_STYLES.get(
            event.event_type, ("", "EVENT")
        )

        # Header line
        header = Text()
        header.append(
            f"[{idx + 1}/{len(self.events)}] ",
            style="dim",
        )
        header.append(label, style=style)
        if event.tool_name:
            header.append(f" ({event.tool_name})", style="dim")
        if event.timestamp:
            header.append(
                f"  {event.timestamp.isoformat()}", style="dim"
            )

        # Content
        content = event.content
        if len(content) > 500:
            content = content[:500] + f"\n... [{len(content) - 500} chars]"

        body = Text()
        body.append(str(header))
        body.append("\n")
        if event.error_message:
            body.append(
                f"\nERROR: {event.error_message[:300]}\n",
                style="bold red",
            )
        if content:
            body.append(f"\n{content}\n")

        # Failure annotations
        failures = self._failure_map.get(idx, [])
        if failures:
            body.append("\n")
            for f in failures:
                sev_style = SEVERITY_COLORS.get(f.severity, "")
                body.append(
                    f"  [{f.severity.value.upper()}] ",
                    style=sev_style,
                )
                body.append(
                    f"{f.subcategory.value}: {f.description[:60]}\n"
                )

        border = "red" if failures else "blue"
        return Panel(body, border_style=border)

    def _print_static(self) -> None:
        """Print all events statically (non-interactive fallback)."""
        for i in range(len(self.events)):
            self.console.print(self._render_event(i))

    def run(self) -> None:
        """Run the interactive replay."""
        if not self.events:
            self.console.print("[yellow]No events to replay.[/yellow]")
            return

        c = self.console
        c.print(f"[bold]Session Replay:[/bold] {self.session.session_id}")
        c.print(
            f"[dim]{len(self.events)} events | "
            f"{len(self.result.failures)} failures | "
            f"Risk: {self.result.risk_score:.0%}[/dim]"
        )
        c.print(
            "[dim]n=next  p=prev  q=quit  "
            "g=goto  a=all[/dim]\n"
        )

        try:
            import termios
            import tty

            fd = sys.stdin.fileno()
            old = termios.tcgetattr(fd)
        except (ImportError, OSError):
            self._print_static()
            return

        try:
            tty.setraw(fd)
            c.print(self._render_event(self.current))

            while True:
                ch = sys.stdin.read(1)
                if ch == "q":
                    break
                elif ch == "n" or ch == " ":
                    if self.current < len(self.events) - 1:
                        self.current += 1
                        c.print(self._render_event(self.current))
                    else:
                        c.print("[dim]End of session.[/dim]")
                elif ch == "p":
                    if self.current > 0:
                        self.current -= 1
                        c.print(self._render_event(self.current))
                elif ch == "a":
                    self._print_static()
                    break
                elif ch == "\x1b":
                    seq = sys.stdin.read(2)
                    if seq == "[C":  # Right arrow
                        if self.current < len(self.events) - 1:
                            self.current += 1
                            c.print(
                                self._render_event(self.current)
                            )
                    elif seq == "[D":  # Left arrow
                        if self.current > 0:
                            self.current -= 1
                            c.print(
                                self._render_event(self.current)
                            )
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)
            c.print()
