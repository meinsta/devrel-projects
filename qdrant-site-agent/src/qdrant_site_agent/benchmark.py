"""Benchmark existing Qdrant content to establish quality baseline."""

import json
import random
from pathlib import Path

from rich.console import Console

from qdrant_site_agent.eval import _call_llm, _collect_files, _parse_frontmatter, EVAL_PROMPT

console = Console()

DEFAULT_SITE_DIR = "/Users/thierrydamiba/landing_page/qdrant-landing/content"

BENCHMARK_DIRS = ["blog", "articles"]


def run_benchmark(site_dir: str | None, model: str, sample: int):
    """Score existing Qdrant content to establish the quality baseline."""
    base = Path(site_dir or DEFAULT_SITE_DIR)
    if not base.exists():
        console.print(f"[red]Content dir not found: {base}[/red]")
        return

    # Collect blog + article posts
    all_files = []
    for d in BENCHMARK_DIRS:
        target = base / d
        if target.exists():
            files = [f for f in _collect_files(str(target)) if f.stat().st_size > 500]
            all_files.extend(files)

    if not all_files:
        console.print("[red]No content files found[/red]")
        return

    # Sample
    if len(all_files) > sample:
        selected = random.sample(all_files, sample)
    else:
        selected = all_files

    console.print(f"[cyan]Benchmarking {len(selected)} posts from {len(all_files)} total[/cyan]\n")

    results = []
    for f in selected:
        text = f.read_text()
        fm, body = _parse_frontmatter(text)
        if not body.strip():
            continue

        title = fm.get("title", f.stem)
        console.print(f"  Scoring: [bold]{title}[/bold]")

        try:
            result = _call_llm(EVAL_PROMPT.format(content=text), model)
            result["file"] = str(f.relative_to(base))
            result["title"] = title
            results.append(result)
        except Exception as e:
            console.print(f"  [red]Error: {e}[/red]")

    if not results:
        return

    # Compute baseline stats
    scores_by_dim = {}
    for r in results:
        for dim, val in r["scores"].items():
            scores_by_dim.setdefault(dim, []).append(val)

    console.print("\n[bold cyan]═══ Qdrant Content Baseline ═══[/bold cyan]\n")

    for dim, vals in scores_by_dim.items():
        avg = sum(vals) / len(vals)
        bar = "█" * int(avg) + "░" * (10 - int(avg))
        console.print(f"  {dim:<20} {bar} {avg:.1f}/10")

    overall_avg = sum(r["overall"] for r in results) / len(results)
    console.print(f"\n  [bold]Overall baseline: {overall_avg:.1f}/10[/bold]")

    # Grade distribution
    grades = {}
    for r in results:
        g = r["grade"][0]  # A, B, C, etc.
        grades[g] = grades.get(g, 0) + 1
    console.print(f"  Grade distribution: {dict(sorted(grades.items()))}")

    # Common strengths/weaknesses
    all_strengths = []
    all_weaknesses = []
    for r in results:
        all_strengths.extend(r.get("strengths", []))
        all_weaknesses.extend(r.get("weaknesses", []))

    console.print("\n  [green]Top strengths:[/green]")
    for s in _top_n(all_strengths, 3):
        console.print(f"    • {s}")

    console.print("\n  [yellow]Top weaknesses:[/yellow]")
    for w in _top_n(all_weaknesses, 3):
        console.print(f"    • {w}")

    # Save
    out = Path("eval_runs")
    out.mkdir(exist_ok=True)
    baseline = {
        "sample_size": len(results),
        "overall_baseline": overall_avg,
        "dimension_baselines": {d: sum(v) / len(v) for d, v in scores_by_dim.items()},
        "grade_distribution": grades,
        "results": results,
    }
    outfile = out / "baseline.json"
    outfile.write_text(json.dumps(baseline, indent=2))
    console.print(f"\n[dim]Baseline saved to {outfile}[/dim]")


def _top_n(items: list[str], n: int) -> list[str]:
    """Return top N most common items."""
    counts: dict[str, int] = {}
    for item in items:
        # Normalize
        key = item.lower().strip().rstrip(".")
        counts[key] = counts.get(key, 0) + 1
    return [k for k, _ in sorted(counts.items(), key=lambda x: -x[1])[:n]]
