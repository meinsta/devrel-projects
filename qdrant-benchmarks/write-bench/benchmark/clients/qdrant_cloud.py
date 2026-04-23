from __future__ import annotations

import logging
import os
import time

from qdrant_client import AsyncQdrantClient, models

from benchmark.clients.base_client import (
    BaseVectorClient,
    CollectionConfig,
    NetworkBaseline,
    RateLimitError,
    SearchResult,
)

log = logging.getLogger(__name__)


class QdrantCloudClient(BaseVectorClient):
    def __init__(self) -> None:
        self._client: AsyncQdrantClient | None = None
        self._collection_name: str = ""

    async def connect(self) -> None:
        url = os.getenv("QDRANT_URL")
        api_key = os.getenv("QDRANT_API_KEY")

        if not url or not api_key:
            raise ValueError("QDRANT_URL and QDRANT_API_KEY must be set in .env")

        self._client = AsyncQdrantClient(
            url=url,
            api_key=api_key,
            prefer_grpc=True,
            timeout=30,
        )

        collections = await self._client.get_collections()
        log.info(
            f"Connected to Qdrant Cloud at {url} "
            f"({len(collections.collections)} existing collections)"
        )

    async def disconnect(self) -> None:
        if self._client:
            await self._client.close()
            self._client = None

    async def measure_baseline_latency(self) -> NetworkBaseline:
        latencies: list[float] = []
        for _ in range(20):
            start = time.monotonic()
            await self._client.get_collections()
            elapsed_ms = (time.monotonic() - start) * 1000
            latencies.append(elapsed_ms)

        measured = sorted(latencies[5:])
        median_ms = measured[len(measured) // 2]
        return NetworkBaseline(ping_ms=median_ms, empty_request_ms=median_ms)

    async def create_collection(self, config: CollectionConfig) -> None:
        self._collection_name = config.name

        try:
            await self._client.delete_collection(config.name)
        except Exception:
            pass

        distance_map = {
            "euclidean": models.Distance.EUCLID,
            "cosine": models.Distance.COSINE,
            "dot": models.Distance.DOT,
        }

        await self._client.create_collection(
            collection_name=config.name,
            vectors_config=models.VectorParams(
                size=config.vector_dim,
                distance=distance_map.get(config.distance, models.Distance.EUCLID),
            ),
        )

        log.info(f"Created collection '{config.name}' ({config.vector_dim}-dim, {config.distance})")

    async def delete_collection(self, name: str) -> None:
        try:
            await self._client.delete_collection(name)
        except Exception:
            pass

    async def upsert_batch(
        self,
        vectors: list[list[float]],
        ids: list[int],
        payloads: list[dict],
    ) -> None:
        points = [
            models.PointStruct(id=ids[i], vector=vectors[i], payload=payloads[i])
            for i in range(len(ids))
        ]

        try:
            await self._client.upsert(
                collection_name=self._collection_name,
                points=points,
                wait=False,
            )
        except Exception as e:
            err = str(e).lower()
            if "rate" in err or "429" in err:
                raise RateLimitError() from e
            raise

    async def search(
        self,
        query_vector: list[float],
        top_k: int = 10,
    ) -> list[SearchResult]:
        try:
            results = await self._client.query_points(
                collection_name=self._collection_name,
                query=query_vector,
                limit=top_k,
            )
            return [
                SearchResult(
                    id=int(point.id),
                    score=point.score,
                    payload=point.payload,
                )
                for point in results.points
            ]
        except Exception as e:
            err = str(e).lower()
            if "rate" in err or "429" in err:
                raise RateLimitError() from e
            raise

    async def count(self) -> int:
        info = await self._client.get_collection(self._collection_name)
        return info.points_count or 0

    def name(self) -> str:
        return "qdrant_cloud"
