# Agent Failure Analyzer

[![CI](https://github.com/cobusgreyling/agent-failure-analyzer/actions/workflows/ci.yml/badge.svg)](https://github.com/cobusgreyling/agent-failure-analyzer/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![PyPI version](https://img.shields.io/pypi/v/agent-failure-analyzer.svg)](https://pypi.org/project/agent-failure-analyzer/)
[![codecov](https://codecov.io/gh/cobusgreyling/agent-failure-analyzer/branch/main/graph/badge.svg)](https://codecov.io/gh/cobusgreyling/agent-failure-analyzer)

```
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║       █████╗ ██████╗  █████╗     ╔═══════════════════════════════════╗       ║
║      ██╔══██╗██╔═══╝ ██╔══██╗    ║  ◉ context_overflow   ██████░░    ║       ║
║      ███████║█████╗  ███████║    ║  ◉ tool_misuse        █████░░░    ║       ║
║      ██╔══██║██╔══╝  ██╔══██║    ║  ◉ instruction_drift  ████░░░░    ║       ║
║      ██║  ██║██║     ██║  ██║    ║  ◉ hallucination      ███░░░░░    ║       ║
║      ╚═╝  ╚═╝╚═╝     ╚═╝  ╚═╝    ║  ◉ loop_repetition    ██░░░░░░    ║       ║
║                                  ║  ◉ error_cascade      █░░░░░░░    ║       ║
║      Agent Failure Analyzer      ╚═══════════════════════════════════╝       ║
║                                                                              ║
║      Classify and diagnose AI agent session failures                         ║
║      across frameworks. Heuristic + LLM-powered analysis.                    ║
║                                                                              ║
║      ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐                  ║
║      │  Claude  │  │ LangChain│  │  CrewAI  │  │ Generic  │                  ║
║      │   Code   │  │ LangSmith│  │          │  │ JSON(L)  │                  ║
║      └─────┬────┘  └──────┬───┘  └────────┬─┘  └──────────┘                  ║
║            └──────────────┴───────────────┴──────────────┘                   ║
║                                    │                                         ║
║                              ┌─────▼─────┐                                   ║
║                              │  CLASSIFY  │                                  ║
║                              │ ◇ heuristic│                                  ║
║                              │ ◆ LLM pass │                                  ║
║                              └─────┬─────┘                                   ║
║                     ┌──────────────┼──────────────┐                          ║
║               ┌─────▼─────┐  ┌─────▼─────┐  ┌─────▼─────┐                    ║
║               │ Terminal  │  │   JSON    │  │ Dashboard │                    ║
║               │  Report   │  │  Export   │  │    Web    │                    ║
║               └───────────┘  └───────────┘  └───────────┘                    ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
```

Classify and analyze AI agent session failures across frameworks.

## Overview

Agent Failure Analyzer ingests session logs from AI agent frameworks (Claude Code, LangChain, CrewAI, and generic JSON), classifies failures using a comprehensive taxonomy, and generates diagnostic reports.

Most agent failures aren't reasoning failures — they're **context failures**, **tool misuse**, **instruction drift**, or **error cascades**. This tool makes those patterns visible and quantifiable.

## Failure Taxonomy

| Category | Description |
|---|---|
| `context_overflow` | Context window filled up, causing information loss or session termination |
| `tool_misuse` | Wrong tool selected, invalid arguments, or unrecovered tool errors |
| `instruction_drift` | Agent forgot or deviated from instructions, goals, or constraints |
| `hallucination` | Fabricated file paths, APIs, facts, or dependencies |
| `loop_repetition` | Repeated identical or semantically similar actions without progress |
| `error_cascade` | Initial error triggered a chain of unrecoverable failures |
| `planning_failure` | Flawed task decomposition or no planning before execution |
| `resource_exhaustion` | Hit token, rate, cost, or time limits |
| `safety_refusal` | Agent refused to proceed (appropriate or false positive) |

Each category has granular subcategories and severity levels (critical, high, medium, low, info).

## Installation

```bash
pip install agent-failure-analyzer
```

Optional extras:

```bash
pip install 'agent-failure-analyzer[dashboard]'  # web dashboard (fastapi/uvicorn)
pip install 'agent-failure-analyzer[llm]'        # LLM-assisted classification (anthropic)
pip install 'agent-failure-analyzer[pdf]'        # PDF reports (weasyprint)
pip install 'agent-failure-analyzer[otel]'       # OpenTelemetry export
```

Or from source:

```bash
git clone https://github.com/cobusgreyling/agent-failure-analyzer.git
cd agent-failure-analyzer
pip install .
```

## Quick Demo

```bash
# Install and analyze in 30 seconds
$ pip install agent-failure-analyzer
$ afa analyze ./sample_logs/

Agent Failure Analysis Report — 9 sessions analyzed
  Total Sessions    9        Failed Sessions    6
  Total Failures    31       Failure Rate       67%

Severity Distribution
  CRITICAL  ████░░░░░░  3
  HIGH      ██████░░░░  7
  MEDIUM    ████████░░  12
  LOW       ██████████  9

Top Failure Types
  1. fabricated_file_path      8
  2. invalid_tool_args         4
  3. cascading_tool_errors     3
  4. nonexistent_dependency    3
  5. identical_action_loop     2

$ afa explain ./sample_logs/claude_code_context_overflow.jsonl 1

  Failure #1 of 2 in session: claude_code_context_overflow
  Category:     context_overflow
  Subcategory:  context_window_exceeded
  Severity:     CRITICAL
  Confidence:   90%

  What happened:
    The session hit the model's context window limit after accumulating
    verbose tool outputs without summarization.

  How to fix:
    → Enable context compaction / summarization before the window fills.
    → Split long tasks into smaller sub-tasks with fresh context.
    → Use a model with a larger context window.

$ afa check ./sample_logs/ --max-risk 0.5
  FAIL: 3 sessions exceed risk threshold (max: 0.50)
  Exit code: 1
```

### Cost Waste Estimation

```bash
$ afa analyze ./sample_logs/ --cost

Cost Waste Estimation
┏━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━━━━━┓
┃ Session                ┃ Total Tokens ┃ Wasted Tokens┃ Waste % ┃ Est. Wasted ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━━━━━┩
│ context_overflow       │        1,583 │           23 │      1% │     $0.0002 │
│ real_world_session     │        8,710 │        7,501 │     86% │     $0.0675 │
│ tool_loop              │          207 │          173 │     84% │     $0.0016 │
│ crewai_hallucination   │       23,000 │       19,290 │     84% │     $0.8681 │
└────────────────────────┴──────────────┴──────────────┴─────────┴─────────────┘
  Total estimated waste: $0.94
```

## Usage

### CLI

```bash
# Analyze a single log file
afa analyze session.jsonl

# Analyze a directory of logs
afa analyze ./logs/

# Output as JSON
afa analyze ./logs/ -f json -o report.json

# Filter by confidence threshold
afa analyze ./logs/ --min-confidence 0.7

# Show cost waste estimation
afa analyze ./logs/ --cost

# Persist results for trend tracking
afa analyze ./logs/ --store

# Auto-discover Claude Code sessions
afa ingest --claude-code

# CI quality gate
afa check ./logs/ --max-risk 0.5 --max-failures 10

# Explain a specific failure in detail
afa explain session.jsonl 1        # explain failure #1
afa explain session.jsonl 3 -s 1   # failure #3 in session index 1

# Compare two sessions
afa compare session_a.jsonl session_b.jsonl

# Show failure trends over time
afa trend --days 30

# Watch directory for changes
afa watch ./logs/ --interval 5

# Output as CSV or standalone HTML
afa analyze ./logs/ -f csv -o report.csv
afa analyze ./logs/ -f html -o report.html

# Interactive TUI mode
afa tui ./logs/

# Session diffing (requires prior --store runs)
afa diff <session_id>

# Webhook/Slack notifications on high risk
afa analyze ./logs/ --notify-webhook https://hooks.example.com/afa
afa analyze ./logs/ --notify-slack https://hooks.slack.com/services/...

# Run classifier benchmark
afa benchmark

# Generate shell completions
eval "$(afa completions bash)"

# Show the failure taxonomy
afa taxonomy

# Launch web dashboard
afa dashboard ./logs/
```

### Python API

```python
from agent_failure_analyzer.analyzers.engine import AnalysisEngine

engine = AnalysisEngine()

# Analyze a directory
batch = engine.analyze_directory("./logs/")
print(f"Sessions: {batch.total_sessions}")
print(f"Failed: {batch.failed_sessions}")
print(f"Top failures: {batch.top_failures}")

# Analyze a single file
results = engine.analyze_file("session.jsonl")
for result in results:
    print(f"Risk: {result.risk_score:.0%}")
    for failure in result.failures:
        print(f"  [{failure.severity.value}] {failure.category.value}: {failure.description}")
```

### Web Dashboard

```bash
afa dashboard ./logs/ --port 8080
```

Opens a browser-based dashboard with:
- Failure distribution charts
- Severity breakdown
- Per-session drill-down with evidence
- Risk scoring

## MCP Server

Expose the analyzer as an [MCP](https://modelcontextprotocol.io) server so
MCP-aware clients (Claude Code, Claude Desktop, IDE integrations) can call
it directly — "explain why my last session failed", "diff these two runs",
"what does `tool_misuse` mean" — without leaving the agent.

```bash
pip install 'agent-failure-analyzer[mcp]'
afa mcp     # speaks MCP over stdio
```

Tools exposed:

| Tool | Purpose |
|---|---|
| `analyze` | Classify failures in a log file or directory; returns JSON report |
| `explain` | Detailed explanation + remediation for a specific failure |
| `compare` | Diff two session logs (risk delta, new/resolved failures) |
| `trend` | Trend data from the stored SQLite history |
| `taxonomy` | Full failure taxonomy with descriptions |
| `remediation` | Fix suggestions for a given subcategory |

### Claude Desktop / Claude Code

Add to your MCP client config (e.g. `~/Library/Application Support/Claude/claude_desktop_config.json` on macOS):

```json
{
  "mcpServers": {
    "agent-failure-analyzer": {
      "command": "afa",
      "args": ["mcp"]
    }
  }
}
```

Then in the client:

> "Use the `agent-failure-analyzer` tools to analyze `~/agent-logs/`. Explain the top failure and show me how to fix it."

## LLM-Powered Classification

For deeper analysis beyond heuristics, enable LLM classification using Claude:

```bash
pip install agent-failure-analyzer[llm]
export ANTHROPIC_API_KEY=your-key

# Always use LLM for every session
afa analyze ./logs/ --llm

# Only use LLM when heuristics are uncertain (cost-efficient)
afa analyze ./logs/ --llm-auto

# Use a specific model
afa analyze ./logs/ --llm --llm-model claude-opus-4-6
```

```python
from agent_failure_analyzer.analyzers.engine import AnalysisEngine

# LLM on every session
engine = AnalysisEngine(use_llm=True)

# LLM only when heuristics are uncertain
engine = AnalysisEngine(llm_auto=True)
```

The LLM classifier catches what heuristics miss:
- Subtle instruction drift where the agent gradually deviates from the goal
- Semantic hallucinations embedded in plausible-sounding text
- Planning failures where individual steps succeed but the approach is wrong
- Quality issues (technically correct but poor solution)

Uses prompt caching — the taxonomy system prompt is cached across calls, reducing cost for batch analysis.

## Supported Log Formats

| Framework | Format | Auto-detected |
|---|---|---|
| Claude Code | JSONL (session logs) | Yes |
| LangChain / LangSmith | JSON (traces, runs) | Yes |
| CrewAI | JSON (crew output) | Yes |
| AutoGen | JSON / JSONL (conversations) | Yes |
| OpenAI Assistants | JSON (threads, runs) | Yes |
| Generic | JSON / JSONL | Fallback |

## How It Works

1. **Parse**: Auto-detect the framework and normalize events into a common model
2. **Classify**: Pattern-match against 30+ failure subcategories using heuristics, optionally enhanced with LLM analysis
3. **Score**: Calculate risk scores based on severity distribution
4. **Report**: Output as terminal tables, JSON, or interactive web dashboard

### Heuristic limitations

The built-in classifier is intentionally simple: it matches keywords against
error messages and tool results (in English), counts tool retries, looks at
token totals, and inspects event sequences. It does **not** reason about
intent. As a result it will:

- Miss failures that don't surface as an error string (silent stalls,
  semantically-wrong tool arguments that don't throw).
- Miss non-English error messages.
- Over-fire on benign retries (e.g. exponential-backoff that ultimately succeeds).
- Misclassify any failure mode that isn't already in the keyword tables in
  `agent_failure_analyzer/analyzers/classifier.py`.

Treat heuristic output as a fast, free triage signal — useful for CI gates
and dashboards, **not** as ground truth. See [`benchmarks/LABELING.md`](benchmarks/LABELING.md)
for the labeled corpus we measure against and current F1 in CI.

### LLM-assisted classification

`--llm` always runs the LLM classifier in addition to heuristics. `--llm-auto`
runs the LLM only when heuristics are likely insufficient. The auto-trigger
fires when (any of):

- The session outcome is `failure`/`abandoned` and heuristics found nothing.
- The session outcome is `failure`/`abandoned` and *every* heuristic finding
  has confidence below 0.6.
- The session has more than 20 events and heuristics found nothing (subtle
  failures often hide in long, "successful-looking" traces).

When both heuristic and LLM agree on a subcategory, the higher-confidence
finding wins; LLM-only findings are kept and tagged.

### Risk score

`risk_score ∈ [0.0, 1.0]` is a single number per session, derived as:

```
weights = {critical: 1.0, high: 0.7, medium: 0.4, low: 0.15, info: 0.05}
weighted_avg = sum(weights[f.severity] for f in failures) / len(failures)
volume_factor = min(len(failures) / 3, 1.0)
risk_score = min(1.0, weighted_avg * volume_factor)
```

In practice:

- 1 critical failure → 0.33 (high severity but low volume)
- 3+ critical failures → 1.00 (saturates)
- 3 medium failures → 0.40
- No failures → 0.00

`afa check --max-risk 0.5` and `--notify-threshold` use this score. Calibrate
the threshold against your own logs — the default 0.5 is a starting point, not
a universal truth.

## CI/CD Integration

Use `afa check` as a quality gate in your pipelines:

```yaml
# GitHub Actions — basic quality gate
- name: Check agent quality
  run: afa check ./agent-logs/ --max-risk 0.5 --max-failures 10
```

Exits with code 1 if any session exceeds the risk threshold or total failures exceed the limit.

### PR Comment Workflow

Add this reusable workflow to automatically post failure analysis as a PR comment:

```yaml
# .github/workflows/agent-quality.yml
name: Agent Quality Check

on:
  pull_request:
    paths:
      - "agent-logs/**"

permissions:
  pull-requests: write

jobs:
  analyze:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install AFA
        run: pip install agent-failure-analyzer

      - name: Run analysis
        id: afa
        run: |
          afa analyze ./agent-logs/ -f markdown -o report.md --cost
          echo "report<<EOF" >> "$GITHUB_OUTPUT"
          cat report.md >> "$GITHUB_OUTPUT"
          echo "EOF" >> "$GITHUB_OUTPUT"

          # Quality gate (non-blocking for the comment step)
          afa check ./agent-logs/ --max-risk 0.5 || echo "gate_failed=true" >> "$GITHUB_OUTPUT"

      - name: Post PR comment
        uses: marocchino/sticky-pull-request-comment@v2
        with:
          header: afa-report
          message: |
            ## Agent Failure Analysis

            ${{ steps.afa.outputs.report }}

            ---
            *Generated by [Agent Failure Analyzer](https://github.com/cobusgreyling/agent-failure-analyzer)*

      - name: Enforce quality gate
        if: steps.afa.outputs.gate_failed == 'true'
        run: |
          echo "::error::Agent quality gate failed — risk score exceeds threshold"
          exit 1
```

### GitHub Action

Use the bundled action directly in your workflow:

```yaml
- uses: cobusgreyling/agent-failure-analyzer@main
  with:
    path: ./agent-logs/
    max-risk: "0.5"
    format: json
    output-file: report.json
```

## Docker

```bash
docker build -t afa .
docker run -v ./logs:/logs afa analyze /logs
docker run -v ./logs:/logs -p 8080:8080 afa dashboard /logs --host 0.0.0.0
```

### Docker Compose

Spin up the full observability stack (dashboard + Grafana) with one command:

```bash
docker compose up
```

This starts:
- **AFA Dashboard** on `http://localhost:8080` — interactive failure analysis
- **Grafana** on `http://localhost:3000` — pre-provisioned failure dashboard (login: admin/admin)

Mount your own logs by editing `docker-compose.yml` or overriding the volume:

```bash
docker compose run -v /path/to/your/logs:/logs afa-dashboard analyze /logs
```

## Configuration File

Create `.afa.toml` in your project root or home directory:

```toml
[analysis]
min_severity = "medium"
min_confidence = 0.5
llm_auto = true

[output]
format = "terminal"
store = true
cost = true

[notify]
slack_webhook_url = "https://hooks.slack.com/services/..."
threshold = 0.7
```

CLI flags override config file values. See `.afa.toml.example` for all options.

## Plugin System

Register custom parsers via entry points:

```toml
# In your package's pyproject.toml
[project.entry-points."afa.parsers"]
myframework = "mypackage.parser:MyFrameworkParser"
```

Your parser class must subclass `BaseParser` and implement `can_parse()` and `parse()`.

## Trend Tracking

Persist results across runs and visualize trends:

```bash
# Store results on each run
afa analyze ./logs/ --store

# View trends
afa trend --days 30
```

Data is stored in `~/.afa/history.db` (SQLite).

## License

MIT
