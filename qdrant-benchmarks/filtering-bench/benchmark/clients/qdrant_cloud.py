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


def _translate_filter(condition: dict | None) -> models.Filter | None:
    if condition is None:
        return None

    must_clauses = []
    for cond in condition.get("must", []):
        field = cond["field"]
        if "match" in cond:
            must_clauses.append(
                models.FieldCondition(
                    key=field, match=models.MatchValue(value=cond["match"])
                )
            )
        elif "match_any" in cond:
            must_clauses.append(
                models.FieldCondition(
                    key=field, match=models.MatchAny(any=cond["match_any"])
                )
            )
        elif "range" in cond:
            r = cond["range"]
            must_clauses.append(
                models.FieldCondition(
                    key=field,
                    range=models.Range(
                        gte=r.get("gte"),
                        lte=r.get("lte"),
                    ),
                )
            )

    return models.Filter(must=must_clauses) if must_clauses else None


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
            url=url, api_key=api_key, prefer_grpc=True, timeout=60,
        )
        collections = await self._client.get_collections()
        log.info(f"Connected to Qdrant Cloud at {url} ({len(collections.collections)} collections)")

    async def disconnect(self) -> None:
        if self._client:
            await self._client.close()
            self._client = None

    async def measure_baseline_latency(self) -> NetworkBaseline:

        latencies: list[float] = []
        for _ in range(20):
            start = time.monotonic()
            await self._client.get_collections()
            latencies.append((time.monotonic() - start) * 1000)
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
        log.info(f"Created collection '{config.name}' ({config.vector_dim}-dim)")

    async def delete_collection(self, name: str) -> None:

        try:
            await self._client.delete_collection(name)
        except Exception:
            pass

    async def create_payload_index(self, collection: str, field_name: str, field_type: str) -> None:

        type_map = {
            "keyword": models.PayloadSchemaType.KEYWORD,
            "integer": models.PayloadSchemaType.INTEGER,
            "float": models.PayloadSchemaType.FLOAT,
            "bool": models.PayloadSchemaType.BOOL,
            "geo": models.PayloadSchemaType.GEO,
        }
        schema_type = type_map.get(field_type, models.PayloadSchemaType.KEYWORD)
        await self._client.create_payload_index(
            collection_name=collection,
            field_name=field_name,
            field_schema=schema_type,
        )
        log.info(f"Created payload index: {field_name} ({field_type})")

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
                collection_name=self._collection_name, points=points, wait=False,
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
        filter_condition: dict | None = None,
    ) -> list[SearchResult]:

        try:
            qdrant_filter = _translate_filter(filter_condition)
            results = await self._client.query_points(
                collection_name=self._collection_name,
                query=query_vector,
                query_filter=qdrant_filter,
                limit=top_k,
            )
            return [
                SearchResult(id=int(p.id), score=p.score, payload=p.payload)
                for p in results.points
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
