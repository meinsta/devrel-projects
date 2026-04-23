"""Qdrant memory store with vector embeddings."""

import time
import uuid
from typing import Optional

from fastembed import TextEmbedding
from qdrant_client import QdrantClient
from qdrant_client.http import models as qm


class QdrantMemoryStore:
    """Vector store for coding memories backed by Qdrant."""

    def __init__(
        self,
        url: str,
        api_key: Optional[str],
        collection: str,
        embedding_model: str,
    ):
        self.collection = collection
        self.embedder = TextEmbedding(model_name=embedding_model)
        self.client = QdrantClient(url=url, api_key=api_key)

        # Infer vector dimension from the embedding model
        dim = len(list(self.embedder.embed(["dimension probe"]))[0])
        self._ensure_collection(dim)

    def _ensure_collection(self, dim: int) -> None:
        """Create collection if it doesn't exist."""
        if not self.client.collection_exists(self.collection):
            self.client.create_collection(
                collection_name=self.collection,
                vectors_config=qm.VectorParams(size=dim, distance=qm.Distance.COSINE),
            )
            # Create payload indexes for efficient filtering
            self.client.create_payload_index(
                collection_name=self.collection,
                field_name="repo_id",
                field_schema=qm.PayloadSchemaType.KEYWORD,
            )
            self.client.create_payload_index(
                collection_name=self.collection,
                field_name="kind",
                field_schema=qm.PayloadSchemaType.KEYWORD,
            )
            self.client.create_payload_index(
                collection_name=self.collection,
                field_name="expires_at",
                field_schema=qm.PayloadSchemaType.INTEGER,
            )

    def remember(
        self,
        repo_id: str,
        kind: str,
        text: str,
        tags: list[str],
        source_paths: list[str],
        session_id: Optional[str],
        ttl_days: Optional[int],
        git_commit: Optional[str] = None,
        git_branch: Optional[str] = None,
    ) -> str:
        """
        Store a memory in Qdrant.

        Returns:
            The ID of the stored memory point.
        """
        now = int(time.time())
        expires_at = (now + ttl_days * 86400) if ttl_days else None

        # Generate embedding
        vec = list(self.embedder.embed([text]))[0]
        point_id = str(uuid.uuid4())

        payload = {
            "repo_id": repo_id,
            "kind": kind,
            "text": text,
            "tags": tags,
            "source_paths": source_paths,
            "session_id": session_id,
            "created_at": now,
            "expires_at": expires_at,
            # Provenance fields
            "git_commit": git_commit,
            "git_branch": git_branch,
            "verified_at": now,  # Track when memory was last verified as accurate
        }

        self.client.upsert(
            collection_name=self.collection,
            points=[qm.PointStruct(id=point_id, vector=vec.tolist(), payload=payload)],
        )

        return point_id

    def recall(
        self,
        repo_id: str,
        query: str,
        kinds: list[str],
        limit: int,
    ) -> list[dict]:
        """
        Search for relevant memories.

        Returns:
            List of memory hits with scores and metadata.
        """
        now = int(time.time())
        qvec = list(self.embedder.embed([query]))[0]

        # Build filter: repo_id matches AND kind is in list
        must_conditions = [
            qm.FieldCondition(key="repo_id", match=qm.MatchValue(value=repo_id)),
            qm.FieldCondition(key="kind", match=qm.MatchAny(any=kinds)),
        ]

        # TTL filter: expires_at is null OR expires_at > now
        not_expired = qm.Filter(
            should=[
                qm.IsNullCondition(is_null=qm.PayloadField(key="expires_at")),
                qm.FieldCondition(key="expires_at", range=qm.Range(gt=now)),
            ]
        )

        # Combine filters
        query_filter = qm.Filter(
            must=must_conditions,
            should=not_expired.should,
        )

        results = self.client.search(
            collection_name=self.collection,
            query_vector=qvec.tolist(),
            limit=limit,
            query_filter=query_filter,
            with_payload=True,
        )

        hits = []
        for r in results:
            p = r.payload or {}
            hits.append({
                "id": r.id,
                "score": r.score,
                "kind": p.get("kind"),
                "text": p.get("text"),
                "tags": p.get("tags", []),
                "source_paths": p.get("source_paths", []),
                "session_id": p.get("session_id"),
                "created_at": p.get("created_at"),
                "git_commit": p.get("git_commit"),
                "git_branch": p.get("git_branch"),
                "verified_at": p.get("verified_at"),
            })

        return hits

    def delete(self, point_id: str) -> bool:
        """Delete a specific memory by ID."""
        self.client.delete(
            collection_name=self.collection,
            points_selector=qm.PointIdsList(points=[point_id]),
        )
        return True

    def list_recent(
        self,
        repo_id: str,
        kinds: Optional[list[str]] = None,
        limit: int = 20,
    ) -> list[dict]:
        """
        List recent memories for a repo, ordered by creation time.

        Returns:
            List of recent memories.
        """
        now = int(time.time())

        must_conditions = [
            qm.FieldCondition(key="repo_id", match=qm.MatchValue(value=repo_id)),
        ]

        if kinds:
            must_conditions.append(
                qm.FieldCondition(key="kind", match=qm.MatchAny(any=kinds))
            )

        # TTL filter
        not_expired = qm.Filter(
            should=[
                qm.IsNullCondition(is_null=qm.PayloadField(key="expires_at")),
                qm.FieldCondition(key="expires_at", range=qm.Range(gt=now)),
            ]
        )

        query_filter = qm.Filter(
            must=must_conditions,
            should=not_expired.should,
        )

        # Scroll through points, ordered by created_at descending
        results, _ = self.client.scroll(
            collection_name=self.collection,
            scroll_filter=query_filter,
            limit=limit,
            with_payload=True,
            order_by=qm.OrderBy(key="created_at", direction=qm.Direction.DESC),
        )

        memories = []
        for r in results:
            p = r.payload or {}
            memories.append({
                "id": r.id,
                "kind": p.get("kind"),
                "text": p.get("text"),
                "tags": p.get("tags", []),
                "source_paths": p.get("source_paths", []),
                "session_id": p.get("session_id"),
                "created_at": p.get("created_at"),
                "git_commit": p.get("git_commit"),
                "git_branch": p.get("git_branch"),
                "verified_at": p.get("verified_at"),
            })

        return memories
