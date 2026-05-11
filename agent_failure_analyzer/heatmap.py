"""
Failure heatmap.

Generates a time-based heatmap showing when failures occur —
by hour-of-day and day-of-week — to reveal temporal patterns.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from rich.console import Console
from rich.table import Table
from rich.text import Text

from .models import BatchAnalysisResult

DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
HOURS = list(range(24))

_HEAT_CHARS = " ░▒▓█"


@dataclass
class HeatmapData:
    """Heatmap grid data: failures[day_of_week][hour] = count."""

    grid: list[list[int]] = field(default_factory=lambda: [[0] * 24 for _ in range(7)])
    total: int = 0
    peak_day: str = ""
    peak_hour: int = 0


def build_heatmap(batch: BatchAnalysisResult) -> HeatmapData:
    """Build a failure heatmap from batch results."""
    data = HeatmapData()

    for result in batch.results:
        session = result.session
        if not result.failures:
            continue

        # Use session start_time or analyzed_at
        ts = session.start_time or result.analyzed_at
        if ts is None:
            continue

        dow = ts.weekday()  # 0=Monday
        hour = ts.hour

        failure_count = len(result.failures)
        data.grid[dow][hour] += failure_count
        data.total += failure_count

    # Find peak
    max_count = 0
    for d in range(7):
        for h in range(24):
            if data.grid[d][h] > max_count:
                max_count = data.grid[d][h]
                data.peak_day = DAYS[d]
                data.peak_hour = h

    return data


def print_heatmap(data: HeatmapData, console: Console | None = None) -> None:
    """Print the heatmap to the terminal using Rich."""
    console = console or Console()

    if data.total == 0:
        console.print("[yellow]No timestamped failures to display.[/yellow]")
        return

    # Find max for normalization
    max_val = max(data.grid[d][h] for d in range(7) for h in range(24))
    if max_val == 0:
        max_val = 1

    table = Table(
        title="Failure Heatmap (hour of day × day of week)",
        border_style="blue",
    )
    table.add_column("Day", style="bold", width=5)
    for h in range(24):
        table.add_column(f"{h:02d}", width=3, justify="center")
    table.add_column("Total", style="bold", justify="right", width=6)

    for d in range(7):
        row_total = sum(data.grid[d])
        cells = []
        for h in range(24):
            val = data.grid[d][h]
            if val == 0:
                cells.append(Text("·", style="dim"))
            else:
                intensity = min(4, int(val / max_val * 4))
                char = _HEAT_CHARS[intensity + 1]
                if intensity >= 3:
                    style = "bold red"
                elif intensity >= 2:
                    style = "yellow"
                elif intensity >= 1:
                    style = "green"
                else:
                    style = "dim green"
                cells.append(Text(char, style=style))

        table.add_row(DAYS[d], *cells, str(row_total))

    console.print(table)
    console.print(
        f"\n  [bold]Total failures:[/bold] {data.total}  |  "
        f"[bold]Peak:[/bold] {data.peak_day} {data.peak_hour:02d}:00"
    )


def heatmap_to_text(data: HeatmapData) -> str:
    """Render heatmap as plain text for non-terminal output."""
    if data.total == 0:
        return "No timestamped failures to display."

    max_val = max(data.grid[d][h] for d in range(7) for h in range(24))
    if max_val == 0:
        max_val = 1

    lines = ["Failure Heatmap (hour × day)", ""]
    header = "     " + " ".join(f"{h:02d}" for h in range(24))
    lines.append(header)

    for d in range(7):
        row = f"{DAYS[d]}  "
        for h in range(24):
            val = data.grid[d][h]
            if val == 0:
                row += " · "
            else:
                intensity = min(len(_HEAT_CHARS) - 2, int(val / max_val * 4))
                row += f" {_HEAT_CHARS[intensity + 1]} "
        lines.append(row)

    lines.append("")
    lines.append(
        f"Total: {data.total} | Peak: {data.peak_day} {data.peak_hour:02d}:00"
    )
    return "\n".join(lines)
