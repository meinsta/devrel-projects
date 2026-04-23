#!/usr/bin/env python3
"""
analysis.py -- Cross-condition comparison and learning curve analysis.

Usage:
  uv run python analysis.py results/
"""

import json
import sys
from pathlib import Path


def load_run(run_dir: Path) -> dict:
    """Load a single run's results."""
    scores_path = run_dir / "chapter_scores.json"
    config_path = run_dir / "config.json"

    if not scores_path.exists():
        return None

    with open(scores_path) as f:
        scores = json.load(f)

    config = {}
    if config_path.exists():
        with open(config_path) as f:
            config = json.load(f)

    return {
        "name": run_dir.name,
        "config": config,
        "scores": scores,
    }


def compute_learning_slope(scores: list[dict]) -> float:
    """Compute linear regression slope of score vs chapter number."""
    if len(scores) < 2:
        return 0.0

    n = len(scores)
    xs = [s["chapter_num"] for s in scores]
    ys = [s["overall_score"] for s in scores]

    mean_x = sum(xs) / n
    mean_y = sum(ys) / n

    numerator = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    denominator = sum((x - mean_x) ** 2 for x in xs)

    if denominator == 0:
        return 0.0
    return numerator / denominator


def gap_closure(opus_mean: float, haiku_baseline_mean: float, haiku_qdrant_mean: float) -> float:
    """Compute gap closure percentage."""
    gap = opus_mean - haiku_baseline_mean
    if gap <= 0:
        return 100.0  # haiku is already at or above opus
    closure = haiku_qdrant_mean - haiku_baseline_mean
    return (closure / gap) * 100


def compare_all_runs(results_dir: Path):
    """Compare all runs in the results directory."""
    results_dir = Path(results_dir)
    runs = {}

    for d in sorted(results_dir.iterdir()):
        if not d.is_dir():
            continue
        run = load_run(d)
        if run:
            runs[d.name] = run

    if not runs:
        print("no runs found in", results_dir)
        return

    print(f"\n{'='*60}")
    print("EXPERIMENT COMPARISON")
    print(f"{'='*60}")

    # Per-run summary
    for name, run in runs.items():
        scores = [s["overall_score"] for s in run["scores"] if s.get("overall_score")]
        if not scores:
            continue
        mean = sum(scores) / len(scores)
        slope = compute_learning_slope(run["scores"])
        condition = run["config"].get("condition", name)
        print(f"\n  {condition} ({name}):")
        print(f"    chapters: {len(scores)}")
        print(f"    mean score: {mean:.2f}")
        print(f"    learning slope: {slope:+.4f}")
        print(f"    score range: {min(scores):.2f} - {max(scores):.2f}")

    # Gap closure analysis
    opus_run = runs.get("opus_baseline")
    baseline_runs = [r for name, r in runs.items() if "baseline" in name and "opus" not in name]
    qdrant_runs = [r for name, r in runs.items() if "qdrant" in name]

    if opus_run and baseline_runs and qdrant_runs:
        opus_scores = [s["overall_score"] for s in opus_run["scores"] if s.get("overall_score")]
        baseline_scores = [s["overall_score"] for s in baseline_runs[0]["scores"] if s.get("overall_score")]
        qdrant_scores = [s["overall_score"] for s in qdrant_runs[0]["scores"] if s.get("overall_score")]

        if opus_scores and baseline_scores and qdrant_scores:
            opus_mean = sum(opus_scores) / len(opus_scores)
            baseline_mean = sum(baseline_scores) / len(baseline_scores)
            qdrant_mean = sum(qdrant_scores) / len(qdrant_scores)

            closure = gap_closure(opus_mean, baseline_mean, qdrant_mean)

            print(f"\n{'='*60}")
            print("GAP CLOSURE ANALYSIS")
            print(f"{'='*60}")
            print(f"  Opus mean:           {opus_mean:.2f}")
            print(f"  Haiku baseline mean: {baseline_mean:.2f}")
            print(f"  Haiku+Qdrant mean:   {qdrant_mean:.2f}")
            print(f"  Gap (Opus-Haiku):    {opus_mean - baseline_mean:.2f}")
            print(f"  Closure:             {closure:.1f}%")

    # Per-dimension breakdown
    print(f"\n{'='*60}")
    print("PER-DIMENSION BREAKDOWN")
    print(f"{'='*60}")

    dimensions = [
        "voice_adherence", "beat_coverage", "character_voice",
        "prose_quality", "engagement", "lore_integration",
    ]

    for name, run in runs.items():
        condition = run["config"].get("condition", name)
        print(f"\n  {condition}:")
        dim_scores = {d: [] for d in dimensions}
        for s in run["scores"]:
            er = s.get("eval_result", {})
            for d in dimensions:
                val = er.get(d)
                if isinstance(val, dict) and "score" in val:
                    dim_scores[d].append(val["score"])
        for d in dimensions:
            if dim_scores[d]:
                mean = sum(dim_scores[d]) / len(dim_scores[d])
                print(f"    {d}: {mean:.2f}")

    # Save comparison
    comparison = {
        "runs": {name: {
            "condition": r["config"].get("condition", name),
            "mean_score": sum(s["overall_score"] for s in r["scores"] if s.get("overall_score")) / max(1, len([s for s in r["scores"] if s.get("overall_score")])),
            "learning_slope": compute_learning_slope(r["scores"]),
            "chapter_count": len(r["scores"]),
        } for name, r in runs.items()},
    }
    with open(results_dir / "comparison.json", "w") as f:
        json.dump(comparison, f, indent=2)
    print(f"\n  Saved to {results_dir / 'comparison.json'}")


if __name__ == "__main__":
    results_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("results")
    compare_all_runs(results_dir)
