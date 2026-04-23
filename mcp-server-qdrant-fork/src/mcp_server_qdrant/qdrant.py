import logging
import uuid
from typing import Any

from pydantic import BaseModel
from qdrant_client import AsyncQdrantClient, models

from mcp_server_qdrant.embeddings.base import EmbeddingProvider
from mcp_server_qdrant.embeddings.multi import MultiEmbeddingProvider
from mcp_server_qdrant.settings import METADATA_PATH

logger = logging.getLogger(__name__)

Metadata = dict[str, Any]
ArbitraryFilter = dict[str, Any]


class Entry(BaseModel):
    """
    A single entry in the Qdrant collection.
    """

    content: str
    metadata: Metadata | None = None


class BatchEntry(BaseModel):
    """
    A single entry for batch operations, with explicit ID.
    """

    id: str
    content: str
    metadata: Metadata | None = None


class CollectionInfo(BaseModel):
    """
    Information about a Qdrant collection.
    """

    exists: bool
    points_count: int | None = None
    vectors_count: int | None = None
    status: str | None = None


class ScrollResult(BaseModel):
    """
    Result of a scroll operation.
    """

    points: list[dict[str, Any]]
    next_offset: str | int | None = None


class MultiVectorEntry(BaseModel):
    """
    Entry for multi-vector storage with explicit ID.
    """

    id: str
    content: str
    metadata: Metadata | None = None


class HybridSearchResult(BaseModel):
    """
    Result from hybrid search with score information.
    """

    id: str
    content: str
    metadata: Metadata | None = None
    score: float
    vector_scores: dict[str, float] | None = None  # Individual scores per vector


