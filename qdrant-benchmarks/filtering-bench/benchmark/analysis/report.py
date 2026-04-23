from __future__ import annotations

import json
import logging
from dataclasses import asdict
from pathlib import Path

import click

from benchmark.analysis.aggregate import (
    compute_cross_trial_stats,
    compute_pass_at_k,
    load_trial_jsons,
)
from benchmark.analysis.plots import generate_all_charts

log = logging.getLogger(__name__)

LABELS = {
    "qdrant_cloud": "Qdrant Cloud",
    "zilliz_cloud": "Zilliz Cloud",
    "weaviate_cloud": "Weaviate Cloud",
}


def _fmt(val: float, precision: int = 1) -> str:
    return f"{val:.{precision}f}"


def _fmt_range(median: float, low: float, high: float) -> str:
    return f"{_fmt(median)} ({_fmt(low)}-{_fmt(high)})"


def generate_report(
    results_dir: Path,
    output_path: Path | None = None,
) -> str:
    if output_path is None:
        output_path = results_dir / "REPORT.md"

    groups = load_trial_jsons(results_dir)
    if not groups:
        return "No results found."

    all_stats = {}
    all_pass = {}
    for system, trials in groups.items():
        all_stats[system] = compute_cross_trial_stats(system, trials)
        all_pass[system] = compute_pass_at_k(trials)

    charts_dir = results_dir / "charts"
    generate_all_charts(results_dir, charts_dir)

    meta_path = results_dir / "run_metadata.json"
    metadata = {}
    if meta_path.exists():
        with open(meta_path) as f:
            metadata = json.load(f)

    params = metadata.get("parameters", {})
    systems = list(groups.keys())

    lines: list[str] = []
    lines.append("# Filtering Performance Under Load: Benchmark Results\n")

    lines.append(f"**Dataset:** SIFT-1M (128-dim, 1M vectors, Euclidean)")
    lines.append(
        f"**Workload:** {params.get('target_ops_per_sec', '?')}/s, "
        f"{params.get('filtered_search_ratio', 0.6)*100:.0f}% filtered / "
        f"{params.get('unfiltered_search_ratio', 0.1)*100:.0f}% unfiltered / "
        f"{params.get('update_ratio', 0.3)*100:.0f}% updates, "
        f"{params.get('duration_s', '?')}s duration"
    )
    lines.append(f"**Trials:** {params.get('trials', '?')} per system")
    lines.append(f"**Top-K:** {params.get('read_top_k', 50)} results requested per query\n")

    # Summary table
    lines.append("## Summary\n")
    lines.append("| Metric | " + " | ".join(LABELS.get(s, s) for s in systems) + " |")
    lines.append("|--------|" + "|".join("--------" for _ in systems) + "|")

    rows = [
        ("Filtered p50 (ms)", "filtered_p50", True),
        ("Filtered p99 (ms)", "filtered_p99", True),
        ("Filtered p99.9 (ms)", "filtered_p999", False),
        ("Unfiltered p50 (ms)", "unfiltered_p50", False),
        ("Unfiltered p99 (ms)", "unfiltered_p99", False),
        ("Update p99 (ms)", "update_p99", False),
        ("Filter overhead ratio", "filter_overhead_ratio", False),
    ]

    for label, key, has_range in rows:
        cells = []
        for s in systems:
            st = all_stats[s]
            if has_range:
                med = getattr(st, f"{key}_median")
                lo = getattr(st, f"{key}_min")
                hi = getattr(st, f"{key}_max")
                cells.append(_fmt_range(med, lo, hi))
            elif key == "filter_overhead_ratio":
                cells.append(f"{st.filter_overhead_ratio}x")
            else:
                val = getattr(st, f"{key}_median")
                cells.append(_fmt(val))
        lines.append(f"| {label} | " + " | ".join(cells) + " |")

    lines.append("")

    # Per-level breakdown
    lines.append("## Filter Complexity Breakdown (p99 ms)\n")
    lines.append("| Level | Description | " + " | ".join(LABELS.get(s, s) for s in systems) + " |")
    lines.append("|-------|-------------|" + "|".join("--------" for _ in systems) + "|")

    level_desc = {
        1: "Single tenant (~2%)",
        2: "Tenant + region (~0.2%)",
        3: "Multi-field (~0.004%)",
        4: "Full hierarchy (~0.0004%)",
        5: "Hierarchy + range (~0.0001%)",
    }

    for level in range(1, 6):
        cells = []
        for s in systems:
            st = all_stats[s]
            val = getattr(st, f"filter_l{level}_p99_median")
            cells.append(_fmt(val))
        lines.append(f"| L{level} | {level_desc[level]} | " + " | ".join(cells) + " |")

    lines.append("")

    # Production readiness
    lines.append("## Production Readiness (filtered p99 < 50ms under load)\n")
    lines.append("| System | pass@1 | pass@5 | pass^1 | pass^5 |")
    lines.append("|--------|--------|--------|--------|--------|")
    for s in systems:
        p = all_pass[s]
        lines.append(
            f"| {LABELS.get(s, s)} | "
            f"{p.get('pass_at_1', '-')} | {p.get('pass_at_5', '-')} | "
            f"{p.get('pass_pow_1', '-')} | {p.get('pass_pow_5', '-')} |"
        )
    lines.append("")
    lines.append(
        "*pass@k = at least one trial meets threshold in k attempts. "
        "pass^k = all k trials meet threshold. "
        "Threshold: filtered search p99 < 50ms (adMarketplace requirement).*\n"
    )

    # Success rates
    lines.append("## Success Rates\n")
    lines.append("| System | Filtered Search | Unfiltered Search | Updates |")
    lines.append("|--------|-----------------|-------------------|---------|")
    for s in systems:
        st = all_stats[s]
        lines.append(
            f"| {LABELS.get(s, s)} | "
            f"{_fmt(st.filtered_search_success_rate)}% | "
            f"{_fmt(st.unfiltered_search_success_rate)}% | "
            f"{_fmt(st.update_success_rate)}% |"
        )
    lines.append("")

    # Charts
    lines.append("## Charts\n")
    chart_names = [
        ("01_filter_level_latencies.png", "Latency by Filter Complexity Level"),
        ("02_filtered_vs_unfiltered_cdf.png", "Filtered vs Unfiltered Latency CDF"),
        ("03_filter_overhead.png", "Filter Overhead Ratio"),
        ("04_latency_over_time.png", "Filtered Search Latency Over Time"),
        ("05_level_latency_over_time.png", "Per-Level Latency Over Time"),
        ("06_update_throughput.png", "Update Throughput During Load"),
        ("07_result_count_distribution.png", "Result Count Accuracy"),
        ("08_trial_reliability.png", "Trial-to-Trial Reliability"),
    ]
    for fname, title in chart_names:
        lines.append(f"### {title}\n")
        lines.append(f"![{title}](charts/{fname})\n")

    # Reproduction
    lines.append("## Reproduce\n")
    lines.append("```bash")
    lines.append("git clone <repo>")
    lines.append("cd vector-db-filter-bench")
    lines.append("cp .env.example .env  # fill in cloud credentials")
    lines.append("uv sync")
    lines.append("python -m benchmark.harness.runner --system all --trials 5")
    lines.append("python -m benchmark.analysis.report results/")
    lines.append("```\n")

    report = "\n".join(lines)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        f.write(report)

    log.info(f"Report written to {output_path}")
    return report


@click.command()
@click.argument("results_dir", type=click.Path(exists=True))
@click.option("--output", "-o", default=None, help="Output path for report")
def main(results_dir: str, output: str | None) -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    out = Path(output) if output else None
    report = generate_report(Path(results_dir), out)
    print(report)


if __name__ == "__main__":
    main()
