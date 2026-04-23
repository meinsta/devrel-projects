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

FIGURE_DPI = 150


def _setup_style(ax: plt.Axes) -> None:
    ax.set_facecolor("#FAFAFA")
    ax.grid(True, alpha=0.3, color="#E0E0E0")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)


def plot_write_throughput_over_time(
    timelines: dict[str, list[list[dict]]],
    output_path: Path,
    bin_size_s: int = 5,
) -> None:
    """Line chart: sustained write throughput over the benchmark."""
    fig, ax = plt.subplots(figsize=(12, 6))
    _setup_style(ax)

    for system, trial_timelines in timelines.items():
        all_bins: list[np.ndarray] = []
        for timeline in trial_timelines:
            writes = [e for e in timeline if e["op"] == "write" and e["success"]]
            if not writes:
                continue
            max_t = max(e["elapsed_s"] for e in writes)
            n_bins = int(max_t / bin_size_s) + 1
            counts = np.zeros(n_bins)
            for e in writes:
                b = int(e["elapsed_s"] / bin_size_s)
                if b < n_bins:
                    counts[b] += 1
            rates = counts * 100 / bin_size_s  # vectors/sec (100 per batch)
            all_bins.append(rates)

        if not all_bins:
            continue

        min_len = min(len(b) for b in all_bins)
        stacked = np.array([b[:min_len] for b in all_bins])
        median = np.median(stacked, axis=0)
        low = np.min(stacked, axis=0)
        high = np.max(stacked, axis=0)

        x = np.arange(min_len) * bin_size_s
        ax.plot(x, median, color=COLORS[system], label=LABELS[system], linewidth=2)
        ax.fill_between(x, low, high, color=COLORS[system], alpha=0.15)

    ax.set_xlabel("Time (seconds)")
    ax.set_ylabel("Write throughput (vectors/sec)")
    ax.set_title("Sustained Write Throughput During 70/30 Workload")
    ax.legend()
    fig.tight_layout()
    fig.savefig(output_path, dpi=FIGURE_DPI)
    plt.close(fig)


def plot_read_latency_cdf(
    timelines: dict[str, list[list[dict]]],
    output_path: Path,
) -> None:
    """CDF plot: read latency distribution during writes."""
    fig, ax = plt.subplots(figsize=(12, 6))
    _setup_style(ax)

    for system, trial_timelines in timelines.items():
        all_latencies: list[float] = []
        for timeline in trial_timelines:
            reads = [e for e in timeline if e["op"] == "read" and e["success"]]
            all_latencies.extend(e["latency_us"] / 1000.0 for e in reads)

        if not all_latencies:
            continue

        sorted_lat = np.sort(all_latencies)
        percentiles = np.arange(1, len(sorted_lat) + 1) / len(sorted_lat) * 100

        ax.plot(
            sorted_lat, percentiles,
            color=COLORS[system], label=LABELS[system], linewidth=2,
        )

    ax.set_xscale("log")
    ax.set_xlabel("Read latency (ms)")
    ax.set_ylabel("Percentile")
    ax.set_title("Read Latency CDF During 70/30 Write-Heavy Workload")
    for p in [50, 95, 99, 99.9]:
        ax.axhline(y=p, color="gray", linestyle=":", alpha=0.3, linewidth=0.5)
        ax.text(ax.get_xlim()[0], p, f"  p{p}", fontsize=8, color="gray", va="bottom")
    ax.legend()
    fig.tight_layout()
    fig.savefig(output_path, dpi=FIGURE_DPI)
    plt.close(fig)


def plot_read_latency_vs_write_load(
    timelines: dict[str, list[list[dict]]],
    output_path: Path,
    time_bins: int = 30,
) -> None:
    """How read latency changes as more data is written."""
    fig, ax = plt.subplots(figsize=(12, 6))
    _setup_style(ax)

    linestyles = {"p50": "-", "p95": "--", "p99": ":"}

    for system, trial_timelines in timelines.items():
        all_reads: list[dict] = []
        for timeline in trial_timelines:
            all_reads.extend(e for e in timeline if e["op"] == "read" and e["success"])

        if not all_reads:
            continue

        max_t = max(e["elapsed_s"] for e in all_reads)
        bin_edges = np.linspace(0, max_t, time_bins + 1)

        for pname, pval in [("p50", 50), ("p95", 95), ("p99", 99)]:
            bin_percentiles: list[float] = []
            bin_centers: list[float] = []
            for i in range(time_bins):
                in_bin = [
                    e["latency_us"] / 1000.0
                    for e in all_reads
                    if bin_edges[i] <= e["elapsed_s"] < bin_edges[i + 1]
                ]
                if in_bin:
                    bin_percentiles.append(float(np.percentile(in_bin, pval)))
                    bin_centers.append((bin_edges[i] + bin_edges[i + 1]) / 2)

            if bin_centers:
                ax.plot(
                    bin_centers, bin_percentiles,
                    color=COLORS[system], linestyle=linestyles[pname],
                    label=f"{LABELS[system]} {pname}", linewidth=1.5,
                )

    ax.set_xlabel("Time (seconds)")
    ax.set_ylabel("Read latency (ms)")
    ax.set_title("Read Latency Over Time (Does It Degrade as Data Grows?)")
    ax.legend(fontsize=8, ncol=3)
    fig.tight_layout()
    fig.savefig(output_path, dpi=FIGURE_DPI)
    plt.close(fig)


