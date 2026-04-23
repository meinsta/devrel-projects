from __future__ import annotations

from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import numpy as np

matplotlib.use("Agg")

COLORS = {
    "qdrant_cloud": "#DC382C",
    "zilliz_cloud": "#4FC3F7",
    "weaviate_cloud": "#01D632",
}

LABELS = {
    "qdrant_cloud": "Qdrant Cloud",
    "zilliz_cloud": "Zilliz Cloud",
    "weaviate_cloud": "Weaviate Cloud",
}

LEVEL_COLORS = {
    1: "#4CAF50",
    2: "#FF9800",
    3: "#2196F3",
    4: "#9C27B0",
    5: "#F44336",
}

FIGURE_DPI = 150


def _setup_style(ax: plt.Axes) -> None:
    ax.set_facecolor("#FAFAFA")
    ax.grid(True, alpha=0.3, color="#E0E0E0")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)


def plot_filter_level_latencies(
    timelines: dict[str, list[list[dict]]],
    output_path: Path,
) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(16, 7))

    for ax_idx, (pname, pval) in enumerate([("p50", 50), ("p99", 99)]):
        ax = axes[ax_idx]
        _setup_style(ax)

        systems = list(timelines.keys())
        n_systems = len(systems)
        x = np.arange(5)  # L1-L5
        width = 0.8 / max(n_systems, 1)

        for sys_idx, system in enumerate(systems):
            level_latencies = {i: [] for i in range(1, 6)}
            for timeline in timelines[system]:
                for e in timeline:
                    if e["op"] == "filtered_search" and e["success"]:
                        level = e.get("filter_level", 0)
                        if 1 <= level <= 5:
                            level_latencies[level].append(e["latency_us"] / 1000.0)

            values = []
            for level in range(1, 6):
                lats = level_latencies[level]
                if lats:
                    values.append(float(np.percentile(lats, pval)))
                else:
                    values.append(0)

            offset = (sys_idx - n_systems / 2 + 0.5) * width
            ax.bar(
                x + offset, values, width,
                color=COLORS.get(system, "#999"),
                label=LABELS.get(system, system),
            )

        ax.set_xticks(x)
        ax.set_xticklabels([f"L{i}" for i in range(1, 6)])
        ax.set_xlabel("Filter Complexity Level")
        ax.set_ylabel(f"Latency {pname} (ms)")
        ax.set_title(f"Filtered Search {pname.upper()} by Complexity Level")
        if pname == "p99":
            ax.axhline(y=50, color="red", linestyle="--", alpha=0.5, linewidth=1)
            ax.text(0, 52, "50ms target", color="red", fontsize=9, alpha=0.7)
        ax.legend()

    fig.tight_layout()
    fig.savefig(output_path, dpi=FIGURE_DPI)
    plt.close(fig)


def plot_filtered_vs_unfiltered_cdf(
    timelines: dict[str, list[list[dict]]],
    output_path: Path,
) -> None:
    fig, ax = plt.subplots(figsize=(12, 6))
    _setup_style(ax)

    for system, trial_timelines in timelines.items():
        filtered_lats: list[float] = []
        unfiltered_lats: list[float] = []
        for timeline in trial_timelines:
            for e in timeline:
                if e["success"]:
                    lat_ms = e["latency_us"] / 1000.0
                    if e["op"] == "filtered_search":
                        filtered_lats.append(lat_ms)
                    elif e["op"] == "unfiltered_search":
                        unfiltered_lats.append(lat_ms)

        color = COLORS.get(system, "#999")
        label = LABELS.get(system, system)

        if filtered_lats:
            sorted_lat = np.sort(filtered_lats)
            pcts = np.arange(1, len(sorted_lat) + 1) / len(sorted_lat) * 100
            ax.plot(sorted_lat, pcts, color=color, label=f"{label} (filtered)", linewidth=2)

        if unfiltered_lats:
            sorted_lat = np.sort(unfiltered_lats)
            pcts = np.arange(1, len(sorted_lat) + 1) / len(sorted_lat) * 100
            ax.plot(sorted_lat, pcts, color=color, label=f"{label} (unfiltered)",
                    linewidth=2, linestyle="--")

    ax.set_xscale("log")
    ax.set_xlabel("Latency (ms)")
    ax.set_ylabel("Percentile")
    ax.set_title("Filtered vs Unfiltered Search Latency Distribution Under Load")
    for p in [50, 95, 99, 99.9]:
        ax.axhline(y=p, color="gray", linestyle=":", alpha=0.3, linewidth=0.5)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(output_path, dpi=FIGURE_DPI)
    plt.close(fig)


