"""
Tunable thresholds for the heuristic detectors.

All numeric knobs live here so they can be overridden from `.afa.toml`
without editing detector code. Keyword lists are intentionally kept in
``detectors/_keywords.py`` — they're not user-facing tuning surface and
changing them requires running the benchmark to confirm there's no
regression.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class DetectorConfig:
    """Numeric thresholds for heuristic detectors."""

    # Context overflow
    verbose_tool_output_chars: int = 5000
    verbose_tool_output_count: int = 3
    total_tokens_threshold: int = 150_000

    # Tool misuse
    repeated_tool_failure_count: int = 3

    # Loops
    identical_loop_window: int = 3
    semantic_loop_window: int = 3
    semantic_loop_overlap_ratio: float = 0.7
    semantic_loop_min_msg_chars: int = 50
    semantic_loop_min_unique_words: int = 5

    # Error cascade
    error_cascade_min_streak: int = 3
    misinterpreted_overlap_threshold: int = 2

    # Planning
    overambitious_tool_calls: int = 20
    overambitious_error_rate: float = 0.4
    no_plan_first_n: int = 5
    no_plan_tool_threshold: int = 3


def detector_config_from_toml(section: dict[str, Any]) -> DetectorConfig:
    """Build a DetectorConfig from a parsed [detector] TOML section.

    Unknown keys are ignored — forward-compatible with future thresholds.
    """
    cfg = DetectorConfig()
    for field_name in cfg.__dataclass_fields__:
        if field_name in section:
            setattr(cfg, field_name, type(getattr(cfg, field_name))(section[field_name]))
    return cfg
