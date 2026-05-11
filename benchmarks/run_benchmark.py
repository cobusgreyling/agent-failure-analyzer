"""
Benchmark suite for measuring classifier accuracy.

Compares heuristic classifier output against hand-labeled expected
failures from labels.json. Reports precision, recall, and F1 for
both failure subcategories and categories.

Usage:
    python -m benchmarks.run_benchmark
    # or
    afa benchmark
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from agent_failure_analyzer.analyzers.engine import AnalysisEngine

SAMPLE_DIR = Path(__file__).parent.parent / "sample_logs"
LABELS_PATH = Path(__file__).parent / "labels.json"


def load_labels() -> dict:
    """Load hand-labeled expected failures."""
    return json.loads(LABELS_PATH.read_text())


def run_benchmark(verbose: bool = True) -> dict:
    """Run the benchmark and return metrics.

    Returns a dict with:
    - subcategory_precision, subcategory_recall, subcategory_f1
    - category_precision, category_recall, category_f1
    - per_file results
    """
    labels = load_labels()
    engine = AnalysisEngine()

    total_sub_tp = 0
    total_sub_fp = 0
    total_sub_fn = 0
    total_cat_tp = 0
    total_cat_fp = 0
    total_cat_fn = 0
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

        # Subcategory metrics
        sub_tp = len(detected_subs & expected_subs)
        sub_fp = len(detected_subs - expected_subs)
        sub_fn = len(expected_subs - detected_subs)

        # Category metrics
        cat_tp = len(detected_cats & expected_cats)
        cat_fp = len(detected_cats - expected_cats)
        cat_fn = len(expected_cats - detected_cats)

        total_sub_tp += sub_tp
        total_sub_fp += sub_fp
        total_sub_fn += sub_fn
        total_cat_tp += cat_tp
        total_cat_fp += cat_fp
        total_cat_fn += cat_fn

        file_result = {
            "file": filename,
            "expected_subs": sorted(expected_subs),
            "detected_subs": sorted(detected_subs),
            "sub_tp": sub_tp,
            "sub_fp": sub_fp,
            "sub_fn": sub_fn,
            "expected_cats": sorted(expected_cats),
            "detected_cats": sorted(detected_cats),
            "cat_tp": cat_tp,
            "cat_fp": cat_fp,
            "cat_fn": cat_fn,
            "risk_score": result.risk_score,
            "min_risk_met": result.risk_score >= expected.get("min_risk", 0),
        }
        per_file.append(file_result)

        if verbose:
            status = "PASS" if sub_fn == 0 and cat_fn == 0 else "MISS"
            print(f"  {status} {filename}")
            if sub_fn > 0:
                print(f"       missed subcategories: {expected_subs - detected_subs}")
            if sub_fp > 0:
                print(f"       extra subcategories:  {detected_subs - expected_subs}")

    # Calculate aggregate metrics
    sub_precision = total_sub_tp / max(total_sub_tp + total_sub_fp, 1)
    sub_recall = total_sub_tp / max(total_sub_tp + total_sub_fn, 1)
    sub_f1 = 2 * sub_precision * sub_recall / max(sub_precision + sub_recall, 1e-9)

    cat_precision = total_cat_tp / max(total_cat_tp + total_cat_fp, 1)
    cat_recall = total_cat_tp / max(total_cat_tp + total_cat_fn, 1)
    cat_f1 = 2 * cat_precision * cat_recall / max(cat_precision + cat_recall, 1e-9)

    metrics = {
        "subcategory_precision": round(sub_precision, 3),
        "subcategory_recall": round(sub_recall, 3),
        "subcategory_f1": round(sub_f1, 3),
        "category_precision": round(cat_precision, 3),
        "category_recall": round(cat_recall, 3),
        "category_f1": round(cat_f1, 3),
        "per_file": per_file,
    }

    if verbose:
        print(f"\n  Subcategory — P: {sub_precision:.1%}  R: {sub_recall:.1%}  F1: {sub_f1:.1%}")
        print(f"  Category    — P: {cat_precision:.1%}  R: {cat_recall:.1%}  F1: {cat_f1:.1%}")

    return metrics


def main():
    print("Agent Failure Analyzer — Classifier Benchmark\n")
    metrics = run_benchmark(verbose=True)
    print(f"\nOverall F1: {metrics['subcategory_f1']:.1%} (subcategory), "
          f"{metrics['category_f1']:.1%} (category)")

    # Exit non-zero if recall drops below 50%
    if metrics["subcategory_recall"] < 0.5:
        print("\nWARN: Subcategory recall below 50%")
        sys.exit(1)


if __name__ == "__main__":
    main()
