from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class ScheduledOp:
    scheduled_time_s: float
    op_type: str  # "filtered_search" | "update" | "unfiltered_search"
    op_index: int
    filter_level: int  # 0 = no filter, 1-5 = filter complexity


@dataclass
class WorkloadConfig:
    filtered_search_ratio: float = 0.60
    unfiltered_search_ratio: float = 0.10
    update_ratio: float = 0.30
    target_ops_per_sec: int = 1000
    duration_s: int = 300
    filter_level_weights: list[float] | None = None


def generate_operation_schedule(
    config: WorkloadConfig,
    seed: int = 42,
    arrival_model: str = "uniform",
) -> list[ScheduledOp]:
    rng = np.random.default_rng(seed)

    total_ops = config.target_ops_per_sec * config.duration_s
    filtered_count = int(total_ops * config.filtered_search_ratio)
    unfiltered_count = int(total_ops * config.unfiltered_search_ratio)
    update_count = total_ops - filtered_count - unfiltered_count

    weights = config.filter_level_weights or [0.20, 0.25, 0.25, 0.20, 0.10]

    filtered_rate = config.target_ops_per_sec * config.filtered_search_ratio
    unfiltered_rate = config.target_ops_per_sec * config.unfiltered_search_ratio
    update_rate = config.target_ops_per_sec * config.update_ratio

    if arrival_model == "poisson":
        filtered_intervals = rng.exponential(1.0 / max(filtered_rate, 0.01), size=filtered_count)
        unfiltered_intervals = rng.exponential(1.0 / max(unfiltered_rate, 0.01), size=unfiltered_count)
        update_intervals = rng.exponential(1.0 / max(update_rate, 0.01), size=update_count)
    else:
        filtered_intervals = np.full(filtered_count, 1.0 / max(filtered_rate, 0.01))
        unfiltered_intervals = np.full(unfiltered_count, 1.0 / max(unfiltered_rate, 0.01))
        update_intervals = np.full(update_count, 1.0 / max(update_rate, 0.01))

    filtered_times = np.cumsum(filtered_intervals)
    unfiltered_times = np.cumsum(unfiltered_intervals)
    update_times = np.cumsum(update_intervals)

    # Assign filter levels to filtered searches
    filter_levels = rng.choice([1, 2, 3, 4, 5], size=filtered_count, p=weights)

    schedule: list[ScheduledOp] = []

    for i, t in enumerate(filtered_times):
        if t > config.duration_s:
            break
        schedule.append(ScheduledOp(
            scheduled_time_s=float(t),
            op_type="filtered_search",
            op_index=i,
            filter_level=int(filter_levels[i]),
        ))

    for i, t in enumerate(unfiltered_times):
        if t > config.duration_s:
            break
        schedule.append(ScheduledOp(
            scheduled_time_s=float(t),
            op_type="unfiltered_search",
            op_index=i,
            filter_level=0,
        ))

    for i, t in enumerate(update_times):
        if t > config.duration_s:
            break
        schedule.append(ScheduledOp(
            scheduled_time_s=float(t),
            op_type="update",
            op_index=i,
            filter_level=0,
        ))

    schedule.sort(key=lambda op: op.scheduled_time_s)
    return schedule
