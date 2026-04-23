#!/usr/bin/env python3
"""
experiment.py -- Run autonovel under different memory conditions.

Usage:
  uv run python experiment.py --condition=baseline --chapters=1-5
  uv run python experiment.py --condition=dense --chapters=1-5
  uv run python experiment.py --condition=qdrant --chapters=1-5
  uv run python experiment.py --score-opus --chapters=1-19
  uv run python experiment.py --compare
"""

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env")

RESULTS_DIR = BASE_DIR / "results"
CHAPTERS_DIR = BASE_DIR / "chapters"
OPUS_CHAPTERS_DIR = BASE_DIR / "chapters_opus"  # saved Opus originals


def parse_chapter_range(s: str) -> list[int]:
    """Parse '1-5' or '1,3,5' into list of ints."""
    if "-" in s:
        start, end = s.split("-")
        return list(range(int(start), int(end) + 1))
    return [int(x) for x in s.split(",")]


def run_cmd(cmd: str, env: dict = None, timeout: int = 600) -> tuple[str, int]:
    merged_env = {**os.environ, **(env or {})}
    r = subprocess.run(
        cmd, shell=True, capture_output=True, text=True,
        timeout=timeout, env=merged_env,
    )
    return r.stdout + r.stderr, r.returncode


def evaluate_chapter(chapter_num: int, env: dict = None) -> dict:
    """Run evaluate.py on a chapter and parse the JSON result."""
    out, rc = run_cmd(
        f"uv run python evaluate.py --chapter={chapter_num}",
        env=env,
        timeout=300,
    )
    # The eval log is saved as JSON. Find the most recent one.
    import glob as g
    import re
    logs = sorted(g.glob(str(BASE_DIR / "eval_logs" / f"*_ch{chapter_num:02d}.json")))
    if logs:
        with open(logs[-1]) as f:
            return json.load(f)
    # Fallback: try to parse overall_score from stdout
    m = re.search(r"overall_score: ([\d.]+)", out)
    if m:
        return {"overall_score": float(m.group(1)), "raw_output": out}
    return {"error": out[:500], "overall_score": 0}


def score_opus_baseline(chapters: list[int]):
    """Score existing Opus Bells chapters (free, no API calls for drafting)."""
    run_dir = RESULTS_DIR / "opus_baseline"
    run_dir.mkdir(parents=True, exist_ok=True)

    # Ensure opus chapters are in the chapters dir
    if not (CHAPTERS_DIR / "ch_01.md").exists():
        print("error: no chapters found. checkout bells branch chapters first.")
        sys.exit(1)

    # Back up opus chapters so we can restore after haiku runs
    OPUS_CHAPTERS_DIR.mkdir(exist_ok=True)
    for ch in chapters:
        src = CHAPTERS_DIR / f"ch_{ch:02d}.md"
        dst = OPUS_CHAPTERS_DIR / f"ch_{ch:02d}.md"
        if src.exists() and not dst.exists():
            import shutil
            shutil.copy2(src, dst)

    results = []
    for ch in chapters:
        print(f"\n  Scoring Opus chapter {ch}...")
        result = evaluate_chapter(ch)
        score = result.get("overall_score", 0)
        raw = result.get("raw_judge_score", score)
        print(f"  Ch {ch}: {score} (raw: {raw})")
        results.append({
            "chapter_num": ch,
            "overall_score": score,
            "raw_judge_score": raw,
            "eval_result": result,
        })

    with open(run_dir / "chapter_scores.json", "w") as f:
        json.dump(results, f, indent=2)

    mean_score = sum(r["overall_score"] for r in results) / len(results) if results else 0
    print(f"\n  Opus baseline mean score: {mean_score:.2f}")
    return results