def plot_freshness_cdf(
    timelines: dict[str, list[list[dict]]],
    output_path: Path,
) -> None:
    """CDF of freshness latency : how long until new data is searchable."""
    fig, ax = plt.subplots(figsize=(12, 6))
    _setup_style(ax)

    for system, trial_timelines in timelines.items():
        all_latencies: list[float] = []
        for timeline in trial_timelines:
            probes = [e for e in timeline if e["op"] == "freshness" and e["success"]]
            all_latencies.extend(e["latency_us"] / 1000.0 for e in probes)

        if not all_latencies:
            continue

        sorted_lat = np.sort(all_latencies)
        percentiles = np.arange(1, len(sorted_lat) + 1) / len(sorted_lat) * 100

        ax.plot(
            sorted_lat, percentiles,
            color=COLORS[system], label=LABELS[system], linewidth=2,
        )

    ax.axvline(x=1000, color="red", linestyle="--", alpha=0.5, linewidth=1)
    ax.text(1050, 50, "1s threshold", color="red", fontsize=9, alpha=0.7)
    ax.set_xlabel("Freshness latency (ms)")
    ax.set_ylabel("Percentile")
    ax.set_title("Data Freshness: Time From Upsert to Searchable")
    ax.legend()
    fig.tight_layout()
    fig.savefig(output_path, dpi=FIGURE_DPI)
    plt.close(fig)


def plot_freshness_over_time(
    timelines: dict[str, list[list[dict]]],
    output_path: Path,
) -> None:
    """Scatter: does freshness degrade as database grows?"""
    fig, ax = plt.subplots(figsize=(12, 6))
    _setup_style(ax)

    for system, trial_timelines in timelines.items():
        xs: list[float] = []
        ys: list[float] = []
        for timeline in trial_timelines:
            probes = [e for e in timeline if e["op"] == "freshness"]
            for e in probes:
                xs.append(e["elapsed_s"])
                ys.append(e["latency_us"] / 1000.0)

        if xs:
            ax.scatter(
                xs, ys,
                color=COLORS[system], alpha=0.3, s=10,
                label=LABELS[system],
            )

            # Rolling median
            if len(xs) > 30:
                order = np.argsort(xs)
                xs_sorted = np.array(xs)[order]
                ys_sorted = np.array(ys)[order]
                window = 30
                rolling = np.convolve(ys_sorted, np.ones(window) / window, mode="valid")
                ax.plot(
                    xs_sorted[window - 1 :], rolling,
                    color=COLORS[system], linewidth=2, alpha=0.8,
                )

    ax.set_xlabel("Time (seconds)")
    ax.set_ylabel("Freshness latency (ms)")
    ax.set_title("Freshness Over Time: Does It Degrade Under Sustained Writes?")
    ax.legend()
    fig.tight_layout()
    fig.savefig(output_path, dpi=FIGURE_DPI)
    plt.close(fig)


def plot_trial_reliability(
    system_p99s: dict[str, list[float]],
    output_path: Path,
) -> None:
    """Box plot: p99 read latency across trials : shows consistency."""
    fig, ax = plt.subplots(figsize=(10, 6))
    _setup_style(ax)

    systems = list(system_p99s.keys())
    data = [system_p99s[s] for s in systems]
    colors = [COLORS.get(s, "#999999") for s in systems]
    labels = [LABELS.get(s, s) for s in systems]

    bp = ax.boxplot(
        data, labels=labels, patch_artist=True, widths=0.5,
        medianprops={"color": "black", "linewidth": 2},
    )
    for patch, color in zip(bp["boxes"], colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.6)

    # Overlay individual trial points
    for i, (s, vals) in enumerate(zip(systems, data)):
        jitter = np.random.default_rng(42).uniform(-0.1, 0.1, len(vals))
        ax.scatter(
            [i + 1 + j for j in jitter], vals,
            color=COLORS.get(s, "#999999"), s=50, zorder=5, edgecolors="black",
        )

    ax.axhline(y=100, color="red", linestyle="--", alpha=0.5, linewidth=1)
    ax.text(0.5, 102, "100ms production threshold", color="red", fontsize=9, alpha=0.7)

    ax.set_ylabel("Read p99 latency (ms)")
    ax.set_title("Trial-to-Trial Reliability: p99 Read Latency Across 5 Trials")
    fig.tight_layout()
    fig.savefig(output_path, dpi=FIGURE_DPI)
    plt.close(fig)


def generate_all_charts(results_dir: Path, charts_dir: Path) -> None:
    from benchmark.analysis.aggregate import load_trial_jsons

    charts_dir.mkdir(parents=True, exist_ok=True)
    groups = load_trial_jsons(results_dir)

    # Build timeline data structures
    timelines: dict[str, list[list[dict]]] = {}
    system_p99s: dict[str, list[float]] = {}

    for system, trials in groups.items():
        timelines[system] = [t.get("timeline", []) for t in trials]
        system_p99s[system] = [
            t.get("histograms", {}).get("read_latency_us", {}).get("p99", 0.0)
            for t in trials
        ]

    plot_write_throughput_over_time(timelines, charts_dir / "01_write_throughput.png")
    plot_read_latency_cdf(timelines, charts_dir / "02_read_latency_cdf.png")
    plot_read_latency_vs_write_load(timelines, charts_dir / "03_read_vs_write.png")
    plot_freshness_cdf(timelines, charts_dir / "04_freshness_cdf.png")
    plot_freshness_over_time(timelines, charts_dir / "05_freshness_time.png")
    plot_trial_reliability(system_p99s, charts_dir / "06_trial_reliability.png")
