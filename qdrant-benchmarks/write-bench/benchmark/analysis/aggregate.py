from __future__ import annotations

import json
from dataclasses import dataclass
from math import comb
from pathlib import Path

import numpy as np


@dataclass
class CrossTrialStats:
    system: str
    num_trials: int
    write_throughput_median: float
    write_throughput_min: float
    write_throughput_max: float
    read_p50_median: float
    read_p50_min: float
    read_p50_max: float
    read_p99_median: float
    read_p99_min: float
    read_p99_max: float
    read_p999_median: float
    read_p999_min: float
    read_p999_max: float
    freshness_p50_median: float
    freshness_p50_min: float
    freshness_p50_max: float
    freshness_p99_median: float
    freshness_p99_min: float
    freshness_p99_max: float
    pct_searchable_under_1s_median: float
    write_success_rate_median: float
    read_success_rate_median: float
    p99_trial_variance: float


def load_trial_jsons(results_dir: Path) -> dict[str, list[dict]]:
    """Load all *_trial_*.json files, grouped by system name."""
    groups: dict[str, list[dict]] = {}
    for path in sorted(results_dir.glob("*_trial_*.json")):
        if path.name.endswith("_docker_stats.json"):
            continue
        # e.g. "qdrant_cloud_trial_0.json" -> "qdrant_cloud"
        parts = path.stem.rsplit("_trial_", 1)
        system = parts[0]
        with open(path) as f:
            data = json.load(f)
        groups.setdefault(system, []).append(data)
    return groups


def _extract_metric(trials: list[dict], hist_name: str, percentile_key: str) -> np.ndarray:
    """Extract a specific percentile from each trial's histogram data."""
    values = []
    for trial in trials:
        hist_data = trial.get("histograms", {}).get(hist_name, {})
        values.append(hist_data.get(percentile_key, 0.0))
    return np.array(values)


def compute_cross_trial_stats(system: str, trials: list[dict]) -> CrossTrialStats:
    """Compute median, min, max across trials for all key metrics."""
    n = len(trials)

    # Write throughput: total writes / duration
    write_throughputs = []
    for t in trials:
        total_writes = t.get("counters", {}).get("write_total", 0)
        duration = t.get("metadata", {}).get("duration_s", 300)
        # Each write op inserts a batch of 100 vectors
        write_throughputs.append(total_writes * 100 / max(duration, 1))
    wt = np.array(write_throughputs)

    read_p50 = _extract_metric(trials, "read_latency_us", "p50")
    read_p99 = _extract_metric(trials, "read_latency_us", "p99")
    read_p999 = _extract_metric(trials, "read_latency_us", "p999")
    fresh_p50 = _extract_metric(trials, "freshness_latency_us", "p50")
    fresh_p99 = _extract_metric(trials, "freshness_latency_us", "p99")

    # Freshness under 1s: count timeline entries
    pct_under_1s = []
    for t in trials:
        fresh_entries = [
            e for e in t.get("timeline", [])
            if e.get("op") == "freshness"
        ]
        if fresh_entries:
            under_1s = sum(1 for e in fresh_entries if e["latency_us"] < 1_000_000 and e["success"])
            pct_under_1s.append(under_1s / len(fresh_entries) * 100)
        else:
            pct_under_1s.append(0.0)
    pct_arr = np.array(pct_under_1s)

    # Success rates
    write_success = []
    read_success = []
    for t in trials:
        c = t.get("counters", {})
        wt_total = c.get("write_total", 1)
        wt_err = c.get("write_error", 0)
        write_success.append((wt_total - wt_err) / max(wt_total, 1) * 100)
        rd_total = c.get("read_total", 1)
        rd_err = c.get("read_error", 0)
        read_success.append((rd_total - rd_err) / max(rd_total, 1) * 100)

    ws = np.array(write_success)
    rs = np.array(read_success)

    return CrossTrialStats(
        system=system,
        num_trials=n,
        write_throughput_median=float(np.median(wt)),
        write_throughput_min=float(np.min(wt)),
        write_throughput_max=float(np.max(wt)),
        read_p50_median=float(np.median(read_p50)),
        read_p50_min=float(np.min(read_p50)),
        read_p50_max=float(np.max(read_p50)),
        read_p99_median=float(np.median(read_p99)),
        read_p99_min=float(np.min(read_p99)),
        read_p99_max=float(np.max(read_p99)),
        read_p999_median=float(np.median(read_p999)),
        read_p999_min=float(np.min(read_p999)),
        read_p999_max=float(np.max(read_p999)),
        freshness_p50_median=float(np.median(fresh_p50)),
        freshness_p50_min=float(np.min(fresh_p50)),
        freshness_p50_max=float(np.max(fresh_p50)),
        freshness_p99_median=float(np.median(fresh_p99)),
        freshness_p99_min=float(np.min(fresh_p99)),
        freshness_p99_max=float(np.max(fresh_p99)),
        pct_searchable_under_1s_median=float(np.median(pct_arr)),
        write_success_rate_median=float(np.median(ws)),
        read_success_rate_median=float(np.median(rs)),
        p99_trial_variance=float(np.max(read_p99) - np.min(read_p99)),
    )


def compute_pass_at_k(
    trials: list[dict],
    threshold_ms: float = 100.0,
) -> dict[str, float]:
    """
    pass@k: probability of at least one success in k trials.
    pass^k: probability all k trials succeed.
    Threshold: read p99 < threshold_ms during sustained writes.
    """
    n = len(trials)
    successes = sum(
        1
        for t in trials
        if t.get("histograms", {})
        .get("read_latency_us", {})
        .get("p99", float("inf"))
        < threshold_ms
    )

    result: dict[str, float] = {}
    for k in [1, 3, 5]:
        if k > n:
            continue
        # pass@k = 1 - C(n-s, k) / C(n, k)
        if successes >= k:
            pass_at_k = 1.0 - comb(n - successes, k) / max(comb(n, k), 1)
        else:
            pass_at_k = 0.0
        # pass^k = (s/n)^k
        pass_pow_k = (successes / max(n, 1)) ** k

        result[f"pass_at_{k}"] = round(pass_at_k, 3)
        result[f"pass_pow_{k}"] = round(pass_pow_k, 3)

    return result
