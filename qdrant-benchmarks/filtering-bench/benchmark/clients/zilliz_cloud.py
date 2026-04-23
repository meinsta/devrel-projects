from __future__ import annotations

import logging
import os
import time

from pymilvus import MilvusClient

from benchmark.clients.base_client import (
    BaseVectorClient,
    CollectionConfig,
    NetworkBaseline,
    RateLimitError,
    SearchResult,
)

log = logging.getLogger(__name__)

# Milvus field schema for the filter benchmark
MILVUS_FILTER_SCHEMA = {
    "tenant_id": "VARCHAR(32)",
    "region": "VARCHAR(32)",
    "country": "VARCHAR(32)",
    "city": "VARCHAR(64)",
    "device_type": "VARCHAR(16)",
    "category_l1": "VARCHAR(32)",
    "category_l2": "VARCHAR(32)",
    "category_l3": "VARCHAR(64)",
    "budget": "INT64",
    "bid_price": "DOUBLE",
    "is_active": "BOOL",
    "updated_at": "INT64",
    "quality_score": "DOUBLE",
}


def _translate_filter(condition: dict | None) -> str:
    if condition is None:
        return ""

    clauses = []
    for cond in condition.get("must", []):
        field = cond["field"]
        if "match" in cond:
            value = cond["match"]
            if isinstance(value, bool):
                clauses.append(f"{field} == {str(value).lower()}")
            elif isinstance(value, str):
                clauses.append(f'{field} == "{value}"')
            elif isinstance(value, (int, float)):
                clauses.append(f"{field} == {value}")
        elif "match_any" in cond:
            values = cond["match_any"]
            if all(isinstance(v, str) for v in values):
                vals_str = ", ".join(f'"{v}"' for v in values)
            else:
                vals_str = ", ".join(str(v) for v in values)
            clauses.append(f"{field} in [{vals_str}]")
        elif "range" in cond:
            r = cond["range"]
            if "gte" in r:
                clauses.append(f"{field} >= {r['gte']}")
            if "lte" in r:
                clauses.append(f"{field} <= {r['lte']}")

    return " and ".join(clauses) if clauses else ""


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
        log.info(f"Connected to Zilliz Cloud ({len(collections)} collections)")

    async def disconnect(self) -> None:
        if self._client:
            self._client.close()
            self._client = None

    async def measure_baseline_latency(self) -> NetworkBaseline:

        latencies: list[float] = []
        for _ in range(20):
            start = time.monotonic()
            self._client.list_collections()
            latencies.append((time.monotonic() - start) * 1000)
        measured = sorted(latencies[5:])
        median_ms = measured[len(measured) // 2]
        return NetworkBaseline(ping_ms=median_ms, empty_request_ms=median_ms)

    async def create_collection(self, config: CollectionConfig) -> None:

        self._collection_name = config.name

        try:
            self._client.drop_collection(config.name)
        except Exception:
            pass

        from pymilvus import CollectionSchema, DataType, FieldSchema

        fields = [
            FieldSchema(name="id", dtype=DataType.INT64, is_primary=True),
            FieldSchema(name="vector", dtype=DataType.FLOAT_VECTOR, dim=config.vector_dim),
        ]

        # Add payload fields for filtering
        dtype_map = {
            "VARCHAR(32)": (DataType.VARCHAR, {"max_length": 32}),
            "VARCHAR(64)": (DataType.VARCHAR, {"max_length": 64}),
            "VARCHAR(16)": (DataType.VARCHAR, {"max_length": 16}),
            "INT64": (DataType.INT64, {}),
            "DOUBLE": (DataType.DOUBLE, {}),
            "BOOL": (DataType.BOOL, {}),
        }

        for field_name, field_type_str in MILVUS_FILTER_SCHEMA.items():
            dtype, params = dtype_map.get(field_type_str, (DataType.VARCHAR, {"max_length": 64}))
            fields.append(FieldSchema(name=field_name, dtype=dtype, **params))

        schema = CollectionSchema(fields=fields)

        distance_map = {
            "euclidean": "L2",
            "cosine": "COSINE",
            "dot": "IP",
        }

        self._client.create_collection(
            collection_name=config.name,
            schema=schema,
        )

        # Create vector index
        index_params = self._client.prepare_index_params()
        index_params.add_index(
            field_name="vector",
            index_type="AUTOINDEX",
            metric_type=distance_map.get(config.distance, "L2"),
        )
        self._client.create_index(collection_name=config.name, index_params=index_params)

        self._client.load_collection(config.name)
        log.info(f"Created collection '{config.name}' ({config.vector_dim}-dim)")

    async def delete_collection(self, name: str) -> None:

        try:
            self._client.drop_collection(name)
        except Exception:
            pass

    async def create_payload_index(self, collection: str, field_name: str, field_type: str) -> None:
        # Milvus creates scalar indexes automatically or via index_params

        try:
            index_params = self._client.prepare_index_params()
            index_params.add_index(field_name=field_name, index_type="AUTOINDEX")
            self._client.create_index(collection_name=collection, index_params=index_params)
            log.info(f"Created scalar index: {field_name}")
        except Exception as e:
            log.debug(f"Scalar index creation for {field_name}: {e}")

    async def upsert_batch(
        self,
        vectors: list[list[float]],
        ids: list[int],
        payloads: list[dict],
    ) -> None:

        data = []
        for i in range(len(ids)):
            row = {"id": ids[i], "vector": vectors[i]}
            row.update(payloads[i])
            # Milvus doesn't support list fields in simple insert; flatten tags
            if "tags" in row:
                del row["tags"]
            data.append(row)
        try:
            self._client.upsert(collection_name=self._collection_name, data=data)
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
            filter_expr = _translate_filter(filter_condition)
            results = self._client.search(
                collection_name=self._collection_name,
                data=[query_vector],
                limit=top_k,
                output_fields=["id"],
                filter=filter_expr if filter_expr else None,
            )
            if not results or not results[0]:
                return []
            return [
                SearchResult(id=int(hit["id"]), score=float(hit["distance"]))
                for hit in results[0]
            ]
        except Exception as e:
            err = str(e).lower()
            if "rate" in err or "429" in err:
                raise RateLimitError() from e
            raise

    async def count(self) -> int:

        stats = self._client.get_collection_stats(self._collection_name)
        return int(stats.get("row_count", 0))

    def name(self) -> str:
        return "zilliz_cloud"
