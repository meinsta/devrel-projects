"""Qdrant store for memory CRUD operations.

Handles all Qdrant interactions:
- Collection creation/management
- Upsert, search, list, delete
- Filter building for repo_id, kinds, tags, since_days
"""

import os
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict, Any

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
    MatchAny,
    Range,
)

from .schema import MemoryRecord
from .embedder import Embedder

# Default collection name
DEFAULT_COLLECTION = "cortex_memory"


class QdrantMemoryStore:
    """Qdrant-backed memory store.

    Provides:
    - upsert(): Store a memory with embedding
    - search(): Vector search with filters
    - list_recent(): Get recent memories by created_at
    - delete(): Remove a memory by ID
    - get(): Get a single memory by ID
    """

    def __init__(
        self,
        url: Optional[str] = None,
        api_key: Optional[str] = None,
        collection: Optional[str] = None,
        embedder: Optional[Embedder] = None,
    ):
        """Initialize store with Qdrant connection.

        Args:
            url: Qdrant URL (default: QDRANT_URL env var)
            api_key: Qdrant API key (default: QDRANT_API_KEY env var)
            collection: Collection name (default: cortex_memory)
            embedder: Embedder instance (default: creates new one)
        """
        self.url = url or os.environ.get("QDRANT_URL")
        self.api_key = api_key or os.environ.get("QDRANT_API_KEY")
        self.collection = collection or os.environ.get("QDRANT_COLLECTION", DEFAULT_COLLECTION)

        if not self.url:
            raise ValueError("QDRANT_URL environment variable is required")

        # Initialize client
        self.client = QdrantClient(url=self.url, api_key=self.api_key)

        # Initialize embedder
        self.embedder = embedder or Embedder()

        # Ensure collection exists
        self._ensure_collection()

    def _ensure_collection(self) -> None:
        """Create collection if it doesn't exist."""
        collections = self.client.get_collections().collections
        exists = any(c.name == self.collection for c in collections)

        if not exists:
            self.client.create_collection(
                collection_name=self.collection,
                vectors_config=VectorParams(
                    size=self.embedder.dimension,
                    distance=Distance.COSINE,
                ),
            )

    def upsert(self, record: MemoryRecord) -> str:
        """Store a memory record with its embedding.

        Args:
            record: MemoryRecord to store

        Returns:
            The record ID
        """
        # Embed the text
        vector = self.embedder.embed(record.text)

        # Upsert to Qdrant
        self.client.upsert(
            collection_name=self.collection,
            points=[
                PointStruct(
                    id=record.id,
                    vector=vector,
                    payload=record.to_payload(),
                )
            ],
        )

        return record.id

    def search(
        self,
        query: str,
        repo_id: str,
        kinds: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
        since_days: Optional[int] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Vector search for memories.

        Args:
            query: Search query text
            repo_id: Filter by repo
            kinds: Filter by memory kinds
            tags: Filter by tags (any match)
            since_days: Only memories from last N days
            limit: Max results

        Returns:
            List of dicts with memory + score
        """
        # Embed query
        query_vector = self.embedder.embed(query)

        # Build filter
        filter_conditions = [
            FieldCondition(key="repo_id", match=MatchValue(value=repo_id))
        ]

        if kinds:
            filter_conditions.append(
                FieldCondition(key="kind", match=MatchAny(any=kinds))
            )

        if tags:
            filter_conditions.append(
                FieldCondition(key="tags", match=MatchAny(any=tags))
            )

        if since_days:
            cutoff = datetime.now(timezone.utc) - timedelta(days=since_days)
            filter_conditions.append(
                FieldCondition(
                    key="created_at",
                    range=Range(gte=cutoff.isoformat()),
                )
            )

        # Search
        results = self.client.search(
            collection_name=self.collection,
            query_vector=query_vector,
            query_filter=Filter(must=filter_conditions),
            limit=limit,
            with_payload=True,
        )

        # Convert to dicts, filter expired
        memories = []
        for hit in results:
            record = MemoryRecord.from_payload(hit.id, hit.payload)
            if not record.is_expired():
                memories.append({
                    **record.to_dict(),
                    "score": hit.score,
                })

        return memories

    def list_recent(
        self,
        repo_id: str,
        kind: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """List recent memories ordered by created_at.

        Args:
            repo_id: Filter by repo
            kind: Optional filter by single kind
            limit: Max results

        Returns:
            List of memory dicts (newest first)
        """
        # Build filter
        filter_conditions = [
            FieldCondition(key="repo_id", match=MatchValue(value=repo_id))
        ]

        if kind:
            filter_conditions.append(
                FieldCondition(key="kind", match=MatchValue(value=kind))
            )

        # Scroll with filter (Qdrant doesn't have direct order by payload)
        # We'll fetch more and sort client-side
        results, _ = self.client.scroll(
            collection_name=self.collection,
            scroll_filter=Filter(must=filter_conditions),
            limit=limit * 2,  # Fetch extra for expired filtering
            with_payload=True,
            with_vectors=False,
        )

        # Convert, filter expired, sort by created_at
        memories = []
        for point in results:
            record = MemoryRecord.from_payload(point.id, point.payload)
            if not record.is_expired():
                memories.append(record.to_dict())

        # Sort by created_at descending
        memories.sort(key=lambda x: x.get("created_at", ""), reverse=True)

        return memories[:limit]

    def delete(self, memory_id: str) -> bool:
        """Delete a memory by ID.

        Args:
            memory_id: Memory ID to delete

        Returns:
            True if deleted, False if not found
        """
        try:
            self.client.delete(
                collection_name=self.collection,
                points_selector=[memory_id],
            )
            return True
        except Exception:
            return False

    def get(self, memory_id: str) -> Optional[MemoryRecord]:
        """Get a single memory by ID.

        Args:
            memory_id: Memory ID

        Returns:
            MemoryRecord or None if not found
        """
        try:
            results = self.client.retrieve(
                collection_name=self.collection,
                ids=[memory_id],
                with_payload=True,
            )
            if results:
                return MemoryRecord.from_payload(results[0].id, results[0].payload)
            return None
        except Exception:
            return None

    def health(self) -> dict:
        """Check store health."""
        try:
            info = self.client.get_collection(self.collection)
            return {
                "status": "healthy",
                "url": self.url[:50] + "..." if len(self.url) > 50 else self.url,
                "collection": self.collection,
                "points_count": info.points_count,
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "url": self.url[:50] + "..." if self.url and len(self.url) > 50 else self.url,
                "collection": self.collection,
                "error": str(e),
            }


# Singleton instance
_store: Optional[QdrantMemoryStore] = None


def get_store() -> QdrantMemoryStore:
    """Get the global store instance."""
    global _store
    if _store is None:
        _store = QdrantMemoryStore()
    return _store
