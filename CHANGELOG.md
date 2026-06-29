# Changelog

## Unreleased

### New Features
- **MCP server** — `afa mcp` exposes the analyzer over the Model Context Protocol. Lets Claude Code, Claude Desktop, and other MCP clients call `analyze`, `explain`, `compare`, `trend`, `taxonomy`, and `remediation` as tools. Install with `pip install 'agent-failure-analyzer[mcp]'`.

## v0.4.0 (2026-05-11)

### New Features
- **Markdown report format** — `afa analyze --format markdown` for GitHub/Notion-friendly output
- **PDF report export** — `afa analyze --format pdf` using weasyprint (`pip install agent-failure-analyzer[pdf]`)
- **Session replay viewer** — `afa replay <path>` for interactive step-by-step event playback
- **Failure remediation suggestions** — `afa remediate <path>` provides concrete fix suggestions per failure
- **Multi-session correlation** — `afa correlate <path>` detects recurring patterns across sessions
- **GitHub Actions reusable action** — `action.yml` for CI/CD integration with quality gates
- **Grafana dashboard template** — pre-built dashboard for OTLP-exported metrics
- **Log anonymizer** — `afa anonymize <path>` strips PII, API keys, secrets, and home paths
- **Real-time streaming analysis** — `afa stream` reads JSONL from stdin for live failure detection
- **Failure heatmap** — `afa heatmap <path>` shows time-of-day × day-of-week failure patterns
- **Comparative framework report** — `afa framework-compare <path>` compares frameworks side-by-side
- **Token budget advisor** — `afa budget <path>` analyzes usage and recommends optimal budgets
- **Failure fingerprinting** — `afa fingerprint <path>` deduplicates with stable hashes
- **Export to GitHub Issues** — `afa github-issues <path>` creates issues for high-severity failures

### Improvements
- PDF format option in analyze command via weasyprint optional dependency
- 10 new CLI commands for advanced analysis workflows
- Comprehensive remediation database covering all 30+ failure subcategories

## v0.3.0 (2026-05-11)

### New Features
- **CSV and HTML report formats** — `afa analyze --format csv` and `--format html` for spreadsheet and standalone HTML reports
- **Plugin system for custom parsers** — register parsers via `afa.parsers` entry point group
- **AutoGen parser** — support for Microsoft AutoGen conversation logs
- **OpenAI Assistants parser** — support for OpenAI Assistants API thread/run logs
- **Session diffing** — `afa diff <session_id>` tracks changes across stored runs, shows regressions
- **Webhook/Slack notifications** — `--notify-webhook` and `--notify-slack` flags for high-risk alerts
- **Interactive TUI** — `afa tui <path>` for keyboard-navigable session browsing
- **OpenTelemetry export** — `pip install agent-failure-analyzer[otel]` for OTLP spans and metrics
- **Benchmark suite** — `afa benchmark` measures classifier precision/recall against hand-labeled samples
- **Configuration file** — `.afa.toml` for default settings (analysis, output, CI, notifications)
- **Shell completions** — `afa completions bash/zsh/fish` generates completion scripts
- **Code coverage** — CI uploads coverage to Codecov with badge in README

### Improvements
- CONTRIBUTING.md with dev setup, coding standards, and contribution guide
- GitHub issue templates (bug report, feature request) and PR template
- Pre-commit hooks config for ruff and mypy
- Fixed all ruff lint errors across codebase
- E501 exemptions for embedded HTML/JS template files
- Plugin parsers load via entry points, tried before generic fallback

## v0.2.0 (2026-05-11)

### New Features
- **LLM-powered classification** — optional Claude API pass for deeper failure analysis (`--llm`, `--llm-auto`)
- **`afa ingest --claude-code`** — auto-discover and analyze sessions from `~/.claude/projects/`
- **`afa watch <dir>`** — monitor directory for new/changed log files and re-analyze
- **`afa check <path>`** — CI quality gate with `--max-risk` and `--max-failures` thresholds
- **`afa compare <a> <b>`** — side-by-side session comparison showing failure diffs
- **`afa trend`** — failure trends over time with daily summaries and top failure types
- **`--min-confidence`** filter across all commands
- **`--cost`** flag for token/dollar waste estimation per session
- **`--store`** flag to persist results to SQLite for trend tracking
- **SQLite storage** at `~/.afa/history.db` for historical analysis
- **Cost waste estimation** with model-specific pricing lookup
- **Real-world anonymized sample** — full Claude Code session with realistic failure patterns
- **GitHub Actions CI** — tests on Python 3.10-3.13 with ruff linting and mypy
- **PyPI publish workflow** — automated release on GitHub release
- **Docker support** — `docker build -t afa . && docker run afa analyze /logs`
- **py.typed marker** for PEP 561 compliance
- **README badges** — CI status, Python versions, license

### Improvements
- Fixed mypy type errors across codebase
- All public modules have `from __future__ import annotations`

## v0.1.0 (2026-05-11)

### Initial Release
- Failure taxonomy: 9 categories, 30+ subcategories, 5 severity levels
- Parsers: Claude Code (JSONL), LangChain/LangSmith (JSON), CrewAI (JSON), Generic
- Heuristic classifier with pattern matching and behavioral signals
- CLI: `afa analyze`, `afa taxonomy`, `afa dashboard`
- Web dashboard with FastAPI + interactive charts
- Terminal reports with Rich
- JSON export
- 28 tests
