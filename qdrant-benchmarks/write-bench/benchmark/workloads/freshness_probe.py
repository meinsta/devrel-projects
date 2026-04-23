from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass

import numpy as np

from benchmark.clients.base_client import BaseVectorClient
from benchmark.harness.metrics import MetricsCollector

log = logging.getLogger(__name__)

PROBE_ID_OFFSET = 10_000_000
POLL_INTERVAL_S = 0.050  # 50ms between polls
FRESHNESS_TIMEOUT_S = 5.0
PROBE_INTERVAL_S = 0.1  # one probe every 100ms


@dataclass
class FreshnessProbe:
    id: int
    vector: list[float]
    payload: dict


@dataclass
class FreshnessResult:
    probe_id: int
    benchmark_elapsed_s: float
    upsert_latency_us: int
    freshness_latency_us: int
    total_latency_us: int
    found: bool
    poll_count: int


class FreshnessProber:
    def __init__(self, seed: int = 42) -> None:
        self._rng = np.random.default_rng(seed)
        self._next_probe_id = PROBE_ID_OFFSET
        self._results: list[FreshnessResult] = []

    def generate_probe(self) -> FreshnessProbe:
            probe_id = self._next_probe_id
        self._next_probe_id += 1

        vector = self._rng.standard_normal(128).astype(np.float32)
        vector = vector / np.linalg.norm(vector)

        return FreshnessProbe(
            id=probe_id,
            vector=vector.tolist(),
            payload={"_freshness_probe": True, "_probe_id": probe_id, "idx": probe_id},
        )

    async def execute_probe(
        self,
        client: BaseVectorClient,
        metrics: MetricsCollector,
        benchmark_elapsed_s: float,
    ) -> FreshnessResult:
            probe = self.generate_probe()

        t0 = time.monotonic()

        await client.upsert_batch([probe.vector], [probe.id], [probe.payload])
        t1 = time.monotonic()
        upsert_latency_us = int((t1 - t0) * 1_000_000)

        found = False
        poll_count = 0
        while (time.monotonic() - t1) < FRESHNESS_TIMEOUT_S:
            results = await client.search(probe.vector, top_k=1)
            poll_count += 1
            if results and results[0].id == probe.id:
                found = True
                break
            await asyncio.sleep(POLL_INTERVAL_S)

        t2 = time.monotonic()
        freshness_latency_us = int((t2 - t1) * 1_000_000)
        total_latency_us = int((t2 - t0) * 1_000_000)

        metrics.record_freshness(freshness_latency_us, success=found)

        result = FreshnessResult(
            probe_id=probe.id,
            benchmark_elapsed_s=benchmark_elapsed_s,
            upsert_latency_us=upsert_latency_us,
            freshness_latency_us=freshness_latency_us,
            total_latency_us=total_latency_us,
            found=found,
            poll_count=poll_count,
        )
        self._results.append(result)

        if not found:
            log.warning(
                f"Freshness probe {probe.id} timed out after {FRESHNESS_TIMEOUT_S}s "
                f"({poll_count} polls)"
            )

        return result
