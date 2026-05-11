# Agent Failure Analyzer

```
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║       █████╗ ██████╗  █████╗     ╔═══════════════════════════════════╗       ║
║      ██╔══██╗██╔═══╝ ██╔══██╗    ║  ◉ context_overflow   ██████░░   ║       ║
║      ███████║█████╗  ███████║    ║  ◉ tool_misuse        █████░░░   ║       ║
║      ██╔══██║██╔══╝  ██╔══██║    ║  ◉ instruction_drift  ████░░░░   ║       ║
║      ██║  ██║██║     ██║  ██║    ║  ◉ hallucination      ███░░░░░   ║       ║
║      ╚═╝  ╚═╝╚═╝     ╚═╝  ╚═╝    ║  ◉ loop_repetition    ██░░░░░░   ║       ║
║                                    ║  ◉ error_cascade      █░░░░░░░   ║       ║
║      Agent Failure Analyzer        ╚═══════════════════════════════════╝       ║
║                                                                              ║
║      Classify and diagnose AI agent session failures                         ║
║      across frameworks. Heuristic + LLM-powered analysis.                    ║
║                                                                              ║
║      ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐                 ║
║      │  Claude   │  │ LangChain│  │  CrewAI  │  │ Generic  │                 ║
║      │   Code    │  │ LangSmith│  │          │  │ JSON(L)  │                 ║
║      └─────┬─────┘  └─────┬─────┘  └─────┬─────┘  └─────┬─────┘                 ║
║            └──────────────┴───────────────┴──────────────┘                   ║
║                                    │                                         ║
║                              ┌─────▼─────┐                                  ║
║                              │  CLASSIFY  │                                  ║
║                              │ ◇ heuristic│                                  ║
║                              │ ◆ LLM pass │                                  ║
║                              └─────┬─────┘                                  ║
║                     ┌──────────────┼──────────────┐                          ║
║               ┌─────▼─────┐  ┌─────▼─────┐  ┌─────▼─────┐                   ║
║               │ Terminal  │  │   JSON    │  │ Dashboard │                   ║
║               │  Report   │  │  Export   │  │    Web    │                   ║
║               └───────────┘  └───────────┘  └───────────┘                   ║
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

## Usage

### CLI

```bash
# Analyze a single log file
afa analyze session.jsonl

# Analyze a directory of logs
afa analyze ./logs/

# Output as JSON
afa analyze ./logs/ -f json -o report.json

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

## License

MIT
