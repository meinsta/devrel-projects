from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class ScheduledOp:
    scheduled_time_s: float
    op_type: str  # "write" | "read"
    op_index: int  # index into write_batches or query_vectors


@dataclass
class WriteBatch:
    vectors: np.ndarray  # (batch_size, 128)
    ids: list[int]
    payloads: list[dict]


@dataclass
class WorkloadConfig:
    write_ratio: float = 0.70
    read_ratio: float = 0.30
    write_batch_size: int = 100
    read_top_k: int = 10
    target_ops_per_sec: int = 1000
    duration_s: int = 300


def generate_operation_schedule(
    config: WorkloadConfig,
    seed: int = 42,
    arrival_model: str = "uniform",
) -> list[ScheduledOp]:
    """
    Pre-compute the full sequence of operations with scheduled times.

    Returns a sorted list of ScheduledOp. Each has a scheduled_time_s
    relative to benchmark start and an op_type ("write" or "read").
    """
    rng = np.random.default_rng(seed)

    total_ops = config.target_ops_per_sec * config.duration_s
    write_count = int(total_ops * config.write_ratio)
    read_count = total_ops - write_count

    write_rate = config.target_ops_per_sec * config.write_ratio
    read_rate = config.target_ops_per_sec * config.read_ratio

    if arrival_model == "poisson":
        write_intervals = rng.exponential(1.0 / write_rate, size=write_count)
        read_intervals = rng.exponential(1.0 / read_rate, size=read_count)
    else:
        write_intervals = np.full(write_count, 1.0 / write_rate)
        read_intervals = np.full(read_count, 1.0 / read_rate)

    write_times = np.cumsum(write_intervals)
    read_times = np.cumsum(read_intervals)

    schedule: list[ScheduledOp] = []

    for i, t in enumerate(write_times):
        if t > config.duration_s:
            break
        schedule.append(ScheduledOp(scheduled_time_s=float(t), op_type="write", op_index=i))

    for i, t in enumerate(read_times):
        if t > config.duration_s:
            break
        schedule.append(ScheduledOp(scheduled_time_s=float(t), op_type="read", op_index=i))

    schedule.sort(key=lambda op: op.scheduled_time_s)
    return schedule


def prepare_write_batches(
    vectors: np.ndarray,
    start_id: int,
    batch_size: int = 100,
) -> list[WriteBatch]:
    batches: list[WriteBatch] = []
    for i in range(0, len(vectors), batch_size):
        end = min(i + batch_size, len(vectors))
        batch_ids = list(range(start_id + i, start_id + end))
        batches.append(
            WriteBatch(
                vectors=vectors[i:end],
                ids=batch_ids,
                payloads=[{"idx": id_, "batch": i // batch_size} for id_ in batch_ids],
            )
        )
    return batches
