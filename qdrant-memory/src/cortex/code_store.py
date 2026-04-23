"""Qdrant code store with hybrid search (sparse BM25 + dense embeddings)."""

import time
import uuid
from typing import Literal, Optional

from fastembed import SparseTextEmbedding, TextEmbedding
from qdrant_client import QdrantClient
from qdrant_client.http import models as qm


SymbolKind = Literal[
    "file", "module", "class", "function", "method", "variable",
    "constant", "interface", "enum", "struct", "type", "import"
]


class QdrantCodeStore:
    """
    Vector store for code with hybrid search.

    Uses:
    - Dense vectors (all-MiniLM-L6-v2) for semantic search
    - Sparse vectors (BM25) for keyword/exact matching
    - RRF fusion for combining results
    """

    def __init__(
        self,
        url: str,
        api_key: Optional[str],
        collection: str = "code_index",
        dense_model: str = "sentence-transformers/all-MiniLM-L6-v2",
        sparse_model: str = "Qdrant/bm25",
    ):
        self.collection = collection
        self.client = QdrantClient(url=url, api_key=api_key)

        # Initialize embedding models
        self.dense_embedder = TextEmbedding(model_name=dense_model)
        self.sparse_embedder = SparseTextEmbedding(model_name=sparse_model)

        # Get vector dimensions
        self._dense_dim = len(list(self.dense_embedder.embed(["dim"]))[0])
        self._ensure_collection()

    def _ensure_collection(self) -> None:
        """Create collection with hybrid vector config if it doesn't exist."""
        if self.client.collection_exists(self.collection):
            return

        self.client.create_collection(
            collection_name=self.collection,
            vectors_config={
                "dense": qm.VectorParams(
                    size=self._dense_dim,
                    distance=qm.Distance.COSINE,
                ),
            },
            sparse_vectors_config={
                "sparse": qm.SparseVectorParams(
                    modifier=qm.Modifier.IDF,  # BM25-style IDF weighting
                ),
            },
        )

        # Create indexes for efficient filtering
        for field in ["repo_id", "file_path", "symbol_kind", "symbol_name", "language"]:
            self.client.create_payload_index(
                collection_name=self.collection,
                field_name=field,
                field_schema=qm.PayloadSchemaType.KEYWORD,
            )
        self.client.create_payload_index(
            collection_name=self.collection,
            field_name="indexed_at",
            field_schema=qm.PayloadSchemaType.INTEGER,
        )

    def _embed_dense(self, text: str) -> list[float]:
        """Generate dense embedding."""
        return list(self.dense_embedder.embed([text]))[0].tolist()

    def _embed_sparse(self, text: str) -> tuple[list[int], list[float]]:
        """Generate sparse BM25 embedding."""
        sparse = list(self.sparse_embedder.embed([text]))[0]
        return sparse.indices.tolist(), sparse.values.tolist()

    def index_chunk(
        self,
        repo_id: str,
        file_path: str,
        content: str,
        language: str,
        symbol_kind: SymbolKind,
        symbol_name: Optional[str] = None,
        start_line: int = 0,
        end_line: int = 0,
        parent_symbol: Optional[str] = None,
        docstring: Optional[str] = None,
        signature: Optional[str] = None,
    ) -> str:
        """
        Index a code chunk (function, class, or file segment).

        Returns the point ID.
        """
        point_id = str(uuid.uuid4())
        now = int(time.time())

        # Create searchable text combining code + metadata
        search_text = content
        if symbol_name:
            search_text = f"{symbol_name} {search_text}"
        if docstring:
            search_text = f"{docstring} {search_text}"
        if signature:
            search_text = f"{signature} {search_text}"

        # Generate embeddings
        dense_vec = self._embed_dense(search_text)
        sparse_indices, sparse_values = self._embed_sparse(search_text)

        payload = {
            "repo_id": repo_id,
            "file_path": file_path,
            "content": content,
            "language": language,
            "symbol_kind": symbol_kind,
            "symbol_name": symbol_name,
            "start_line": start_line,
            "end_line": end_line,
            "parent_symbol": parent_symbol,
            "docstring": docstring,
            "signature": signature,
            "indexed_at": now,
        }

        self.client.upsert(
            collection_name=self.collection,
            points=[
                qm.PointStruct(
                    id=point_id,
                    vector={
                        "dense": dense_vec,
                        "sparse": qm.SparseVector(
                            indices=sparse_indices,
                            values=sparse_values,
                        ),
                    },
                    payload=payload,
                )
            ],
        )

        return point_id

    def search_hybrid(
        self,
        query: str,
        repo_id: Optional[str] = None,
        file_path: Optional[str] = None,
        path_prefix: Optional[str] = None,
        symbol_kinds: Optional[list[SymbolKind]] = None,
        language: Optional[str] = None,
        limit: int = 10,
        score_threshold: float = 0.0,
    ) -> list[dict]:
        """
        Hybrid search combining dense semantic + sparse keyword search.

        Uses Reciprocal Rank Fusion (RRF) to combine results.
        """
        # Build filter conditions
        must_conditions = []
        if repo_id:
            must_conditions.append(
                qm.FieldCondition(key="repo_id", match=qm.MatchValue(value=repo_id))
            )
        if path_prefix:
            # Filter by path prefix (e.g., "src/", "tests/")
            must_conditions.append(
                qm.FieldCondition(
                    key="file_path",
                    match=qm.MatchText(text=path_prefix)
                )
            )
        if file_path:
            must_conditions.append(
                qm.FieldCondition(key="file_path", match=qm.MatchValue(value=file_path))
            )
        if symbol_kinds:
            must_conditions.append(
                qm.FieldCondition(key="symbol_kind", match=qm.MatchAny(any=symbol_kinds))
            )
        if language:
            must_conditions.append(
                qm.FieldCondition(key="language", match=qm.MatchValue(value=language))
            )

        query_filter = qm.Filter(must=must_conditions) if must_conditions else None

        # Generate query embeddings
        dense_vec = self._embed_dense(query)
        sparse_indices, sparse_values = self._embed_sparse(query)

        # Hybrid search with RRF fusion
        results = self.client.query_points(
            collection_name=self.collection,
            prefetch=[
                qm.Prefetch(
                    query=dense_vec,
                    using="dense",
                    limit=limit * 2,
                    filter=query_filter,
                ),
                qm.Prefetch(
                    query=qm.SparseVector(indices=sparse_indices, values=sparse_values),
                    using="sparse",
                    limit=limit * 2,
                    filter=query_filter,
                ),
            ],
            query=qm.FusionQuery(fusion=qm.Fusion.RRF),
            limit=limit,
            with_payload=True,
            score_threshold=score_threshold,
        )

        hits = []
        for point in results.points:
            p = point.payload or {}
            hits.append({
                "id": point.id,
                "score": point.score,
                "file_path": p.get("file_path"),
                "content": p.get("content"),
                "language": p.get("language"),
                "symbol_kind": p.get("symbol_kind"),
                "symbol_name": p.get("symbol_name"),
                "start_line": p.get("start_line"),
                "end_line": p.get("end_line"),
                "parent_symbol": p.get("parent_symbol"),
                "docstring": p.get("docstring"),
                "signature": p.get("signature"),
            })

        return hits

    def search_dense_only(
        self,
        query: str,
        repo_id: Optional[str] = None,
        limit: int = 10,
    ) -> list[dict]:
        """Pure semantic search (dense vectors only)."""
        must_conditions = []
        if repo_id:
            must_conditions.append(
                qm.FieldCondition(key="repo_id", match=qm.MatchValue(value=repo_id))
            )

        query_filter = qm.Filter(must=must_conditions) if must_conditions else None
        dense_vec = self._embed_dense(query)

        results = self.client.search(
            collection_name=self.collection,
            query_vector=("dense", dense_vec),
            limit=limit,
            query_filter=query_filter,
            with_payload=True,
        )

        return [self._point_to_dict(r) for r in results]

    def search_sparse_only(
        self,
        query: str,
        repo_id: Optional[str] = None,
        limit: int = 10,
    ) -> list[dict]:
        """Pure keyword search (sparse BM25 only)."""
        must_conditions = []
        if repo_id:
            must_conditions.append(
                qm.FieldCondition(key="repo_id", match=qm.MatchValue(value=repo_id))
            )

        query_filter = qm.Filter(must=must_conditions) if must_conditions else None
        sparse_indices, sparse_values = self._embed_sparse(query)

        results = self.client.search(
            collection_name=self.collection,
            query_vector=("sparse", qm.SparseVector(indices=sparse_indices, values=sparse_values)),
            limit=limit,
            query_filter=query_filter,
            with_payload=True,
        )

        return [self._point_to_dict(r) for r in results]

    def find_symbol(
        self,
        symbol_name: str,
        repo_id: Optional[str] = None,
        symbol_kinds: Optional[list[SymbolKind]] = None,
    ) -> list[dict]:
        """Find symbol definitions by exact name."""
        must_conditions = [
            qm.FieldCondition(key="symbol_name", match=qm.MatchValue(value=symbol_name))
        ]
        if repo_id:
            must_conditions.append(
                qm.FieldCondition(key="repo_id", match=qm.MatchValue(value=repo_id))
            )
        if symbol_kinds:
            must_conditions.append(
                qm.FieldCondition(key="symbol_kind", match=qm.MatchAny(any=symbol_kinds))
            )

        results, _ = self.client.scroll(
            collection_name=self.collection,
            scroll_filter=qm.Filter(must=must_conditions),
            limit=50,
            with_payload=True,
        )

        return [self._point_to_dict(r) for r in results]

    def get_file_symbols(
        self,
        file_path: str,
        repo_id: Optional[str] = None,
    ) -> list[dict]:
        """Get all symbols in a file."""
        must_conditions = [
            qm.FieldCondition(key="file_path", match=qm.MatchValue(value=file_path))
        ]
        if repo_id:
            must_conditions.append(
                qm.FieldCondition(key="repo_id", match=qm.MatchValue(value=repo_id))
            )

        results, _ = self.client.scroll(
            collection_name=self.collection,
            scroll_filter=qm.Filter(must=must_conditions),
            limit=500,
            with_payload=True,
            order_by=qm.OrderBy(key="start_line", direction=qm.Direction.ASC),
        )

        return [self._point_to_dict(r) for r in results]

    def delete_file(self, file_path: str, repo_id: Optional[str] = None) -> int:
        """Delete all chunks for a file. Returns count deleted."""
        must_conditions = [
            qm.FieldCondition(key="file_path", match=qm.MatchValue(value=file_path))
        ]
        if repo_id:
            must_conditions.append(
                qm.FieldCondition(key="repo_id", match=qm.MatchValue(value=repo_id))
            )

        result = self.client.delete(
            collection_name=self.collection,
            points_selector=qm.FilterSelector(
                filter=qm.Filter(must=must_conditions)
            ),
        )
        return result.status

    def delete_repo(self, repo_id: str) -> int:
        """Delete all chunks for a repo."""
        result = self.client.delete(
            collection_name=self.collection,
            points_selector=qm.FilterSelector(
                filter=qm.Filter(
                    must=[qm.FieldCondition(key="repo_id", match=qm.MatchValue(value=repo_id))]
                )
            ),
        )
        return result.status

    def _point_to_dict(self, point) -> dict:
        """Convert a Qdrant point to a dictionary."""
        p = point.payload or {}
        return {
            "id": point.id,
            "score": getattr(point, "score", None),
            "file_path": p.get("file_path"),
            "content": p.get("content"),
            "language": p.get("language"),
            "symbol_kind": p.get("symbol_kind"),
            "symbol_name": p.get("symbol_name"),
            "start_line": p.get("start_line"),
            "end_line": p.get("end_line"),
            "parent_symbol": p.get("parent_symbol"),
            "docstring": p.get("docstring"),
            "signature": p.get("signature"),
        }