def run_experiment(condition: str, chapters: list[int]):
    """Run a full experiment for a given condition."""
    run_id = f"{condition}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    run_dir = RESULTS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    # Restore opus chapters to the chapters dir before haiku overwrites them
    for ch in chapters:
        opus_src = OPUS_CHAPTERS_DIR / f"ch_{ch:02d}.md"
        if opus_src.exists():
            # We'll only keep the previous chapter for continuity
            pass

    # Set up environment for this condition
    env = {
        "EXPERIMENT_CONDITION": condition,
        "EXPERIMENT_MODEL": "claude-haiku-4-5-20251001",
    }

    # Initialize Qdrant collection if needed
    if condition != "baseline":
        from memory.schema import get_client, create_collection, COLLECTION_NAME
        client = get_client()
        # Use a unique collection per run to avoid cross-contamination
        coll_name = f"autonovel_{run_id}"
        env["QDRANT_COLLECTION"] = coll_name
        os.environ["QDRANT_COLLECTION"] = coll_name
        create_collection(client, coll_name)

    results = []
    config = {
        "run_id": run_id,
        "condition": condition,
        "model": "claude-haiku-4-5-20251001",
        "chapters": chapters,
        "started_at": datetime.now().isoformat(),
    }

    for ch in chapters:
        print(f"\n{'='*50}")
        print(f"  CHAPTER {ch} | condition={condition}")
        print(f"{'='*50}")

        # For continuity, ensure previous chapter exists
        # (use opus version for ch-1 if haiku hasn't written it yet)
        prev_ch = ch - 1
        if prev_ch >= 1:
            prev_haiku = CHAPTERS_DIR / f"ch_{prev_ch:02d}.md"
            prev_opus = OPUS_CHAPTERS_DIR / f"ch_{prev_ch:02d}.md"
            if not prev_haiku.exists() and prev_opus.exists():
                import shutil
                shutil.copy2(prev_opus, prev_haiku)

        # Draft
        t0 = time.perf_counter()
        out, rc = run_cmd(
            f"uv run python draft_chapter.py {ch}",
            env=env,
            timeout=600,
        )
        draft_time = time.perf_counter() - t0

        if rc != 0:
            print(f"  DRAFT FAILED: {out[:200]}")
            results.append({"chapter_num": ch, "error": out[:500], "overall_score": 0})
            continue

        # Word count
        ch_text = (CHAPTERS_DIR / f"ch_{ch:02d}.md").read_text()
        word_count = len(ch_text.split())
        print(f"  Words: {word_count} | Draft time: {draft_time:.1f}s")

        # Evaluate
        t0 = time.perf_counter()
        eval_result = evaluate_chapter(ch, env=env)
        eval_time = time.perf_counter() - t0

        score = eval_result.get("overall_score", 0)
        raw = eval_result.get("raw_judge_score", score)
        print(f"  Score: {score} (raw: {raw}) | Eval time: {eval_time:.1f}s")

        # Upsert memory
        if condition != "baseline":
            try:
                from memory.hooks import post_evaluate_hook
                post_evaluate_hook(client, ch, eval_result, run_id, condition)
                print(f"  Memory upserted for chapter {ch}")
            except Exception as e:
                print(f"  Memory upsert failed: {e}")

        results.append({
            "chapter_num": ch,
            "overall_score": score,
            "raw_judge_score": raw,
            "word_count": word_count,
            "draft_time_s": round(draft_time, 1),
            "eval_time_s": round(eval_time, 1),
            "condition": condition,
            "eval_result": eval_result,
        })

        # Save incrementally
        with open(run_dir / "chapter_scores.json", "w") as f:
            json.dump(results, f, indent=2)

    config["finished_at"] = datetime.now().isoformat()
    with open(run_dir / "config.json", "w") as f:
        json.dump(config, f, indent=2)

    mean_score = sum(r["overall_score"] for r in results if r.get("overall_score")) / len(results) if results else 0
    print(f"\n  {condition} mean score: {mean_score:.2f}")
    return results


def compare_results():
    """Compare all experimental results."""
    from analysis import compare_all_runs
    compare_all_runs(RESULTS_DIR)


def main():
    parser = argparse.ArgumentParser(description="autonovel-qdrant experiment runner")
    parser.add_argument("--condition", choices=["baseline", "dense", "qdrant"],
                        help="Experimental condition to run")
    parser.add_argument("--chapters", default="1-19",
                        help="Chapter range (e.g., 1-5 or 1,3,5)")
    parser.add_argument("--score-opus", action="store_true",
                        help="Score existing Opus chapters as baseline")
    parser.add_argument("--compare", action="store_true",
                        help="Compare all completed runs")

    args = parser.parse_args()
    chapters = parse_chapter_range(args.chapters)

    if args.score_opus:
        score_opus_baseline(chapters)
    elif args.compare:
        compare_results()
    elif args.condition:
        run_experiment(args.condition, chapters)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
