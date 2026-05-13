"""
Benchmark suite for measuring classifier accuracy.

Compares heuristic classifier output against hand-labeled expected
failures from labels.json. Reports precision, recall, and F1 — overall
and per-category — for both failure subcategories and categories.

Usage:
    python -m benchmarks.run_benchmark
    python -m benchmarks.run_benchmark --json
    python -m benchmarks.run_benchmark --save benchmarks/baseline.json
    python -m benchmarks.run_benchmark --baseline benchmarks/baseline.json
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

from agent_failure_analyzer.analyzers.engine import AnalysisEngine

SAMPLE_DIR = Path(__file__).parent.parent / "sample_logs"
LABELS_PATH = Path(__file__).parent / "labels.json"
DEFAULT_BASELINE = Path(__file__).parent / "baseline.json"

# Regression gate: fail CI if F1 drops more than this much vs baseline.
F1_REGRESSION_TOLERANCE = 0.02


def load_labels() -> dict:
    """Load hand-labeled expected failures."""
    return json.loads(LABELS_PATH.read_text())


def _prf(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    precision = tp / max(tp + fp, 1)
    recall = tp / max(tp + fn, 1)
    f1 = 2 * precision * recall / max(precision + recall, 1e-9)
    return precision, recall, f1


def run_benchmark(verbose: bool = True) -> dict[str, Any]:
    """Run the benchmark and return metrics.

    Returns a dict with overall P/R/F1 (subcategory + category), per-category
    breakdown (TP/FP/FN/P/R/F1/support), and per_file diagnostics.
    """
    labels = load_labels()
    engine = AnalysisEngine()

    total_sub_tp = total_sub_fp = total_sub_fn = 0
    total_cat_tp = total_cat_fp = total_cat_fn = 0

    # Per-category aggregates (keyed by category name).
    per_cat_tp: dict[str, int] = defaultdict(int)
    per_cat_fp: dict[str, int] = defaultdict(int)
    per_cat_fn: dict[str, int] = defaultdict(int)

    per_file: list[dict] = []

    for filename, expected in labels.items():
        filepath = SAMPLE_DIR / filename
        if not filepath.exists():
            if verbose:
                print(f"  SKIP {filename} (file not found)")
            continue

        results = engine.analyze_file(filepath)
        if not results:
            if verbose:
                print(f"  SKIP {filename} (no sessions parsed)")
            continue

        result = results[0]
        detected_subs = {f.subcategory.value for f in result.failures}
        detected_cats = {f.category.value for f in result.failures}
        expected_subs = set(expected["expected_failures"])
        expected_cats = set(expected["expected_categories"])

        sub_tp = len(detected_subs & expected_subs)
        sub_fp = len(detected_subs - expected_subs)
        sub_fn = len(expected_subs - detected_subs)

        cat_tp = len(detected_cats & expected_cats)
        cat_fp = len(detected_cats - expected_cats)
        cat_fn = len(expected_cats - detected_cats)

        total_sub_tp += sub_tp
        total_sub_fp += sub_fp
        total_sub_fn += sub_fn
        total_cat_tp += cat_tp
        total_cat_fp += cat_fp
        total_cat_fn += cat_fn

        for c in detected_cats & expected_cats:
            per_cat_tp[c] += 1
        for c in detected_cats - expected_cats:
            per_cat_fp[c] += 1
        for c in expected_cats - detected_cats:
            per_cat_fn[c] += 1

        per_file.append({
            "file": filename,
            "expected_subs": sorted(expected_subs),
            "detected_subs": sorted(detected_subs),
            "sub_tp": sub_tp, "sub_fp": sub_fp, "sub_fn": sub_fn,
            "expected_cats": sorted(expected_cats),
            "detected_cats": sorted(detected_cats),
            "cat_tp": cat_tp, "cat_fp": cat_fp, "cat_fn": cat_fn,
            "risk_score": round(result.risk_score, 3),
            "min_risk_met": result.risk_score >= expected.get("min_risk", 0),
        })

        if verbose:
            status = "PASS" if sub_fn == 0 and cat_fn == 0 else "MISS"
            print(f"  {status} {filename}")
            if sub_fn > 0:
                print(f"       missed subcategories: {sorted(expected_subs - detected_subs)}")
            if sub_fp > 0:
                print(f"       extra subcategories:  {sorted(detected_subs - expected_subs)}")

    sub_p, sub_r, sub_f1 = _prf(total_sub_tp, total_sub_fp, total_sub_fn)
    cat_p, cat_r, cat_f1 = _prf(total_cat_tp, total_cat_fp, total_cat_fn)

    per_category: dict[str, dict[str, float | int]] = {}
    all_cats = set(per_cat_tp) | set(per_cat_fp) | set(per_cat_fn)
    for c in sorted(all_cats):
        tp, fp, fn = per_cat_tp[c], per_cat_fp[c], per_cat_fn[c]
        p, r, f1 = _prf(tp, fp, fn)
        per_category[c] = {
            "tp": tp, "fp": fp, "fn": fn,
            "precision": round(p, 3),
            "recall": round(r, 3),
            "f1": round(f1, 3),
            "support": tp + fn,
        }

    metrics = {
        "subcategory_precision": round(sub_p, 3),
        "subcategory_recall": round(sub_r, 3),
        "subcategory_f1": round(sub_f1, 3),
        "category_precision": round(cat_p, 3),
        "category_recall": round(cat_r, 3),
        "category_f1": round(cat_f1, 3),
        "per_category": per_category,
        "per_file": per_file,
    }

    if verbose:
        print(f"\n  Subcategory — P: {sub_p:.1%}  R: {sub_r:.1%}  F1: {sub_f1:.1%}")
        print(f"  Category    — P: {cat_p:.1%}  R: {cat_r:.1%}  F1: {cat_f1:.1%}")
        if per_category:
            print("\n  Per-category (category-level):")
            print(f"    {'category':<22} {'P':>6} {'R':>6} {'F1':>6} {'support':>8}")
            for c, m in per_category.items():
                print(
                    f"    {c:<22} {m['precision']:>6.1%} {m['recall']:>6.1%} "
                    f"{m['f1']:>6.1%} {m['support']:>8}"
                )

    return metrics


def _diff_against_baseline(metrics: dict, baseline_path: Path) -> int:
    """Compare current metrics against a baseline. Returns exit code."""
    if not baseline_path.exists():
        print(f"\nNo baseline at {baseline_path} — skipping regression check.")
        return 0

    baseline = json.loads(baseline_path.read_text())
    keys = ("subcategory_f1", "category_f1")
    regressed = False
    print(f"\nBaseline diff (tolerance: {F1_REGRESSION_TOLERANCE:+.1%}):")
    for k in keys:
        cur = metrics.get(k, 0.0)
        base = baseline.get(k, 0.0)
        delta = cur - base
        marker = ""
        if delta < -F1_REGRESSION_TOLERANCE:
            marker = "  REGRESSION"
            regressed = True
        elif delta > F1_REGRESSION_TOLERANCE:
            marker = "  IMPROVED"
        print(f"  {k:<24} {base:>6.1%} → {cur:>6.1%}  ({delta:+.1%}){marker}")

    return 1 if regressed else 0


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true", help="Emit metrics as JSON.")
    ap.add_argument("--save", type=Path, metavar="PATH",
                    help="Write metrics JSON to PATH (e.g. for a new baseline).")
    ap.add_argument("--baseline", type=Path, metavar="PATH",
                    nargs="?", const=DEFAULT_BASELINE,
                    help="Compare against baseline JSON; fail on F1 regression.")
    args = ap.parse_args()

    verbose = not args.json
    if verbose:
        print("Agent Failure Analyzer — Classifier Benchmark\n")
    metrics = run_benchmark(verbose=verbose)

    if args.save:
        args.save.write_text(json.dumps(metrics, indent=2, sort_keys=True))
        if verbose:
            print(f"\nSaved metrics to {args.save}")

    exit_code = 0
    if args.baseline:
        exit_code = _diff_against_baseline(metrics, args.baseline)
    else:
        # Legacy floor: fail if category recall drops below 30%.
        if metrics["category_recall"] < 0.3 and verbose:
            print("\nFAIL: Category recall below 30%")
            exit_code = 1

    if args.json:
        print(json.dumps(metrics, indent=2, sort_keys=True))

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