def plot_filter_overhead(
    timelines: dict[str, list[list[dict]]],
    output_path: Path,
) -> None:
    fig, ax = plt.subplots(figsize=(10, 6))
    _setup_style(ax)

    systems = list(timelines.keys())
    overheads = []
    colors = []

    for system in systems:
        filtered_lats: list[float] = []
        unfiltered_lats: list[float] = []
        for timeline in timelines[system]:
            for e in timeline:
                if e["success"]:
                    lat_ms = e["latency_us"] / 1000.0
                    if e["op"] == "filtered_search":
                        filtered_lats.append(lat_ms)
                    elif e["op"] == "unfiltered_search":
                        unfiltered_lats.append(lat_ms)

        fp99 = float(np.percentile(filtered_lats, 99)) if filtered_lats else 0
        up99 = float(np.percentile(unfiltered_lats, 99)) if unfiltered_lats else 1
        overheads.append(fp99 / max(up99, 0.001))
        colors.append(COLORS.get(system, "#999"))

    bars = ax.bar(
        [LABELS.get(s, s) for s in systems],
        overheads,
        color=colors,
    )
    ax.axhline(y=1.0, color="gray", linestyle="--", alpha=0.5)
    ax.set_ylabel("Filter Overhead Ratio (filtered p99 / unfiltered p99)")
    ax.set_title("Cost of Filtering: How Much Overhead Does Filtering Add?")

    for bar, val in zip(bars, overheads):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.05,
                f"{val:.2f}x", ha="center", fontsize=11, fontweight="bold")

    fig.tight_layout()
    fig.savefig(output_path, dpi=FIGURE_DPI)
    plt.close(fig)


def plot_latency_over_time(
    timelines: dict[str, list[list[dict]]],
    output_path: Path,
    time_bins: int = 30,
) -> None:
    fig, ax = plt.subplots(figsize=(12, 6))
    _setup_style(ax)

    linestyles = {"p50": "-", "p95": "--", "p99": ":"}

    for system, trial_timelines in timelines.items():
        all_reads: list[dict] = []
        for timeline in trial_timelines:
            all_reads.extend(e for e in timeline if e["op"] == "filtered_search" and e["success"])

        if not all_reads:
            continue

        max_t = max(e["elapsed_s"] for e in all_reads)
        bin_edges = np.linspace(0, max_t, time_bins + 1)

        for pname, pval in [("p50", 50), ("p95", 95), ("p99", 99)]:
            bin_pcts: list[float] = []
            bin_centers: list[float] = []
            for i in range(time_bins):
                in_bin = [
                    e["latency_us"] / 1000.0
                    for e in all_reads
                    if bin_edges[i] <= e["elapsed_s"] < bin_edges[i + 1]
                ]
                if in_bin:
                    bin_pcts.append(float(np.percentile(in_bin, pval)))
                    bin_centers.append((bin_edges[i] + bin_edges[i + 1]) / 2)

            if bin_centers:
                ax.plot(
                    bin_centers, bin_pcts,
                    color=COLORS.get(system, "#999"), linestyle=linestyles[pname],
                    label=f"{LABELS.get(system, system)} {pname}", linewidth=1.5,
                )

    ax.axhline(y=50, color="red", linestyle="--", alpha=0.5, linewidth=1)
    ax.text(0, 52, "50ms target", color="red", fontsize=9, alpha=0.7)
    ax.set_xlabel("Time (seconds)")
    ax.set_ylabel("Filtered search latency (ms)")
    ax.set_title("Filtered Search Latency Over Time (Does It Degrade Under Load?)")
    ax.legend(fontsize=8, ncol=3)
    fig.tight_layout()
    fig.savefig(output_path, dpi=FIGURE_DPI)
    plt.close(fig)