class QdrantConnector:
    """
    Encapsulates the connection to a Qdrant server and all the methods to interact with it.
    :param qdrant_url: The URL of the Qdrant server.
    :param qdrant_api_key: The API key to use for the Qdrant server.
    :param collection_name: The name of the default collection to use. If not provided, each tool will require
                            the collection name to be provided.
    :param embedding_provider: The embedding provider to use.
    :param qdrant_local_path: The path to the storage directory for the Qdrant client, if local mode is used.
    """

    def __init__(
        self,
        qdrant_url: str | None,
        qdrant_api_key: str | None,
        collection_name: str | None,
        embedding_provider: EmbeddingProvider,
        qdrant_local_path: str | None = None,
        field_indexes: dict[str, models.PayloadSchemaType] | None = None,
    ):
        self._qdrant_url = qdrant_url.rstrip("/") if qdrant_url else None
        self._qdrant_api_key = qdrant_api_key
        self._default_collection_name = collection_name
        self._embedding_provider = embedding_provider
        self._client = AsyncQdrantClient(
            location=qdrant_url, api_key=qdrant_api_key, path=qdrant_local_path
        )
        self._field_indexes = field_indexes

    async def get_collection_names(self) -> list[str]:
        """
        Get the names of all collections in the Qdrant server.
        :return: A list of collection names.
        """
        response = await self._client.get_collections()
        return [collection.name for collection in response.collections]

    async def store(
        self,
        entry: Entry,
        *,
        collection_name: str | None = None,
        point_id: str | None = None,
    ):
        """
        Store some information in the Qdrant collection, along with the specified metadata.
        :param entry: The entry to store in the Qdrant collection.
        :param collection_name: The name of the collection to store the information in, optional. If not provided,
                                the default collection is used.
        :param point_id: Optional custom ID for the point. If not provided, a UUID will be generated.
        """
        collection_name = collection_name or self._default_collection_name
        assert collection_name is not None
        await self._ensure_collection_exists(collection_name)

        # Embed the document
        # ToDo: instead of embedding text explicitly, use `models.Document`,
        # it should unlock usage of server-side inference.
        embeddings = await self._embedding_provider.embed_documents([entry.content])

        # Add to Qdrant
        vector_name = self._embedding_provider.get_vector_name()
        payload = {"document": entry.content, METADATA_PATH: entry.metadata}

        # Use provided ID or generate UUID
        final_id = point_id if point_id else uuid.uuid4().hex

        await self._client.upsert(
            collection_name=collection_name,
            points=[
                models.PointStruct(
                    id=final_id,
                    vector={vector_name: embeddings[0]},
                    payload=payload,
                )
            ],
        )

    async def store_batch(
        self,
        entries: list[BatchEntry],
        *,
        collection_name: str | None = None,
    ) -> int:
        """
        Store multiple entries in the Qdrant collection in a single batch operation.
        :param entries: List of BatchEntry objects with id, content, and optional metadata.
        :param collection_name: The name of the collection to store in.
        :return: Number of points upserted.
        """
        if not entries:
            return 0

        collection_name = collection_name or self._default_collection_name
        assert collection_name is not None
        await self._ensure_collection_exists(collection_name)

        # Embed all documents in batch
        contents = [e.content for e in entries]
        embeddings = await self._embedding_provider.embed_documents(contents)

        # Build points
        vector_name = self._embedding_provider.get_vector_name()
        points = []
        for i, entry in enumerate(entries):
            payload = {"document": entry.content, METADATA_PATH: entry.metadata}
            points.append(
                models.PointStruct(
                    id=entry.id,
                    vector={vector_name: embeddings[i]},
                    payload=payload,
                )
            )

        # Batch upsert
        await self._client.upsert(
            collection_name=collection_name,
            points=points,
        )

        return len(points)

    async def search(
        self,
        query: str,
        *,
        collection_name: str | None = None,
        limit: int = 10,
        query_filter: models.Filter | None = None,
    ) -> list[Entry]:
        """
        Find points in the Qdrant collection. If there are no entries found, an empty list is returned.
        :param query: The query to use for the search.
        :param collection_name: The name of the collection to search in, optional. If not provided,
                                the default collection is used.
        :param limit: The maximum number of entries to return.
        :param query_filter: The filter to apply to the query, if any.

        :return: A list of entries found.
        """
        collection_name = collection_name or self._default_collection_name
        collection_exists = await self._client.collection_exists(collection_name)
        if not collection_exists:
            return []

        # Embed the query
        # ToDo: instead of embedding text explicitly, use `models.Document`,
        # it should unlock usage of server-side inference.

        query_vector = await self._embedding_provider.embed_query(query)
        vector_name = self._embedding_provider.get_vector_name()

        # Search in Qdrant
        search_results = await self._client.query_points(
            collection_name=collection_name,
            query=query_vector,
            using=vector_name,
            limit=limit,
            query_filter=query_filter,
        )

        return [
            Entry(
                content=result.payload["document"],
                metadata=result.payload.get("metadata"),
            )
            for result in search_results.points
        ]

    async def get_collection_info(
        self,
        collection_name: str | None = None,
    ) -> CollectionInfo:
        """
        Get information about a collection.
        :param collection_name: The name of the collection to get info for.
        :return: CollectionInfo with exists status and stats.
        """
        collection_name = collection_name or self._default_collection_name
        assert collection_name is not None

        collection_exists = await self._client.collection_exists(collection_name)
        if not collection_exists:
            return CollectionInfo(exists=False)

        # Get collection info
        info = await self._client.get_collection(collection_name)
        return CollectionInfo(
            exists=True,
            points_count=info.points_count,
            vectors_count=info.vectors_count,
            status=str(info.status) if info.status else None,
        )

    async def scroll(
        self,
        *,
        collection_name: str | None = None,
        limit: int = 100,
        offset: str | int | None = None,
        query_filter: models.Filter | None = None,
        with_payload: bool | list[str] = True,
    ) -> ScrollResult:
        """
        Scroll through points in the collection with pagination.
        :param collection_name: The name of the collection to scroll.
        :param limit: Maximum number of points to return.
        :param offset: Offset for pagination (from previous scroll result).
        :param query_filter: Optional filter to apply.
        :param with_payload: Whether to include payload (True, False, or list of field names).
        :return: ScrollResult with points and next_offset.
        """
        collection_name = collection_name or self._default_collection_name
        assert collection_name is not None

        collection_exists = await self._client.collection_exists(collection_name)
        if not collection_exists:
            return ScrollResult(points=[], next_offset=None)

        # Perform scroll
        result = await self._client.scroll(
            collection_name=collection_name,
            limit=limit,
            offset=offset,
            scroll_filter=query_filter,
            with_payload=with_payload,
        )

        points_data = []
        for point in result[0]:
            point_dict = {
                "id": point.id,
                "payload": point.payload if point.payload else {},
            }
            points_data.append(point_dict)

        return ScrollResult(
            points=points_data,
            next_offset=result[1],  # next_page_offset
        )

    async def _ensure_collection_exists(self, collection_name: str):
        """
        Ensure that the collection exists, creating it if necessary.
        :param collection_name: The name of the collection to ensure exists.
        """
        collection_exists = await self._client.collection_exists(collection_name)
        if not collection_exists:
            # Create the collection with the appropriate vector size
            vector_size = self._embedding_provider.get_vector_size()

            # Use the vector name as defined in the embedding provider
            vector_name = self._embedding_provider.get_vector_name()
            await self._client.create_collection(
                collection_name=collection_name,
                vectors_config={
                    vector_name: models.VectorParams(
                        size=vector_size,
                        distance=models.Distance.COSINE,
                    )
                },
            )

            # Create payload indexes if configured

            if self._field_indexes:
                for field_name, field_type in self._field_indexes.items():
                    await self._client.create_payload_index(
                        collection_name=collection_name,
                        field_name=field_name,
                        field_schema=field_type,
                    )


