from __future__ import annotations

import asyncio
import logging
import os
import time

import weaviate
from weaviate.classes.config import Configure, DataType, Property, VectorDistances
from weaviate.classes.data import DataObject
from weaviate.classes.init import Auth
from weaviate.classes.query import MetadataQuery
from weaviate.util import generate_uuid5

from benchmark.clients.base_client import (
    BaseVectorClient,
    CollectionConfig,
    NetworkBaseline,
    RateLimitError,
    SearchResult,
)

log = logging.getLogger(__name__)


class WeaviateCloudClient(BaseVectorClient):
    def __init__(self) -> None:
        self._client: weaviate.WeaviateClient | None = None
        self._collection_name: str = ""

    async def connect(self) -> None:
        url = os.getenv("WEAVIATE_URL")
        api_key = os.getenv("WEAVIATE_API_KEY")

        if not url or not api_key:
            raise ValueError("WEAVIATE_URL and WEAVIATE_API_KEY must be set in .env")

        self._client = weaviate.connect_to_weaviate_cloud(
            cluster_url=url,
            auth_credentials=Auth.api_key(api_key),
        )

        meta = self._client.get_meta()
        log.info(
            f"Connected to Weaviate Cloud at {url} "
            f"(version {meta.get('version', 'unknown')})"
        )

    async def disconnect(self) -> None:
        if self._client:
            self._client.close()
            self._client = None

    async def measure_baseline_latency(self) -> NetworkBaseline:
        latencies: list[float] = []
        for _ in range(20):
            start = time.monotonic()
            self._client.get_meta()
            elapsed_ms = (time.monotonic() - start) * 1000
            latencies.append(elapsed_ms)

        measured = sorted(latencies[5:])
        median_ms = measured[len(measured) // 2]
        return NetworkBaseline(ping_ms=median_ms, empty_request_ms=median_ms)

    async def create_collection(self, config: CollectionConfig) -> None:
        self._collection_name = config.name

        try:
            self._client.collections.delete(config.name)
        except Exception:
            pass

        distance_map = {
            "euclidean": VectorDistances.L2_SQUARED,
            "cosine": VectorDistances.COSINE,
            "dot": VectorDistances.DOT,
        }

        self._client.collections.create(
            name=config.name,
            vectorizer_config=Configure.Vectorizer.none(),
            vector_index_config=Configure.VectorIndex.hnsw(
                distance_metric=distance_map.get(
                    config.distance, VectorDistances.L2_SQUARED
                ),
            ),
            properties=[
                Property(name="idx", data_type=DataType.INT),
                Property(name="batch_num", data_type=DataType.INT),
                Property(name="is_freshness_probe", data_type=DataType.BOOL),
            ],
        )

        log.info(
            f"Created collection '{config.name}' "
            f"({config.vector_dim}-dim, {config.distance}, default HNSW)"
        )

    async def delete_collection(self, name: str) -> None:
        try:
            self._client.collections.delete(name)
        except Exception:
            pass

    async def upsert_batch(
        self,
        vectors: list[list[float]],
        ids: list[int],
        payloads: list[dict],
    ) -> None:
        collection = self._client.collections.get(self._collection_name)

        objects = [
            DataObject(
                properties={
                    "idx": payloads[i].get("idx", ids[i]),
                    "batch_num": payloads[i].get("batch", 0),
                    "is_freshness_probe": payloads[i].get("_freshness_probe", False),
                },
                vector=vectors[i],
                uuid=generate_uuid5(ids[i]),
            )
            for i in range(len(ids))
        ]

        def _insert() -> None:
            response = collection.data.insert_many(objects)
            if response.has_errors:
                error_msgs = [str(e) for e in response.errors.values()]
                if any("rate" in e.lower() or "429" in e for e in error_msgs):
                    raise RateLimitError()
                raise RuntimeError(f"Weaviate insert errors: {error_msgs[:3]}")

        try:
            await asyncio.to_thread(_insert)
        except weaviate.exceptions.WeaviateConnectionError as e:
            raise RateLimitError() from e

    async def search(
        self,
        query_vector: list[float],
        top_k: int = 10,
    ) -> list[SearchResult]:
        collection = self._client.collections.get(self._collection_name)

        def _search() -> list[SearchResult]:
            response = collection.query.near_vector(
                near_vector=query_vector,
                limit=top_k,
                return_metadata=MetadataQuery(distance=True),
                return_properties=["idx"],
            )
            return [
                SearchResult(
                    id=obj.properties.get("idx", 0),
                    score=obj.metadata.distance if obj.metadata else 0.0,
                    payload=obj.properties,
                )
                for obj in response.objects
            ]

        try:
            return await asyncio.to_thread(_search)
        except weaviate.exceptions.WeaviateConnectionError as e:
            raise RateLimitError() from e

    async def count(self) -> int:
        collection = self._client.collections.get(self._collection_name)
        result = collection.aggregate.over_all(total_count=True)
        return result.total_count or 0

    def name(self) -> str:
        return "weaviate_cloud"
