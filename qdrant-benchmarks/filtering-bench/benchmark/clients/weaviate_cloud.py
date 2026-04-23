from __future__ import annotations

import logging
import os
import time
import uuid

import weaviate
import weaviate.classes as wvc
from weaviate.classes.config import DataType, Property
from weaviate.classes.query import Filter

from benchmark.clients.base_client import (
    BaseVectorClient,
    CollectionConfig,
    NetworkBaseline,
    RateLimitError,
    SearchResult,
)

log = logging.getLogger(__name__)


def _translate_filter(condition: dict | None) -> Filter | None:
    if condition is None:
        return None

    filters = []
    for cond in condition.get("must", []):
        field = cond["field"]
        if "match" in cond:
            value = cond["match"]
            filters.append(Filter.by_property(field).equal(value))
        elif "match_any" in cond:
            values = cond["match_any"]
            filters.append(Filter.by_property(field).contains_any(values))
        elif "range" in cond:
            r = cond["range"]
            if "gte" in r and "lte" in r:
                filters.append(Filter.by_property(field).greater_or_equal(r["gte"]))
                filters.append(Filter.by_property(field).less_or_equal(r["lte"]))
            elif "gte" in r:
                filters.append(Filter.by_property(field).greater_or_equal(r["gte"]))
            elif "lte" in r:
                filters.append(Filter.by_property(field).less_or_equal(r["lte"]))

    if not filters:
        return None
    if len(filters) == 1:
        return filters[0]
    result = filters[0] & filters[1]
    for f in filters[2:]:
        result = result & f
    return result


def _int_to_uuid(n: int) -> str:
    return str(uuid.UUID(int=n))


def _uuid_to_int(u: str) -> int:
    return uuid.UUID(u).int


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
            auth_credentials=weaviate.auth.AuthApiKey(api_key),
        )
        log.info(f"Connected to Weaviate Cloud at {url}")

    async def disconnect(self) -> None:
        if self._client:
            self._client.close()
            self._client = None

    async def measure_baseline_latency(self) -> NetworkBaseline:

        latencies: list[float] = []
        for _ in range(20):
            start = time.monotonic()
            self._client.collections.list_all()
            latencies.append((time.monotonic() - start) * 1000)
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
            "euclidean": wvc.config.VectorDistances.L2_SQUARED,
            "cosine": wvc.config.VectorDistances.COSINE,
            "dot": wvc.config.VectorDistances.DOT,
        }

        properties = [
            Property(name="tenant_id", data_type=DataType.TEXT, indexFilterable=True, indexSearchable=False),
            Property(name="region", data_type=DataType.TEXT, indexFilterable=True, indexSearchable=False),
            Property(name="country", data_type=DataType.TEXT, indexFilterable=True, indexSearchable=False),
            Property(name="city", data_type=DataType.TEXT, indexFilterable=True, indexSearchable=False),
            Property(name="device_type", data_type=DataType.TEXT, indexFilterable=True, indexSearchable=False),
            Property(name="category_l1", data_type=DataType.TEXT, indexFilterable=True, indexSearchable=False),
            Property(name="category_l2", data_type=DataType.TEXT, indexFilterable=True, indexSearchable=False),
            Property(name="category_l3", data_type=DataType.TEXT, indexFilterable=True, indexSearchable=False),
            Property(name="budget", data_type=DataType.INT, indexFilterable=True),
            Property(name="bid_price", data_type=DataType.NUMBER, indexFilterable=True),
            Property(name="is_active", data_type=DataType.BOOL, indexFilterable=True),
            Property(name="updated_at", data_type=DataType.INT, indexFilterable=True),
            Property(name="quality_score", data_type=DataType.NUMBER, indexFilterable=True),
            Property(name="point_id", data_type=DataType.INT, indexFilterable=True),
        ]

        self._client.collections.create(
            name=config.name,
            properties=properties,
            vectorizer_config=wvc.config.Configure.Vectorizer.none(),
            vector_index_config=wvc.config.Configure.VectorIndex.hnsw(
                distance_metric=distance_map.get(config.distance, wvc.config.VectorDistances.L2_SQUARED),
            ),
        )
        log.info(f"Created collection '{config.name}' ({config.vector_dim}-dim)")

    async def delete_collection(self, name: str) -> None:

        try:
            self._client.collections.delete(name)
        except Exception:
            pass

    async def create_payload_index(self, collection: str, field_name: str, field_type: str) -> None:
        # Weaviate creates indexes via property config at collection creation time
        pass

    async def upsert_batch(
        self,
        vectors: list[list[float]],
        ids: list[int],
        payloads: list[dict],
    ) -> None:

        collection = self._client.collections.get(self._collection_name)

        objects = []
        for i in range(len(ids)):
            props = dict(payloads[i])
            props["point_id"] = ids[i]
            # Weaviate doesn't support list[str] well in filtering; drop tags
            props.pop("tags", None)
            objects.append(
                wvc.data.DataObject(
                    properties=props,
                    vector=vectors[i],
                    uuid=_int_to_uuid(ids[i]),
                )
            )

        try:
            collection.data.insert_many(objects)
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

        collection = self._client.collections.get(self._collection_name)
        try:
            wv_filter = _translate_filter(filter_condition)
            result = collection.query.near_vector(
                near_vector=query_vector,
                limit=top_k,
                filters=wv_filter,
                return_properties=["point_id"],
            )
            return [
                SearchResult(
                    id=obj.properties.get("point_id", 0),
                    score=obj.metadata.distance if obj.metadata.distance else 0.0,
                )
                for obj in result.objects
            ]
        except Exception as e:
            err = str(e).lower()
            if "rate" in err or "429" in err:
                raise RateLimitError() from e
            raise

    async def count(self) -> int:

        collection = self._client.collections.get(self._collection_name)
        result = collection.aggregate.over_all(total_count=True)
        return result.total_count or 0

    def name(self) -> str:
        return "weaviate_cloud"