class MultiVectorConnector:
    """
    Connector for multi-vector (named vectors) operations.

    Supports storing documents with multiple embedding types and hybrid search
    with Reciprocal Rank Fusion (RRF).

    Example usage:
        connector = MultiVectorConnector(
            qdrant_url="http://localhost:6333",
            collection_name="my-collection",
            vector_configs={"code": "jinaai/jina-embeddings-v2-base-code", "text": "all-MiniLM-L6-v2"}
        )

        # Store with multiple vectors
        await connector.store_multi(entry, collection_name="docs")

        # Search specific vector
        results = await connector.search_single("parse JSON", vector_name="code")

        # Hybrid search with RRF fusion
        results = await connector.search_hybrid("parse JSON", vector_names=["code", "text"])
    """

    def __init__(
        self,
        qdrant_url: str | None,
        qdrant_api_key: str | None,
        collection_name: str | None,
        vector_configs: dict[str, str],  # {vector_name: model_name}
        qdrant_local_path: str | None = None,
        field_indexes: dict[str, models.PayloadSchemaType] | None = None,
    ):
        self._qdrant_url = qdrant_url.rstrip("/") if qdrant_url else None
        self._qdrant_api_key = qdrant_api_key
        self._default_collection_name = collection_name
        self._multi_provider = MultiEmbeddingProvider(vector_configs)
        self._client = AsyncQdrantClient(
            location=qdrant_url, api_key=qdrant_api_key, path=qdrant_local_path
        )
        self._field_indexes = field_indexes
        self._vector_configs = vector_configs

    def get_vector_names(self) -> list[str]:
        """Get all configured vector names."""
        return self._multi_provider.get_vector_names()

    async def store_multi(
        self,
        entry: MultiVectorEntry,
        *,
        collection_name: str | None = None,
    ):
        """
        Store a document with embeddings from ALL configured vector models.

        :param entry: Entry with id, content, and optional metadata.
        :param collection_name: Collection to store in.
        """
        collection_name = collection_name or self._default_collection_name
        assert collection_name is not None
        await self._ensure_multi_collection_exists(collection_name)

        # Embed with all models
        all_embeddings = await self._multi_provider.embed_all([entry.content])

        # Build vectors dict
        vectors = {}
        for vector_name, embeddings in all_embeddings.items():
            vectors[vector_name] = embeddings[0]

        # Store point
        payload = {"document": entry.content, METADATA_PATH: entry.metadata}
        await self._client.upsert(
            collection_name=collection_name,
            points=[
                models.PointStruct(
                    id=entry.id,
                    vector=vectors,
                    payload=payload,
                )
            ],
        )

    async def store_multi_batch(
        self,
        entries: list[MultiVectorEntry],
        *,
        collection_name: str | None = None,
    ) -> int:
        """
        Store multiple documents with embeddings from ALL configured vector models.

        :param entries: List of entries with id, content, and optional metadata.
        :param collection_name: Collection to store in.
        :return: Number of points stored.
        """
        if not entries:
            return 0

        collection_name = collection_name or self._default_collection_name
        assert collection_name is not None
        await self._ensure_multi_collection_exists(collection_name)

        # Embed all documents with all models
        contents = [e.content for e in entries]
        all_embeddings = await self._multi_provider.embed_all(contents)

        # Build points
        points = []
        for i, entry in enumerate(entries):
            vectors = {}
            for vector_name, embeddings in all_embeddings.items():
                vectors[vector_name] = embeddings[i]

            payload = {"document": entry.content, METADATA_PATH: entry.metadata}
            points.append(
                models.PointStruct(
                    id=entry.id,
                    vector=vectors,
                    payload=payload,
                )
            )

        # Batch upsert
        await self._client.upsert(
            collection_name=collection_name,
            points=points,
        )

        return len(points)

    async def search_single(
        self,
        query: str,
        vector_name: str,
        *,
        collection_name: str | None = None,
        limit: int = 10,
        query_filter: models.Filter | None = None,
    ) -> list[HybridSearchResult]:
        """
        Search using a specific named vector.

        :param query: Query string.
        :param vector_name: Which vector to search (e.g., "code" or "text").
        :param collection_name: Collection to search.
        :param limit: Max results.
        :param query_filter: Optional filter.
        :return: List of results with scores.
        """
        collection_name = collection_name or self._default_collection_name
        collection_exists = await self._client.collection_exists(collection_name)
        if not collection_exists:
            return []

        # Embed query with specified model
        query_vector = await self._multi_provider.embed_query(vector_name, query)

        # Search
        results = await self._client.query_points(
            collection_name=collection_name,
            query=query_vector,
            using=vector_name,
            limit=limit,
            query_filter=query_filter,
            with_payload=True,
        )

        return [
            HybridSearchResult(
                id=str(r.id),
                content=r.payload.get("document", ""),
                metadata=r.payload.get(METADATA_PATH),
                score=r.score,
                vector_scores={vector_name: r.score},
            )
            for r in results.points
        ]

    async def search_hybrid(
        self,
        query: str,
        vector_names: list[str] | None = None,
        *,
        collection_name: str | None = None,
        limit: int = 10,
        query_filter: models.Filter | None = None,
        fusion_method: str = "rrf",  # "rrf" or "dbsf"
    ) -> list[HybridSearchResult]:
        """
        Hybrid search across multiple named vectors with fusion.

        Uses Qdrant's native prefetch + fusion for efficient hybrid search.

        :param query: Query string.
        :param vector_names: Which vectors to search (default: all).
        :param collection_name: Collection to search.
        :param limit: Max results.
        :param query_filter: Optional filter.
        :param fusion_method: "rrf" (Reciprocal Rank Fusion) or "dbsf" (Distribution-Based Score Fusion).
        :return: List of results with combined scores.
        """
        collection_name = collection_name or self._default_collection_name
        collection_exists = await self._client.collection_exists(collection_name)
        if not collection_exists:
            return []

        # Use all vectors if none specified
        if vector_names is None:
            vector_names = self.get_vector_names()

        if len(vector_names) == 1:
            # Single vector search, no fusion needed
            return await self.search_single(
                query,
                vector_names[0],
                collection_name=collection_name,
                limit=limit,
                query_filter=query_filter,
            )

        # Build prefetch queries for each vector
        prefetch_queries = []
        for vector_name in vector_names:
            query_vector = await self._multi_provider.embed_query(vector_name, query)
            prefetch_queries.append(
                models.Prefetch(
                    query=query_vector,
                    using=vector_name,
                    limit=limit * 2,  # Fetch more for fusion
                    filter=query_filter,
                )
            )

        # Select fusion method
        if fusion_method == "dbsf":
            fusion = models.Fusion.DBSF
        else:
            fusion = models.Fusion.RRF

        # Execute hybrid query with fusion
        results = await self._client.query_points(
            collection_name=collection_name,
            prefetch=prefetch_queries,
            query=fusion,
            limit=limit,
            with_payload=True,
        )

        return [
            HybridSearchResult(
                id=str(r.id),
                content=r.payload.get("document", ""),
                metadata=r.payload.get(METADATA_PATH),
                score=r.score,
                vector_scores=None,  # Fusion doesn't provide individual scores
            )
            for r in results.points
        ]

    async def _ensure_multi_collection_exists(self, collection_name: str):
        """
        Ensure collection exists with all named vector configurations.
        """
        collection_exists = await self._client.collection_exists(collection_name)
        if not collection_exists:
            # Build vectors config for all named vectors
            vectors_config = {}
            for vector_name in self._multi_provider.get_vector_names():
                vector_size = self._multi_provider.get_vector_size(vector_name)
                vectors_config[vector_name] = models.VectorParams(
                    size=vector_size,
                    distance=models.Distance.COSINE,
                )

            await self._client.create_collection(
                collection_name=collection_name,
                vectors_config=vectors_config,
            )

            # Create payload indexes if configured
            if self._field_indexes:
                for field_name, field_type in self._field_indexes.items():
                    await self._client.create_payload_index(
                        collection_name=collection_name,
                        field_name=field_name,
                        field_schema=field_type,
                    )
