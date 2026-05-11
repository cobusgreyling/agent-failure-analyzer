# Agent Failure Analyzer

[![CI](https://github.com/cobusgreyling/agent-failure-analyzer/actions/workflows/ci.yml/badge.svg)](https://github.com/cobusgreyling/agent-failure-analyzer/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![PyPI version](https://img.shields.io/pypi/v/agent-failure-analyzer.svg)](https://pypi.org/project/agent-failure-analyzer/)

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

Or from source:

```bash
git clone https://github.com/cobusgreyling/agent-failure-analyzer.git
cd agent-failure-analyzer
pip install .
```

## Demo

```
$ afa analyze ./sample_logs/ --cost

Cost Waste Estimation
┏━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━━━━━┓
┃ Session                ┃ Total Tokens ┃ Wasted Tokens┃ Waste % ┃ Est. Wasted $┃
┡━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━━━━━┩
│ context_overflow       │        1,583 │           23 │      1% │     $0.0002 │
│ real_world_session     │        8,710 │        7,501 │     86% │     $0.0675 │
│ tool_loop              │          207 │          173 │     84% │     $0.0016 │
│ crewai_hallucination   │       23,000 │       19,290 │     84% │     $0.8681 │
└────────────────────────┴──────────────┴──────────────┴─────────┴─────────────┘
  Total estimated waste: $0.94

Agent Failure Analysis Report — 6 sessions analyzed
  Total Sessions    6        Failed Sessions    4
  Total Failures    26       Failure Rate       67%

Top Failure Types
  1. fabricated_file_path      8
  2. invalid_tool_args         4
  3. nonexistent_dependency    3
  4. repeated_tool_failure     2
  5. identical_action_loop     2
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

# Compare two sessions
afa compare session_a.jsonl session_b.jsonl

# Show failure trends over time
afa trend --days 30

# Watch directory for changes
afa watch ./logs/ --interval 5

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
| Generic | JSON / JSONL | Fallback |

## How It Works

1. **Parse**: Auto-detect the framework and normalize events into a common model
2. **Classify**: Pattern-match against 30+ failure subcategories using heuristics, optionally enhanced with LLM analysis
3. **Score**: Calculate risk scores based on severity distribution
4. **Report**: Output as terminal tables, JSON, or interactive web dashboard

## CI/CD Integration

Use `afa check` as a quality gate in your pipelines:

```yaml
# GitHub Actions
- name: Check agent quality
  run: afa check ./agent-logs/ --max-risk 0.5 --max-failures 10
```

Exits with code 1 if any session exceeds the risk threshold or total failures exceed the limit.

## Docker

```bash
docker build -t afa .
docker run -v ./logs:/logs afa analyze /logs
docker run -v ./logs:/logs -p 8080:8080 afa dashboard /logs --host 0.0.0.0
```

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