def plot_level_latency_over_time(
    timelines: dict[str, list[list[dict]]],
    output_path: Path,
    system: str | None = None,
    time_bins: int = 20,
) -> None:
    fig, ax = plt.subplots(figsize=(12, 6))
    _setup_style(ax)

    if system is None:
        system = next(iter(timelines.keys()), None)
    if system is None:
        plt.close(fig)
        return

    trial_timelines = timelines.get(system, [])
    all_filtered: list[dict] = []
    for timeline in trial_timelines:
        all_filtered.extend(e for e in timeline if e["op"] == "filtered_search" and e["success"])

    if not all_filtered:
        plt.close(fig)
        return

    max_t = max(e["elapsed_s"] for e in all_filtered)
    bin_edges = np.linspace(0, max_t, time_bins + 1)

    for level in range(1, 6):
        level_entries = [e for e in all_filtered if e.get("filter_level") == level]
        if not level_entries:
            continue

        bin_p99s: list[float] = []
        bin_centers: list[float] = []
        for i in range(time_bins):
            in_bin = [
                e["latency_us"] / 1000.0
                for e in level_entries
                if bin_edges[i] <= e["elapsed_s"] < bin_edges[i + 1]
            ]
            if len(in_bin) >= 5:
                bin_p99s.append(float(np.percentile(in_bin, 99)))
                bin_centers.append((bin_edges[i] + bin_edges[i + 1]) / 2)

        if bin_centers:
            ax.plot(
                bin_centers, bin_p99s,
                color=LEVEL_COLORS[level],
                label=f"L{level} p99", linewidth=2,
            )

    ax.axhline(y=50, color="red", linestyle="--", alpha=0.5, linewidth=1)
    ax.set_xlabel("Time (seconds)")
    ax.set_ylabel("p99 Latency (ms)")
    ax.set_title(f"Per-Level Filter Latency Over Time: {LABELS.get(system, system)}")
    ax.legend()
    fig.tight_layout()
    fig.savefig(output_path, dpi=FIGURE_DPI)
    plt.close(fig)


def plot_update_throughput(
    timelines: dict[str, list[list[dict]]],
    output_path: Path,
    bin_size_s: int = 5,
) -> None:
    fig, ax = plt.subplots(figsize=(12, 6))
    _setup_style(ax)

    for system, trial_timelines in timelines.items():
        all_bins: list[np.ndarray] = []
        for timeline in trial_timelines:
            updates = [e for e in timeline if e["op"] == "update" and e["success"]]
            if not updates:
                continue
            max_t = max(e["elapsed_s"] for e in updates)
            n_bins = int(max_t / bin_size_s) + 1
            counts = np.zeros(n_bins)
            for e in updates:
                b = int(e["elapsed_s"] / bin_size_s)
                if b < n_bins:
                    counts[b] += 1
            rates = counts / bin_size_s
            all_bins.append(rates)

        if not all_bins:
            continue

        min_len = min(len(b) for b in all_bins)
        stacked = np.array([b[:min_len] for b in all_bins])
        median = np.median(stacked, axis=0)

        x = np.arange(min_len) * bin_size_s
        ax.plot(x, median, color=COLORS.get(system, "#999"),
                label=LABELS.get(system, system), linewidth=2)

    ax.set_xlabel("Time (seconds)")
    ax.set_ylabel("Update throughput (ops/sec)")
    ax.set_title("Metadata Update Throughput During Filtered Search Load")
    ax.legend()
    fig.tight_layout()
    fig.savefig(output_path, dpi=FIGURE_DPI)
    plt.close(fig)


