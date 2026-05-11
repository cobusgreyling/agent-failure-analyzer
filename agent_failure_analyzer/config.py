"""
Configuration file support for Agent Failure Analyzer.

Loads settings from .afa.toml in the current directory or home directory.
CLI flags override config file values.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:
    try:
        import tomllib  # type: ignore[import-not-found]
    except ImportError:
        tomllib = None  # type: ignore[assignment]


CONFIG_FILENAMES = [".afa.toml", "afa.toml"]


@dataclass
class AFAConfig:
    """Resolved configuration for Agent Failure Analyzer."""

    # Analysis
    min_severity: str = "info"
    min_confidence: float = 0.0
    use_llm: bool = False
    llm_auto: bool = False
    llm_model: str = "claude-sonnet-4-6"

    # Output
    format: str = "terminal"
    store: bool = False
    cost: bool = False

    # CI gate
    max_risk: float = 0.5
    max_failures: int | None = None

    # Notifications
    webhook_url: str | None = None
    slack_webhook_url: str | None = None
    notify_threshold: float = 0.5

    # Paths
    log_dirs: list[str] = field(default_factory=list)
    db_path: str | None = None


def find_config_file() -> Path | None:
    """Search for a config file in CWD and home directory."""
    search_dirs = [Path.cwd(), Path.home()]

    for directory in search_dirs:
        for name in CONFIG_FILENAMES:
            path = directory / name
            if path.exists():
                return path

    return None


def load_config(path: Path | None = None) -> AFAConfig:
    """Load configuration from a TOML file.

    If no path is given, searches CWD and home directory.
    Returns default config if no file is found or tomllib is unavailable.
    """
    if path is None:
        path = find_config_file()

    if path is None or tomllib is None:
        return AFAConfig()

    try:
        with open(path, "rb") as f:
            raw = tomllib.load(f)
    except Exception:
        return AFAConfig()

    config = AFAConfig()

    # [analysis] section
    analysis = raw.get("analysis", {})
    if "min_severity" in analysis:
        config.min_severity = analysis["min_severity"]
    if "min_confidence" in analysis:
        config.min_confidence = float(analysis["min_confidence"])
    if "llm" in analysis:
        config.use_llm = bool(analysis["llm"])
    if "llm_auto" in analysis:
        config.llm_auto = bool(analysis["llm_auto"])
    if "llm_model" in analysis:
        config.llm_model = analysis["llm_model"]

    # [output] section
    output = raw.get("output", {})
    if "format" in output:
        config.format = output["format"]
    if "store" in output:
        config.store = bool(output["store"])
    if "cost" in output:
        config.cost = bool(output["cost"])

    # [ci] section
    ci = raw.get("ci", {})
    if "max_risk" in ci:
        config.max_risk = float(ci["max_risk"])
    if "max_failures" in ci:
        config.max_failures = int(ci["max_failures"])

    # [notify] section
    notify = raw.get("notify", {})
    if "webhook_url" in notify:
        config.webhook_url = notify["webhook_url"]
    if "slack_webhook_url" in notify:
        config.slack_webhook_url = notify["slack_webhook_url"]
    if "threshold" in notify:
        config.notify_threshold = float(notify["threshold"])

    # [paths] section
    paths = raw.get("paths", {})
    if "log_dirs" in paths:
        config.log_dirs = list(paths["log_dirs"])
    if "db_path" in paths:
        config.db_path = paths["db_path"]

    return config
