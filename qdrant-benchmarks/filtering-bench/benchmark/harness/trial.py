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
from benchmark.datasets.payload_generator import PAYLOAD_INDEX_FIELDS, PayloadGenerator
from benchmark.harness.metrics import (
    FILTER_LEVEL_LATENCIES,
    FILTERED_SEARCH_LATENCY,
    UNFILTERED_SEARCH_LATENCY,
    UPDATE_LATENCY,
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
    filtered_search_ratio: float
    unfiltered_search_ratio: float
    update_ratio: float
    read_top_k: int
    preload_count: int
    arrival_model: str
    output_dir: Path
    dataset: SIFTDataset
    collection_name: str
    filter_level_weights: list[float] | None = None


@dataclass
class TrialResult:
    system: str
    trial_number: int
    seed: int
    baseline: NetworkBaseline | None
    filtered_search_percentiles: PercentileReport
    unfiltered_search_percentiles: PercentileReport
    update_percentiles: PercentileReport
    filter_level_percentiles: dict[int, PercentileReport]
    counters: dict[str, int]


class Trial:
    def __init__(self, config: TrialConfig, client: BaseVectorClient) -> None:
        self._config = config
        self._client = client
        self._metrics = MetricsCollector()
        self._baseline: NetworkBaseline | None = None
        self._payload_gen = PayloadGenerator(seed=config.seed)

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
        log.info(f"Baseline latency to {self._config.system}: {self._baseline.ping_ms:.1f}ms")

        await self._client.delete_collection(self._config.collection_name)
        await asyncio.sleep(2)

        await self._client.create_collection(
            CollectionConfig(
                name=self._config.collection_name,
                vector_dim=128,
                distance="euclidean",
            )
        )

        # Create payload indexes for efficient filtering
        log.info("Creating payload indexes...")
        for idx_config in PAYLOAD_INDEX_FIELDS:
            try:
                await self._client.create_payload_index(
                    self._config.collection_name,
                    idx_config.field_name,
                    idx_config.field_type,
                )
            except Exception as e:
                log.debug(f"Index creation for {idx_config.field_name}: {e}")

    async def _preload(self) -> None:
        vectors = self._config.dataset.base_vectors[: self._config.preload_count]
        preload_batch_size = 500

        total_batches = (len(vectors) + preload_batch_size - 1) // preload_batch_size
        log.info(f"Pre-loading {self._config.preload_count} vectors with filter payloads...")
        start = time.monotonic()

        for batch_num in range(total_batches):
            s = batch_num * preload_batch_size
            e = min(s + preload_batch_size, len(vectors))
            batch_ids = list(range(s, e))
            batch_payloads = self._payload_gen.generate_batch(s, e - s)

            await self._client.upsert_batch(
                vectors=vectors[s:e].tolist(),
                ids=batch_ids,
                payloads=batch_payloads,
            )

            if batch_num % 100 == 0:
                log.info(f"  Pre-load progress: {e}/{self._config.preload_count}")

        await self._wait_for_index_ready()

        # Warm-up: run some filtered queries (discarded, errors swallowed)
        rng = np.random.default_rng(self._config.seed)
        from benchmark.workloads.filter_scenarios import FilterScenarioGenerator
        warmup_filter_gen = FilterScenarioGenerator(seed=self._config.seed + 999)
        warmup_indices = rng.choice(len(self._config.dataset.query_vectors), size=50, replace=False)
        warmup_ok = 0
        for idx in warmup_indices:
            try:
                scenario = warmup_filter_gen.generate_mixed()
                await self._client.search(
                    self._config.dataset.query_vectors[idx].tolist(),
                    top_k=self._config.read_top_k,
                    filter_condition=scenario.filter_condition,
                )
                warmup_ok += 1
            except Exception:
                pass
        log.info(f"Warmup: {warmup_ok}/{len(warmup_indices)} queries succeeded")

        elapsed = time.monotonic() - start
        log.info(f"Pre-load complete: {self._config.preload_count} vectors in {elapsed:.1f}s")

    async def _wait_for_index_ready(self, timeout_s: int = 600) -> None:
        start = time.monotonic()
        while (time.monotonic() - start) < timeout_s:
            try:
                count = await self._client.count()
                if count >= self._config.preload_count:
                    log.info(f"Index ready: {count} vectors in {time.monotonic() - start:.1f}s")
                    return
            except Exception:
                pass
            try:
                query_vec = self._config.dataset.query_vectors[0].tolist()
                results = await self._client.search(query_vec, top_k=1)
                if results:
                    log.info(f"Index ready (search verified) in {time.monotonic() - start:.1f}s")
                    return
            except Exception:
                pass
            await asyncio.sleep(5)
        raise RuntimeError(f"Index not ready after {timeout_s}s")

    async def _benchmark(self) -> None:
        scheduler = OpenLoopScheduler(
            target_ops_per_sec=self._config.target_ops_per_sec,
            filtered_search_ratio=self._config.filtered_search_ratio,
            unfiltered_search_ratio=self._config.unfiltered_search_ratio,
            update_ratio=self._config.update_ratio,
            duration_s=self._config.duration_s,
            seed=self._config.seed,
            arrival_model=self._config.arrival_model,
            filter_level_weights=self._config.filter_level_weights,
        )
        scheduler.set_read_data(self._config.dataset.query_vectors, self._config.read_top_k)
        scheduler.set_collection_info(self._config.collection_name, self._config.preload_count)

        log.info(
            f"Starting benchmark phase ({self._config.duration_s}s, "
            f"{self._config.target_ops_per_sec} ops/s, "
            f"{self._config.filtered_search_ratio*100:.0f}% filtered / "
            f"{self._config.unfiltered_search_ratio*100:.0f}% unfiltered / "
            f"{self._config.update_ratio*100:.0f}% updates)"
        )

        self._metrics.start()
        await scheduler.run(self._client, self._metrics)

    async def _export(self) -> TrialResult:
        prefix = f"{self._config.system}_trial_{self._config.trial_number}"
        out = self._config.output_dir
        out.mkdir(parents=True, exist_ok=True)

        self._metrics.export_json(out / f"{prefix}.json")
        self._metrics.export_hdr(out / f"{prefix}_filtered.hdr", FILTERED_SEARCH_LATENCY)
        self._metrics.export_hdr(out / f"{prefix}_unfiltered.hdr", UNFILTERED_SEARCH_LATENCY)
        self._metrics.export_hdr(out / f"{prefix}_update.hdr", UPDATE_LATENCY)

        for level, hist_name in FILTER_LEVEL_LATENCIES.items():
            self._metrics.export_hdr(out / f"{prefix}_l{level}.hdr", hist_name)

        log.info(f"Exported results to {out / prefix}.json")

        filter_level_pcts = {}
        for level, hist_name in FILTER_LEVEL_LATENCIES.items():
            filter_level_pcts[level] = self._metrics.get_percentiles(hist_name)

        return TrialResult(
            system=self._config.system,
            trial_number=self._config.trial_number,
            seed=self._config.seed,
            baseline=self._baseline,
            filtered_search_percentiles=self._metrics.get_percentiles(FILTERED_SEARCH_LATENCY),
            unfiltered_search_percentiles=self._metrics.get_percentiles(UNFILTERED_SEARCH_LATENCY),
            update_percentiles=self._metrics.get_percentiles(UPDATE_LATENCY),
            filter_level_percentiles=filter_level_pcts,
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
