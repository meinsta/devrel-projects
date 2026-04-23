from __future__ import annotations

import asyncio
import logging
import time

import numpy as np

from benchmark.clients.base_client import BaseVectorClient, RateLimitError
from benchmark.datasets.payload_generator import PayloadGenerator
from benchmark.harness.metrics import MetricsCollector
from benchmark.workloads.filter_scenarios import FilterScenarioGenerator
from benchmark.workloads.filter_workload import (
    ScheduledOp,
    WorkloadConfig,
    generate_operation_schedule,
)

log = logging.getLogger(__name__)

FILTERED_SEARCH_CONCURRENCY = 24
UNFILTERED_SEARCH_CONCURRENCY = 8
UPDATE_CONCURRENCY = 16


class OpenLoopScheduler:
    def __init__(
        self,
        target_ops_per_sec: int = 1000,
        filtered_search_ratio: float = 0.60,
        unfiltered_search_ratio: float = 0.10,
        update_ratio: float = 0.30,
        duration_s: int = 300,
        seed: int = 42,
        arrival_model: str = "uniform",
        filter_level_weights: list[float] | None = None,
    ) -> None:
        self._config = WorkloadConfig(
            filtered_search_ratio=filtered_search_ratio,
            unfiltered_search_ratio=unfiltered_search_ratio,
            update_ratio=update_ratio,
            target_ops_per_sec=target_ops_per_sec,
            duration_s=duration_s,
            filter_level_weights=filter_level_weights,
        )
        self._seed = seed
        self._arrival_model = arrival_model

        self._query_vectors: np.ndarray | None = None
        self._read_top_k: int = 50  # Procurify requirement: expect 50 results
        self._collection_name: str = ""
        self._preload_count: int = 0

        self._filter_gen = FilterScenarioGenerator(seed=seed + 100)
        self._payload_gen = PayloadGenerator(seed=seed + 200)

    def set_read_data(
        self,
        query_vectors: np.ndarray,
        top_k: int = 50,
    ) -> None:
        self._query_vectors = query_vectors
        self._read_top_k = top_k

    def set_collection_info(self, collection_name: str, preload_count: int) -> None:
        self._collection_name = collection_name
        self._preload_count = preload_count

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
            f"{self._config.filtered_search_ratio*100:.0f}% filtered / "
            f"{self._config.unfiltered_search_ratio*100:.0f}% unfiltered / "
            f"{self._config.update_ratio*100:.0f}% updates)"
        )

        filtered_queue: asyncio.Queue[tuple[float, int, int]] = asyncio.Queue()
        unfiltered_queue: asyncio.Queue[tuple[float, int]] = asyncio.Queue()
        update_queue: asyncio.Queue[tuple[float, int]] = asyncio.Queue()

        workers = []
        for i in range(FILTERED_SEARCH_CONCURRENCY):
            workers.append(asyncio.create_task(
                self._filtered_search_worker(i, filtered_queue, client, metrics)
            ))
        for i in range(UNFILTERED_SEARCH_CONCURRENCY):
            workers.append(asyncio.create_task(
                self._unfiltered_search_worker(i, unfiltered_queue, client, metrics)
            ))
        for i in range(UPDATE_CONCURRENCY):
            workers.append(asyncio.create_task(
                self._update_worker(i, update_queue, client, metrics)
            ))

        start_time = time.monotonic()

        # Progress ticker
        async def progress_ticker() -> None:
            while (time.monotonic() - start_time) < self._config.duration_s:
                await asyncio.sleep(30)
                elapsed = time.monotonic() - start_time
                log.info(
                    f"Progress: {elapsed:.0f}/{self._config.duration_s}s, "
                    f"filtered={metrics._counters['filtered_search_total']} "
                    f"unfiltered={metrics._counters['unfiltered_search_total']} "
                    f"updates={metrics._counters['update_total']}"
                )

        ticker_task = asyncio.create_task(progress_ticker())

        # Dispatch loop
        update_idx = 0
        for op in schedule:
            now = time.monotonic() - start_time
            delay = op.scheduled_time_s - now
            if delay > 0:
                await asyncio.sleep(delay)

            abs_time = op.scheduled_time_s + start_time

            if op.op_type == "filtered_search":
                query_idx = op.op_index % len(self._query_vectors)
                await filtered_queue.put((abs_time, query_idx, op.filter_level))
            elif op.op_type == "unfiltered_search":
                query_idx = op.op_index % len(self._query_vectors)
                await unfiltered_queue.put((abs_time, query_idx))
            elif op.op_type == "update":
                await update_queue.put((abs_time, update_idx))
                update_idx += 1

        log.info("Dispatch complete, draining queues...")
        await filtered_queue.join()
        await unfiltered_queue.join()
        await update_queue.join()

        ticker_task.cancel()
        try:
            await ticker_task
        except asyncio.CancelledError:
            pass

        for w in workers:
            w.cancel()
        await asyncio.gather(*workers, return_exceptions=True)

        log.info(
            f"Benchmark phase complete. "
            f"Filtered: {metrics._counters['filtered_search_total']} "
            f"({metrics._counters['filtered_search_error']} errors). "
            f"Unfiltered: {metrics._counters['unfiltered_search_total']} "
            f"({metrics._counters['unfiltered_search_error']} errors). "
            f"Updates: {metrics._counters['update_total']} "
            f"({metrics._counters['update_error']} errors)."
        )

    async def _filtered_search_worker(
        self,
        worker_id: int,
        queue: asyncio.Queue[tuple[float, int, int]],
        client: BaseVectorClient,
        metrics: MetricsCollector,
    ) -> None:
        while True:
            scheduled_abs, query_idx, filter_level = await queue.get()
            try:
                query_vec = self._query_vectors[query_idx].tolist()
                scenario = self._filter_gen.generate(filter_level)
                results = await client.search(
                    query_vec, top_k=self._read_top_k,
                    filter_condition=scenario.filter_condition,
                )
                latency_us = int((time.monotonic() - scheduled_abs) * 1_000_000)
                metrics.record_filtered_search(
                    latency_us, success=True,
                    filter_level=filter_level,
                    result_count=len(results),
                )
            except RateLimitError:
                latency_us = int((time.monotonic() - scheduled_abs) * 1_000_000)
                metrics.record_filtered_search(latency_us, False, filter_level)
                metrics.record_rate_limit(client.name(), None)
            except Exception as e:
                latency_us = int((time.monotonic() - scheduled_abs) * 1_000_000)
                metrics.record_filtered_search(latency_us, False, filter_level)
                log.debug(f"filtered_worker_{worker_id}: {e}")
            finally:
                queue.task_done()

    async def _unfiltered_search_worker(
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
                metrics.record_unfiltered_search(
                    latency_us, success=True, result_count=len(results),
                )
            except RateLimitError:
                latency_us = int((time.monotonic() - scheduled_abs) * 1_000_000)
                metrics.record_unfiltered_search(latency_us, False)
                metrics.record_rate_limit(client.name(), None)
            except Exception as e:
                latency_us = int((time.monotonic() - scheduled_abs) * 1_000_000)
                metrics.record_unfiltered_search(latency_us, False)
                log.debug(f"unfiltered_worker_{worker_id}: {e}")
            finally:
                queue.task_done()

    async def _update_worker(
        self,
        worker_id: int,
        queue: asyncio.Queue[tuple[float, int]],
        client: BaseVectorClient,
        metrics: MetricsCollector,
    ) -> None:
        rng = np.random.default_rng(self._seed + worker_id + 5000)
        while True:
            scheduled_abs, update_idx = await queue.get()
            try:
                # Pick a random existing point and update its payload
                point_id = int(rng.integers(0, max(self._preload_count, 1)))
                # Generate fresh payload
                payload = self._payload_gen.generate(point_id).to_dict()
                # Use a random vector (simulates re-embedding after content update)
                dim = 128
                vec = rng.standard_normal(dim).astype(np.float32)
                vec = (vec / np.linalg.norm(vec)).tolist()

                await client.upsert_batch([vec], [point_id], [payload])
                latency_us = int((time.monotonic() - scheduled_abs) * 1_000_000)
                metrics.record_update(latency_us, success=True)
            except RateLimitError:
                latency_us = int((time.monotonic() - scheduled_abs) * 1_000_000)
                metrics.record_update(latency_us, success=False)
                metrics.record_rate_limit(client.name(), None)
            except Exception as e:
                latency_us = int((time.monotonic() - scheduled_abs) * 1_000_000)
                metrics.record_update(latency_us, success=False)
                log.debug(f"update_worker_{worker_id}: {e}")
            finally:
                queue.task_done()
