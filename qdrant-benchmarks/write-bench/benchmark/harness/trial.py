from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from benchmark.clients.base_client import (
    BaseVectorClient,
    CollectionConfig,
    NetworkBaseline,
)
from benchmark.datasets.download_sift import SIFTDataset
from benchmark.harness.metrics import (
    FRESHNESS_LATENCY,
    READ_LATENCY,
    WRITE_LATENCY,
    MetricsCollector,
    PercentileReport,
)
from benchmark.harness.open_loop import OpenLoopScheduler

log = logging.getLogger(__name__)


@dataclass
class TrialConfig:
    system: str
    trial_number: int
    seed: int
    duration_s: int
    target_ops_per_sec: int
    write_ratio: float
    read_ratio: float
    write_batch_size: int
    read_top_k: int
    preload_count: int
    arrival_model: str
    output_dir: Path
    dataset: SIFTDataset
    collection_name: str


@dataclass
class TrialResult:
    system: str
    trial_number: int
    seed: int
    baseline: NetworkBaseline | None
    write_percentiles: PercentileReport
    read_percentiles: PercentileReport
    freshness_percentiles: PercentileReport
    counters: dict[str, int]


class Trial:
    def __init__(self, config: TrialConfig, client: BaseVectorClient) -> None:
        self._config = config
        self._client = client
        self._metrics = MetricsCollector()
        self._baseline: NetworkBaseline | None = None

    async def execute(self) -> TrialResult:
        try:
            await self._setup()
            await self._preload()
            await self._benchmark()
            result = await self._export()
            return result
        finally:
            await self._teardown()

    async def _setup(self) -> None:
        await self._client.connect()

        self._baseline = await self._client.measure_baseline_latency()
        log.info(
            f"Baseline latency to {self._config.system}: "
            f"{self._baseline.ping_ms:.1f}ms"
        )

        await self._client.delete_collection(self._config.collection_name)
        await asyncio.sleep(2)

        await self._client.create_collection(
            CollectionConfig(
                name=self._config.collection_name,
                vector_dim=128,
                distance="euclidean",
            )
        )



    async def _preload(self) -> None:
        vectors = self._config.dataset.base_vectors[: self._config.preload_count]
        ids = list(range(self._config.preload_count))
        payloads = [{"idx": i, "batch": i // 1000} for i in ids]

        preload_batch_size = 1000
        total_batches = (len(vectors) + preload_batch_size - 1) // preload_batch_size

        log.info(f"Pre-loading {self._config.preload_count} vectors...")
        start = time.monotonic()

        for batch_num in range(total_batches):
            s = batch_num * preload_batch_size
            e = min(s + preload_batch_size, len(vectors))

            await self._client.upsert_batch(
                vectors=vectors[s:e].tolist(),
                ids=ids[s:e],
                payloads=payloads[s:e],
            )

            if batch_num % 50 == 0:
                log.info(f"  Pre-load progress: {e}/{self._config.preload_count}")

        await self._wait_for_index_ready()

        # Warm-up queries (discarded)
        rng = np.random.default_rng(self._config.seed)
        warmup_indices = rng.choice(
            len(self._config.dataset.query_vectors), size=100, replace=False
        )
        for idx in warmup_indices:
            await self._client.search(
                self._config.dataset.query_vectors[idx].tolist(),
                top_k=self._config.read_top_k,
            )

        elapsed = time.monotonic() - start
        log.info(
            f"Pre-load complete: {self._config.preload_count} vectors in {elapsed:.1f}s"
        )

    async def _wait_for_index_ready(self, timeout_s: int = 600) -> None:
        start = time.monotonic()
        while (time.monotonic() - start) < timeout_s:
            try:
                count = await self._client.count()
                if count >= self._config.preload_count:
                    log.info(
                        f"Index ready: {count} vectors in {time.monotonic() - start:.1f}s"
                    )
                    return
            except Exception:
                pass

            # Fallback: try a search to verify data is queryable
            try:
                query_vec = self._config.dataset.query_vectors[0].tolist()
                results = await self._client.search(query_vec, top_k=1)
                if results:
                    log.info(
                        f"Index ready (search verified) in {time.monotonic() - start:.1f}s"
                    )
                    return
            except Exception:
                pass

            await asyncio.sleep(5)

        raise RuntimeError(
            f"Index not ready after {timeout_s}s "
            f"(expected={self._config.preload_count})"
        )

    async def _benchmark(self) -> None:
        write_vectors = self._config.dataset.base_vectors[self._config.preload_count :]
        write_ids = list(range(self._config.preload_count, 1_000_000))
        write_payloads = [
            {"idx": i, "batch": i // self._config.write_batch_size} for i in write_ids
        ]

        scheduler = OpenLoopScheduler(
            target_ops_per_sec=self._config.target_ops_per_sec,
            write_ratio=self._config.write_ratio,
            read_ratio=self._config.read_ratio,
            duration_s=self._config.duration_s,
            seed=self._config.seed,
            arrival_model=self._config.arrival_model,
        )

        scheduler.set_write_data(write_vectors, write_ids, write_payloads)
        scheduler.set_read_data(
            self._config.dataset.query_vectors,
            self._config.dataset.ground_truth,
            self._config.read_top_k,
        )

        log.info(
            f"Starting benchmark phase ({self._config.duration_s}s, "
            f"{self._config.target_ops_per_sec} ops/s, "
            f"{self._config.write_ratio*100:.0f}/{self._config.read_ratio*100:.0f} w/r)"
        )

        self._metrics.start()
        await scheduler.run(self._client, self._metrics)

    async def _export(self) -> TrialResult:
        prefix = f"{self._config.system}_trial_{self._config.trial_number}"
        out = self._config.output_dir
        out.mkdir(parents=True, exist_ok=True)

        self._metrics.export_json(out / f"{prefix}.json")
        self._metrics.export_hdr(out / f"{prefix}_write.hdr", WRITE_LATENCY)
        self._metrics.export_hdr(out / f"{prefix}_read.hdr", READ_LATENCY)
        self._metrics.export_hdr(out / f"{prefix}_freshness.hdr", FRESHNESS_LATENCY)

        log.info(f"Exported results to {out / prefix}.json")

        return TrialResult(
            system=self._config.system,
            trial_number=self._config.trial_number,
            seed=self._config.seed,
            baseline=self._baseline,
            write_percentiles=self._metrics.get_percentiles(WRITE_LATENCY),
            read_percentiles=self._metrics.get_percentiles(READ_LATENCY),
            freshness_percentiles=self._metrics.get_percentiles(FRESHNESS_LATENCY),
            counters=dict(self._metrics._counters),
        )

    async def _teardown(self) -> None:
        try:
            await self._client.delete_collection(self._config.collection_name)
        except Exception:
            pass
        try:
            await self._client.disconnect()
        except Exception:
            pass
