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


def _fmt(val: float, precision: int = 1) -> str:
    return f"{val:.{precision}f}"


def _fmt_range(median: float, low: float, high: float) -> str:
    return f"{_fmt(median)} ({_fmt(low)}-{_fmt(high)})"


def _bold_best(values: dict[str, float], lower_is_better: bool = True) -> dict[str, str]:
    """Return formatted strings with the best value bolded."""
    if not values:
        return {}
    best_val = min(values.values()) if lower_is_better else max(values.values())
    result = {}
    for k, v in values.items():
        s = _fmt(v)
        if v == best_val:
            s = f"**{s}**"
        result[k] = s
    return result


def generate_report(
    results_dir: Path,
    output_path: Path | None = None,
) -> str:
    if output_path is None:
        output_path = results_dir / "REPORT.md"

    groups = load_trial_jsons(results_dir)
    if not groups:
        return "No results found."

    # Compute stats
    all_stats = {}
    all_pass = {}
    for system, trials in groups.items():
        all_stats[system] = compute_cross_trial_stats(system, trials)
        all_pass[system] = compute_pass_at_k(trials)

    # Generate charts
    charts_dir = results_dir / "charts"
    generate_all_charts(results_dir, charts_dir)

    # Load metadata
    meta_path = results_dir / "run_metadata.json"
    metadata = {}
    if meta_path.exists():
        with open(meta_path) as f:
            metadata = json.load(f)

    params = metadata.get("parameters", {})
    systems = list(groups.keys())

    # Build report
    lines: list[str] = []
    lines.append("# Write-Heavy Benchmark Results\n")

    lines.append(f"**Dataset:** SIFT-1M (128-dim, 1M vectors, Euclidean)")
    lines.append(
        f"**Workload:** {params.get('target_ops_per_sec', '?')}/s, "
        f"{params.get('write_ratio', 0.7)*100:.0f}% writes / "
        f"{params.get('read_ratio', 0.3)*100:.0f}% reads, "
        f"{params.get('duration_s', '?')}s duration"
    )
    lines.append(f"**Trials:** {params.get('trials', '?')} per system\n")

    # Summary table
    lines.append("## Summary\n")
    lines.append("| Metric | " + " | ".join(LABELS.get(s, s) for s in systems) + " |")
    lines.append("|--------|" + "|".join("--------" for _ in systems) + "|")

    rows = [
        ("Write throughput (vec/sec)", "write_throughput", True, False),
        ("Read p50 (ms)", "read_p50", True, True),
        ("Read p99 (ms)", "read_p99", True, True),
        ("Read p99.9 (ms)", "read_p999", True, True),
        ("Freshness p50 (ms)", "freshness_p50", True, True),
        ("Freshness p99 (ms)", "freshness_p99", True, True),
        ("% searchable < 1s", "pct_searchable_under_1s", False, False),
        ("Write success rate (%)", "write_success_rate", False, False),
        ("Read success rate (%)", "read_success_rate", False, False),
        ("p99 trial variance (ms)", "p99_trial_variance", False, True),
    ]

    for label, key_prefix, has_range, lower_better in rows:
        cells = []
        for s in systems:
            st = all_stats[s]
            if has_range:
                med = getattr(st, f"{key_prefix}_median")
                lo = getattr(st, f"{key_prefix}_min")
                hi = getattr(st, f"{key_prefix}_max")
                cells.append(_fmt_range(med, lo, hi))
            elif key_prefix == "p99_trial_variance":
                cells.append(_fmt(st.p99_trial_variance))
            else:
                val = getattr(st, f"{key_prefix}_median")
                cells.append(_fmt(val))
        lines.append(f"| {label} | " + " | ".join(cells) + " |")

    lines.append("")

    # Production readiness
    lines.append("## Production Readiness (p99 < 100ms under load)\n")
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
        "*pass@k = at least one trial meets threshold in k attempts (capability). "
        "pass^k = all k trials meet threshold (reliability).*\n"
    )

    # Charts
    lines.append("## Charts\n")
    chart_names = [
        ("01_write_throughput.png", "Write Throughput Over Time"),
        ("02_read_latency_cdf.png", "Read Latency CDF During Writes"),
        ("03_read_vs_write.png", "Read Latency vs Write Load"),
        ("04_freshness_cdf.png", "Freshness Latency Distribution"),
        ("05_freshness_time.png", "Freshness Over Time"),
        ("06_trial_reliability.png", "Trial-to-Trial Reliability"),
    ]
    for fname, title in chart_names:
        lines.append(f"### {title}\n")
        lines.append(f"![{title}](charts/{fname})\n")

    # Per-system detail
    lines.append("## Per-System Detail\n")
    for s in systems:
        st = all_stats[s]
        lines.append(f"### {LABELS.get(s, s)}\n")
        lines.append(f"- Write throughput: {_fmt(st.write_throughput_median)} vec/s "
                      f"(range: {_fmt(st.write_throughput_min)}-{_fmt(st.write_throughput_max)})")
        lines.append(f"- Read p99: {_fmt(st.read_p99_median)}ms "
                      f"(range: {_fmt(st.read_p99_min)}-{_fmt(st.read_p99_max)})")
        lines.append(f"- Freshness p50: {_fmt(st.freshness_p50_median)}ms")
        lines.append(f"- Write success: {_fmt(st.write_success_rate_median)}%")
        lines.append(f"- Read success: {_fmt(st.read_success_rate_median)}%")

        baseline = metadata.get("systems", {}).get(s, {}).get("baseline_latency_ms")
        if baseline:
            lines.append(f"- Network baseline: {_fmt(baseline)}ms")

        lines.append("")

    # Reproduction
    lines.append("## Reproduce\n")
    lines.append("```bash")
    lines.append("git clone <repo>")
    lines.append("cd vector-db-write-bench")
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


LABELS = {
    "qdrant_cloud": "Qdrant Cloud",
    "zilliz_cloud": "Zilliz Cloud",
    "weaviate_cloud": "Weaviate Cloud",
}


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
