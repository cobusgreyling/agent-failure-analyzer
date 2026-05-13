# Contributing to Agent Failure Analyzer

Thanks for your interest in contributing! This guide covers how to set up a development environment, run tests, and submit changes.

## Development Setup

```bash
# Clone the repo
git clone https://github.com/cobusgreyling/agent-failure-analyzer.git
cd agent-failure-analyzer

# Create a virtual environment
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows

# Install in editable mode with dev dependencies (+ dashboard/llm for full local testing)
pip install -e ".[dev,dashboard,llm]"
```

## Running Tests

```bash
# Run full test suite
pytest tests/ -v

# With coverage
pytest tests/ -v --cov=agent_failure_analyzer --cov-report=term-missing

# Run a specific test file
pytest tests/test_classifier.py -v
```

## Linting & Type Checking

```bash
# Lint with ruff
ruff check agent_failure_analyzer/ tests/

# Auto-fix lint issues
ruff check --fix agent_failure_analyzer/ tests/

# Type check with mypy
mypy agent_failure_analyzer/ --ignore-missing-imports --no-strict-optional
```

## Pre-commit Hooks

This project uses [pre-commit](https://pre-commit.com/) to run checks before each commit:

```bash
pip install pre-commit
pre-commit install
```

After installation, ruff and mypy run automatically on `git commit`.

## Project Structure

```
agent_failure_analyzer/
  analyzers/          # Heuristic + LLM classifiers, analysis engine
  dashboard/          # FastAPI web dashboard
  parsers/            # Framework-specific log parsers
  reports/            # Output formatters (terminal, JSON, CSV, HTML)
  cli.py              # Click CLI commands
  config.py           # Configuration file support
  cost.py             # Token/cost waste estimation
  ingest.py           # Auto-discovery of session logs
  models.py           # Pydantic data models
  notify.py           # Webhook/Slack notifications
  storage.py          # SQLite persistence
  taxonomy.py         # Failure categories, subcategories, severities
sample_logs/          # Example log files for testing
tests/                # Test suite
```

## Adding a New Parser

1. Create a new file in `agent_failure_analyzer/parsers/` (e.g., `myframework.py`)
2. Subclass `BaseParser` and implement `can_parse()` and `parse()`
3. Register it in `agent_failure_analyzer/parsers/registry.py`
4. Add sample log files to `sample_logs/`
5. Add tests in `tests/test_parsers.py`

Alternatively, you can use the **plugin system** by adding an entry point in your own package:

```toml
[project.entry-points."afa.parsers"]
myframework = "mypackage.parser:MyFrameworkParser"
```

## Adding a New Failure Subcategory

1. Add the enum value to `FailureSubcategory` in `taxonomy.py`
2. Map it to its parent category in `SUBCATEGORY_TO_CATEGORY`
3. Add detection logic in `analyzers/classifier.py`
4. Add tests in `tests/test_classifier.py`

## Code Style

- **Line length**: 100 characters (configured in `pyproject.toml`)
- **Imports**: sorted by ruff (isort-compatible)
- **Type hints**: use `from __future__ import annotations` for all modules
- **Python version**: 3.10+ (use `X | Y` union syntax, not `Union[X, Y]`)

## Submitting Changes

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Make your changes and add tests
4. Ensure all checks pass: `ruff check . && pytest tests/ -v`
5. Commit with a clear message describing the change
6. Open a pull request against `main`

## Reporting Issues

Use the [GitHub issue tracker](https://github.com/cobusgreyling/agent-failure-analyzer/issues) with the provided templates for bug reports and feature requests.

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
