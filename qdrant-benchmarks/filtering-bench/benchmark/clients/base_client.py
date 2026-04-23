from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class SearchResult:
    id: int
    score: float
    payload: dict | None = None


@dataclass
class CollectionConfig:
    name: str
    vector_dim: int
    distance: str  # "euclidean" | "cosine" | "dot"
    payload_indexes: list[PayloadIndexConfig] | None = None


@dataclass
class PayloadIndexConfig:
    field_name: str
    field_type: str  # "keyword" | "integer" | "float" | "bool" | "geo"


@dataclass
class NetworkBaseline:
    ping_ms: float
    empty_request_ms: float


class RateLimitError(Exception):
    def __init__(self, retry_after_s: float | None = None):
        self.retry_after_s = retry_after_s
        super().__init__(
            f"Rate limited (retry_after={retry_after_s}s)"
            if retry_after_s
            else "Rate limited"
        )


class BaseVectorClient(ABC):

    @abstractmethod
    async def connect(self) -> None:
        ...

    @abstractmethod
    async def disconnect(self) -> None:
        ...

    @abstractmethod
    async def measure_baseline_latency(self) -> NetworkBaseline:
        ...

    @abstractmethod
    async def create_collection(self, config: CollectionConfig) -> None:
        ...

    @abstractmethod
    async def delete_collection(self, name: str) -> None:
        ...

    @abstractmethod
    async def create_payload_index(self, collection: str, field_name: str, field_type: str) -> None:
        ...

    @abstractmethod
    async def upsert_batch(
        self,
        vectors: list[list[float]],
        ids: list[int],
        payloads: list[dict],
    ) -> None:
        ...

    @abstractmethod
    async def search(
        self,
        query_vector: list[float],
        top_k: int = 10,
        filter_condition: dict | None = None,
    ) -> list[SearchResult]:
        ...

    @abstractmethod
    async def count(self) -> int:
        ...

    @abstractmethod
    def name(self) -> str:
        ...
