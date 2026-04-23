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
    # Filtered search latencies
    filtered_p50_median: float
    filtered_p50_min: float
    filtered_p50_max: float
    filtered_p99_median: float
    filtered_p99_min: float
    filtered_p99_max: float
    filtered_p999_median: float
    # Unfiltered search latencies
    unfiltered_p50_median: float
    unfiltered_p99_median: float
    # Per filter level p99
    filter_l1_p99_median: float
    filter_l2_p99_median: float
    filter_l3_p99_median: float
    filter_l4_p99_median: float
    filter_l5_p99_median: float
    # Update latencies
    update_p99_median: float
    # Success rates
    filtered_search_success_rate: float
    unfiltered_search_success_rate: float
    update_success_rate: float
    # Filter overhead: ratio of filtered_p99 / unfiltered_p99
    filter_overhead_ratio: float
    # Trial variance
    p99_trial_variance: float


def load_trial_jsons(results_dir: Path) -> dict[str, list[dict]]:
    groups: dict[str, list[dict]] = {}
    for path in sorted(results_dir.glob("*_trial_*.json")):
        parts = path.stem.rsplit("_trial_", 1)
        system = parts[0]
        with open(path) as f:
            data = json.load(f)
        groups.setdefault(system, []).append(data)
    return groups


def _extract_metric(trials: list[dict], hist_name: str, percentile_key: str) -> np.ndarray:
    values = []
    for trial in trials:
        hist_data = trial.get("histograms", {}).get(hist_name, {})
        values.append(hist_data.get(percentile_key, 0.0))
    return np.array(values)


def _success_rate(trials: list[dict], total_key: str, error_key: str) -> float:
    rates = []
    for t in trials:
        c = t.get("counters", {})
        total = c.get(total_key, 1)
        errors = c.get(error_key, 0)
        rates.append((total - errors) / max(total, 1) * 100)
    return float(np.median(rates))


def compute_cross_trial_stats(system: str, trials: list[dict]) -> CrossTrialStats:
    n = len(trials)

    fp50 = _extract_metric(trials, "filtered_search_latency_us", "p50")
    fp99 = _extract_metric(trials, "filtered_search_latency_us", "p99")
    fp999 = _extract_metric(trials, "filtered_search_latency_us", "p999")

    up50 = _extract_metric(trials, "unfiltered_search_latency_us", "p50")
    up99 = _extract_metric(trials, "unfiltered_search_latency_us", "p99")

    l1p99 = _extract_metric(trials, "filter_l1_latency_us", "p99")
    l2p99 = _extract_metric(trials, "filter_l2_latency_us", "p99")
    l3p99 = _extract_metric(trials, "filter_l3_latency_us", "p99")
    l4p99 = _extract_metric(trials, "filter_l4_latency_us", "p99")
    l5p99 = _extract_metric(trials, "filter_l5_latency_us", "p99")

    wp99 = _extract_metric(trials, "update_latency_us", "p99")

    # Filter overhead
    median_fp99 = float(np.median(fp99))
    median_up99 = float(np.median(up99))
    overhead = median_fp99 / max(median_up99, 0.001)

    return CrossTrialStats(
        system=system,
        num_trials=n,
        filtered_p50_median=float(np.median(fp50)),
        filtered_p50_min=float(np.min(fp50)),
        filtered_p50_max=float(np.max(fp50)),
        filtered_p99_median=median_fp99,
        filtered_p99_min=float(np.min(fp99)),
        filtered_p99_max=float(np.max(fp99)),
        filtered_p999_median=float(np.median(fp999)),
        unfiltered_p50_median=float(np.median(up50)),
        unfiltered_p99_median=median_up99,
        filter_l1_p99_median=float(np.median(l1p99)),
        filter_l2_p99_median=float(np.median(l2p99)),
        filter_l3_p99_median=float(np.median(l3p99)),
        filter_l4_p99_median=float(np.median(l4p99)),
        filter_l5_p99_median=float(np.median(l5p99)),
        update_p99_median=float(np.median(wp99)),
        filtered_search_success_rate=_success_rate(trials, "filtered_search_total", "filtered_search_error"),
        unfiltered_search_success_rate=_success_rate(trials, "unfiltered_search_total", "unfiltered_search_error"),
        update_success_rate=_success_rate(trials, "update_total", "update_error"),
        filter_overhead_ratio=round(overhead, 2),
        p99_trial_variance=float(np.max(fp99) - np.min(fp99)),
    )


def compute_pass_at_k(
    trials: list[dict],
    threshold_ms: float = 50.0,
) -> dict[str, float]:
    """
    pass@k for filtered search p99 < threshold_ms under load.
    Default threshold: 50ms (the adMarketplace target).
    """
    n = len(trials)
    successes = sum(
        1
        for t in trials
        if t.get("histograms", {})
        .get("filtered_search_latency_us", {})
        .get("p99", float("inf"))
        < threshold_ms
    )

    result: dict[str, float] = {}
    for k in [1, 3, 5]:
        if k > n:
            continue
        if successes >= k:
            pass_at_k = 1.0 - comb(n - successes, k) / max(comb(n, k), 1)
        else:
            pass_at_k = 0.0
        pass_pow_k = (successes / max(n, 1)) ** k
        result[f"pass_at_{k}"] = round(pass_at_k, 3)
        result[f"pass_pow_{k}"] = round(pass_pow_k, 3)

    return result
