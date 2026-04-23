from __future__ import annotations

import asyncio
import logging
import os
import time

from pymilvus import CollectionSchema, DataType, FieldSchema, MilvusClient

from benchmark.clients.base_client import (
    BaseVectorClient,
    CollectionConfig,
    NetworkBaseline,
    RateLimitError,
    SearchResult,
)

log = logging.getLogger(__name__)


class ZillizCloudClient(BaseVectorClient):
    def __init__(self) -> None:
        self._client: MilvusClient | None = None
        self._collection_name: str = ""

    async def connect(self) -> None:
        uri = os.getenv("ZILLIZ_URI")
        token = os.getenv("ZILLIZ_TOKEN")

        if not uri or not token:
            raise ValueError("ZILLIZ_URI and ZILLIZ_TOKEN must be set in .env")

        self._client = MilvusClient(uri=uri, token=token)

        collections = self._client.list_collections()
        log.info(f"Connected to Zilliz Cloud at {uri} ({len(collections)} existing collections)")

    async def disconnect(self) -> None:
        if self._client:
            self._client.close()
            self._client = None

    async def measure_baseline_latency(self) -> NetworkBaseline:
        latencies: list[float] = []
        for _ in range(20):
            start = time.monotonic()
            self._client.list_collections()
            elapsed_ms = (time.monotonic() - start) * 1000
            latencies.append(elapsed_ms)

        measured = sorted(latencies[5:])
        median_ms = measured[len(measured) // 2]
        return NetworkBaseline(ping_ms=median_ms, empty_request_ms=median_ms)

    async def create_collection(self, config: CollectionConfig) -> None:
        self._collection_name = config.name

        try:
            self._client.drop_collection(config.name)
        except Exception:
            pass

        schema = CollectionSchema(
            fields=[
                FieldSchema(name="id", dtype=DataType.INT64, is_primary=True),
                FieldSchema(
                    name="vector",
                    dtype=DataType.FLOAT_VECTOR,
                    dim=config.vector_dim,
                ),
                FieldSchema(name="payload", dtype=DataType.JSON),
            ],
            auto_id=False,
        )

        metric_map = {
            "euclidean": "L2",
            "cosine": "COSINE",
            "dot": "IP",
        }

        index_params = self._client.prepare_index_params()
        index_params.add_index(
            field_name="vector",
            metric_type=metric_map.get(config.distance, "L2"),
            index_type="AUTOINDEX",
        )

        self._client.create_collection(
            collection_name=config.name,
            schema=schema,
            index_params=index_params,
        )

        # Ensure collection is loaded for serverless
        try:
            self._client.load_collection(config.name)
        except Exception:
            pass

        log.info(f"Created collection '{config.name}' ({config.vector_dim}-dim, AUTOINDEX)")

    async def delete_collection(self, name: str) -> None:
        try:
            self._client.drop_collection(name)
        except Exception:
            pass

    async def upsert_batch(
        self,
        vectors: list[list[float]],
        ids: list[int],
        payloads: list[dict],
    ) -> None:
        data = [
            {"id": ids[i], "vector": vectors[i], "payload": payloads[i]}
            for i in range(len(ids))
        ]

        def _upsert() -> None:
            self._client.upsert(
                collection_name=self._collection_name,
                data=data,
            )

        try:
            await asyncio.to_thread(_upsert)
        except Exception as e:
            err = str(e).lower()
            if "rate" in err or "429" in err or "throttl" in err:
                raise RateLimitError() from e
            raise

    async def search(
        self,
        query_vector: list[float],
        top_k: int = 10,
    ) -> list[SearchResult]:
        def _search() -> list[SearchResult]:
            results = self._client.search(
                collection_name=self._collection_name,
                data=[query_vector],
                anns_field="vector",
                limit=top_k,
                output_fields=["payload"],
                consistency_level="Strong",
            )
            if not results or not results[0]:
                return []
            return [
                SearchResult(
                    id=int(hit["id"]),
                    score=hit["distance"],
                    payload=hit.get("entity", {}).get("payload"),
                )
                for hit in results[0]
            ]

        try:
            return await asyncio.to_thread(_search)
        except Exception as e:
            err = str(e).lower()
            if "rate" in err or "429" in err or "throttl" in err:
                raise RateLimitError() from e
            raise

    async def count(self) -> int:

        def _count() -> int:
            try:
                res = self._client.query(
                    collection_name=self._collection_name,
                    filter="",
                    output_fields=["count(*)"],
                )
                if res:
                    return res[0].get("count(*)", 0)
            except Exception:
                pass
            try:
                stats = self._client.get_collection_stats(self._collection_name)
                return stats.get("row_count", 0)
            except Exception:
                return 0

        return await asyncio.to_thread(_count)

    def name(self) -> str:
        return "zilliz_cloud"