def plot_result_count_distribution(
    timelines: dict[str, list[list[dict]]],
    output_path: Path,
) -> None:
    fig, ax = plt.subplots(figsize=(12, 6))
    _setup_style(ax)

    for system, trial_timelines in timelines.items():
        counts: list[int] = []
        for timeline in trial_timelines:
            for e in timeline:
                if e["op"] == "filtered_search" and e["success"]:
                    counts.append(e.get("result_count", 0))

        if counts:
            ax.hist(
                counts, bins=50, alpha=0.5, density=True,
                color=COLORS.get(system, "#999"),
                label=LABELS.get(system, system),
            )

    ax.axvline(x=50, color="red", linestyle="--", alpha=0.7, linewidth=1.5)
    ax.text(51, ax.get_ylim()[1] * 0.9, "requested top_k=50", color="red", fontsize=9)
    ax.set_xlabel("Number of results returned")
    ax.set_ylabel("Density")
    ax.set_title("Result Count Accuracy: Does Filtering Return Expected Results?")
    ax.legend()
    fig.tight_layout()
    fig.savefig(output_path, dpi=FIGURE_DPI)
    plt.close(fig)


def plot_trial_reliability(
    system_p99s: dict[str, list[float]],
    output_path: Path,
) -> None:
    fig, ax = plt.subplots(figsize=(10, 6))
    _setup_style(ax)

    systems = list(system_p99s.keys())
    data = [system_p99s[s] for s in systems]
    colors = [COLORS.get(s, "#999") for s in systems]
    labels = [LABELS.get(s, s) for s in systems]

    bp = ax.boxplot(
        data, labels=labels, patch_artist=True, widths=0.5,
        medianprops={"color": "black", "linewidth": 2},
    )
    for patch, color in zip(bp["boxes"], colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.6)

    for i, (s, vals) in enumerate(zip(systems, data)):
        jitter = np.random.default_rng(42).uniform(-0.1, 0.1, len(vals))
        ax.scatter(
            [i + 1 + j for j in jitter], vals,
            color=COLORS.get(s, "#999"), s=50, zorder=5, edgecolors="black",
        )

    ax.axhline(y=50, color="red", linestyle="--", alpha=0.5, linewidth=1)
    ax.text(0.5, 52, "50ms p99 target", color="red", fontsize=9, alpha=0.7)

    ax.set_ylabel("Filtered search p99 latency (ms)")
    ax.set_title("Trial-to-Trial Reliability: Filtered Search p99 Across Trials")
    fig.tight_layout()
    fig.savefig(output_path, dpi=FIGURE_DPI)
    plt.close(fig)


def generate_all_charts(results_dir: Path, charts_dir: Path) -> None:
    from benchmark.analysis.aggregate import load_trial_jsons

    charts_dir.mkdir(parents=True, exist_ok=True)
    groups = load_trial_jsons(results_dir)

    timelines: dict[str, list[list[dict]]] = {}
    system_p99s: dict[str, list[float]] = {}

    for system, trials in groups.items():
        timelines[system] = [t.get("timeline", []) for t in trials]
        system_p99s[system] = [
            t.get("histograms", {}).get("filtered_search_latency_us", {}).get("p99", 0.0)
            for t in trials
        ]

    plot_filter_level_latencies(timelines, charts_dir / "01_filter_level_latencies.png")
    plot_filtered_vs_unfiltered_cdf(timelines, charts_dir / "02_filtered_vs_unfiltered_cdf.png")
    plot_filter_overhead(timelines, charts_dir / "03_filter_overhead.png")
    plot_latency_over_time(timelines, charts_dir / "04_latency_over_time.png")
    plot_level_latency_over_time(timelines, charts_dir / "05_level_latency_over_time.png")
    plot_update_throughput(timelines, charts_dir / "06_update_throughput.png")
    plot_result_count_distribution(timelines, charts_dir / "07_result_count_distribution.png")
    plot_trial_reliability(system_p99s, charts_dir / "08_trial_reliability.png")
