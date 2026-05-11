# Changelog

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
