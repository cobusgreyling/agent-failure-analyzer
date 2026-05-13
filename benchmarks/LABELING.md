# Labeling Guide

The benchmark in `run_benchmark.py` compares classifier output to hand-labeled
ground truth in `labels.json`. Labels are the only thing keeping the classifier
honest — please keep this file accurate.

## Adding a new labeled sample

1. Drop a real (anonymized) session log into `sample_logs/`. Use the existing
   `claude_code_real_*` files as a format reference for each framework.
2. Add an entry in `labels.json`:

   ```json
   "your_sample.jsonl": {
     "expected_categories": ["tool_misuse", "loop_repetition"],
     "expected_failures": ["repeated_tool_failure", "identical_action_loop"],
     "min_risk": 0.4,
     "notes": "Short human description of what actually went wrong."
   }
   ```

3. Run `python -m benchmarks.run_benchmark` and confirm the file appears in
   the output. Misses are fine — the goal is honest measurement, not a perfect
   classifier.
4. Update the baseline if the new sample changes overall F1:
   `python -m benchmarks.run_benchmark --save benchmarks/baseline.json`.
   Mention this in your PR description.

## Labeling rules

- **One labeler per sample is OK** for now, but mark the labeler in `notes`.
  As we grow past ~30 samples we should aim for two-labeler agreement on a
  ~10% subset and report Cohen's κ.
- **Use the published taxonomy** (`agent_failure_analyzer/taxonomy.py`) verbatim
  — values must match `FailureCategory` / `FailureSubcategory` enum names.
- **Label what *actually* happened**, not what the classifier currently
  detects. The benchmark only has value if the labels are independent of the
  detector.
- **Be conservative**. If a subcategory is debatable, leave it out and add a
  note. Over-labeling inflates false-negatives and gives the wrong incentive.
- **Anonymize before committing**. Run `afa anonymize` on real logs. Replace
  API keys, file paths under `/Users/`, email addresses, and any project
  identifiers.

## Regenerating the baseline

The CI step `python -m benchmarks.run_benchmark --baseline` compares current
metrics against `benchmarks/baseline.json` and fails on F1 regressions larger
than 2 percentage points. To update the baseline (after an *intentional*
metric change):

```bash
python -m benchmarks.run_benchmark --save benchmarks/baseline.json
git add benchmarks/baseline.json
```

Always include a 1-line justification in the PR ("baseline updated:
+5pp subcategory F1 from new keyword set").
