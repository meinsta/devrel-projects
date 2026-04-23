from __future__ import annotations

import asyncio
import logging
import time

import numpy as np

from benchmark.clients.base_client import BaseVectorClient, RateLimitError
from benchmark.datasets.download_sift import compute_recall
from benchmark.harness.metrics import MetricsCollector
from benchmark.workloads.freshness_probe import FreshnessProber
from benchmark.workloads.write_heavy import (
    ScheduledOp,
    WorkloadConfig,
    WriteBatch,
    generate_operation_schedule,
    prepare_write_batches,
)

log = logging.getLogger(__name__)

WRITE_CONCURRENCY = 32
READ_CONCURRENCY = 16
FRESHNESS_CONCURRENCY = 2
FRESHNESS_PROBE_INTERVAL_S = 1.0


class OpenLoopScheduler:
    def __init__(
        self,
        target_ops_per_sec: int = 1000,
        write_ratio: float = 0.70,
        read_ratio: float = 0.30,
        duration_s: int = 300,
        seed: int = 42,
        arrival_model: str = "uniform",
    ) -> None:
        self._config = WorkloadConfig(
            write_ratio=write_ratio,
            read_ratio=read_ratio,
            target_ops_per_sec=target_ops_per_sec,
            duration_s=duration_s,
        )
        self._seed = seed
        self._arrival_model = arrival_model

        self._write_batches: list[WriteBatch] = []
        self._query_vectors: np.ndarray | None = None
        self._ground_truth: np.ndarray | None = None
        self._read_top_k: int = 10

    def set_write_data(
        self,
        vectors: np.ndarray,
        ids: list[int],
        payloads: list[dict],
    ) -> None:
        self._write_batches = prepare_write_batches(
            vectors, ids[0], self._config.write_batch_size
        )

    def set_read_data(
        self,
        query_vectors: np.ndarray,
        ground_truth: np.ndarray,
        top_k: int = 10,
    ) -> None:
        self._query_vectors = query_vectors
        self._ground_truth = ground_truth
        self._read_top_k = top_k

    async def run(
        self,
        client: BaseVectorClient,
        metrics: MetricsCollector,
    ) -> None:
        schedule = generate_operation_schedule(
            self._config, self._seed, self._arrival_model
        )

        log.info(
            f"Schedule: {len(schedule)} ops over {self._config.duration_s}s "
            f"({self._config.target_ops_per_sec} ops/s, "
            f"{self._config.write_ratio*100:.0f}% writes)"
        )

        write_queue: asyncio.Queue[tuple[float, WriteBatch]] = asyncio.Queue()
        read_queue: asyncio.Queue[tuple[float, int]] = asyncio.Queue()
        freshness_queue: asyncio.Queue[float] = asyncio.Queue()

        prober = FreshnessProber(seed=self._seed + 1000)

        workers = []
        for i in range(WRITE_CONCURRENCY):
            workers.append(
                asyncio.create_task(
                    self._write_worker(i, write_queue, client, metrics)
                )
            )
        for i in range(READ_CONCURRENCY):
            workers.append(
                asyncio.create_task(
                    self._read_worker(i, read_queue, client, metrics)
                )
            )
        for i in range(FRESHNESS_CONCURRENCY):
            workers.append(
                asyncio.create_task(
                    self._freshness_worker(i, freshness_queue, prober, client, metrics)
                )
            )

        start_time = time.monotonic()

        # Freshness ticker
        async def freshness_ticker() -> None:
            while (time.monotonic() - start_time) < self._config.duration_s:
                elapsed = time.monotonic() - start_time
                await freshness_queue.put(elapsed)
                await asyncio.sleep(FRESHNESS_PROBE_INTERVAL_S)

        ticker_task = asyncio.create_task(freshness_ticker())

        # Dispatch loop
        write_idx = 0
        for op in schedule:
            now = time.monotonic() - start_time
            delay = op.scheduled_time_s - now
            if delay > 0:
                await asyncio.sleep(delay)

            if op.op_type == "write":
                if write_idx < len(self._write_batches):
                    batch = self._write_batches[write_idx]
                    await write_queue.put((op.scheduled_time_s + start_time, batch))
                    write_idx += 1
            elif op.op_type == "read":
                query_idx = op.op_index % len(self._query_vectors)
                await read_queue.put((op.scheduled_time_s + start_time, query_idx))

        # Wait for queues to drain
        log.info("Dispatch complete, draining queues...")
        await write_queue.join()
        await read_queue.join()

        ticker_task.cancel()
        try:
            await ticker_task
        except asyncio.CancelledError:
            pass

        await freshness_queue.join()

        for w in workers:
            w.cancel()

        await asyncio.gather(*workers, return_exceptions=True)

        log.info(
            f"Benchmark phase complete. "
            f"Writes: {metrics._counters['write_total']} "
            f"({metrics._counters['write_error']} errors). "
            f"Reads: {metrics._counters['read_total']} "
            f"({metrics._counters['read_error']} errors). "
            f"Freshness probes: {metrics._counters['freshness_total']} "
            f"({metrics._counters['freshness_timeout']} timeouts)."
        )

    async def _write_worker(
        self,
        worker_id: int,
        queue: asyncio.Queue[tuple[float, WriteBatch]],
        client: BaseVectorClient,
        metrics: MetricsCollector,
    ) -> None:
        while True:
            scheduled_abs, batch = await queue.get()
            try:
                await client.upsert_batch(
                    batch.vectors.tolist(), batch.ids, batch.payloads
                )
                latency_us = int((time.monotonic() - scheduled_abs) * 1_000_000)
                metrics.record_write(latency_us, success=True)
            except RateLimitError:
                latency_us = int((time.monotonic() - scheduled_abs) * 1_000_000)
                metrics.record_write(latency_us, success=False)
                metrics.record_rate_limit(client.name(), None)
            except Exception as e:
                latency_us = int((time.monotonic() - scheduled_abs) * 1_000_000)
                metrics.record_write(latency_us, success=False)
                log.debug(f"write_worker_{worker_id}: {e}")
            finally:
                queue.task_done()

    async def _read_worker(
        self,
        worker_id: int,
        queue: asyncio.Queue[tuple[float, int]],
        client: BaseVectorClient,
        metrics: MetricsCollector,
    ) -> None:
        while True:
            scheduled_abs, query_idx = await queue.get()
            try:
                query_vec = self._query_vectors[query_idx].tolist()
                results = await client.search(query_vec, top_k=self._read_top_k)
                latency_us = int((time.monotonic() - scheduled_abs) * 1_000_000)
                result_ids = [r.id for r in results]
                recall = compute_recall(
                    result_ids, self._ground_truth[query_idx], self._read_top_k
                )
                metrics.record_read(latency_us, success=True, recall=recall)
            except RateLimitError:
                latency_us = int((time.monotonic() - scheduled_abs) * 1_000_000)
                metrics.record_read(latency_us, success=False, recall=0.0)
                metrics.record_rate_limit(client.name(), None)
            except Exception as e:
                latency_us = int((time.monotonic() - scheduled_abs) * 1_000_000)
                metrics.record_read(latency_us, success=False, recall=0.0)
                log.debug(f"read_worker_{worker_id}: {e}")
            finally:
                queue.task_done()

    async def _freshness_worker(
        self,
        worker_id: int,
        queue: asyncio.Queue[float],
        prober: FreshnessProber,
        client: BaseVectorClient,
        metrics: MetricsCollector,
    ) -> None:
        while True:
            benchmark_elapsed = await queue.get()
            try:
                await prober.execute_probe(client, metrics, benchmark_elapsed)
            except Exception as e:
                log.debug(f"freshness_worker_{worker_id}: {e}")
            finally:
                queue.task_done()
