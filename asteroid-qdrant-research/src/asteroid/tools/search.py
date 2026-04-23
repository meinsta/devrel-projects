"""Search tools backed by Qdrant."""

from qdrant_client import QdrantClient, models
from fastembed import TextEmbedding

from .base import ToolResult


class QdrantSearchTools:
    """All seven Qdrant-native tools in one class.

    Shared state: qdrant client, embedding model, collection name.
    Each method is a tool the agent can call.
    """

    def __init__(self, qdrant: QdrantClient, embed_model: TextEmbedding, collection: str):
        self.qdrant = qdrant
        self.embed_model = embed_model
        self.collection = collection

    def _embed(self, text: str) -> list[float]:
        return list(self.embed_model.embed([text]))[0].tolist()

    def _format_results(self, points) -> str:
        chunks = []
        for p in points:
            title = p.payload.get("title", "")
            text = p.payload.get("text", "")
            page_id = p.payload.get("page_id", "")
            chunk_id = str(p.id)
            score = getattr(p, "score", 0.0)
            chunks.append(f"[chunk_id={chunk_id}] [{title}] (page_id={page_id}, score={score:.3f})\n{text}")
        return "\n\n---\n\n".join(chunks) if chunks else "No results found."

    def search_corpus(self, query: str, top_k: int = 5) -> ToolResult:
        """Hybrid search: BGE dense + BM25 sparse + RRF fusion."""
        results = self.qdrant.query_points(
            collection_name=self.collection,
            prefetch=[
                models.Prefetch(
                    query=models.Document(text=query, model="Qdrant/bm25"),
                    using="bm25",
                    limit=top_k * 2,
                ),
                models.Prefetch(
                    query=self._embed(query),
                    using="dense",
                    limit=top_k * 2,
                ),
            ],
            query=models.FusionQuery(fusion=models.Fusion.RRF),
            limit=top_k,
            with_payload=True,
        )
        content = self._format_results(results.points)
        return ToolResult(content=content, metadata={"n_results": len(results.points)})

    def filter_search(self, query: str, filters: dict, top_k: int = 5) -> ToolResult:
        """Hybrid search scoped by payload filters."""
        must_conditions = []
        for key, value in filters.items():
            if isinstance(value, dict):
                must_conditions.append(models.FieldCondition(key=key, range=models.Range(**value)))
            else:
                must_conditions.append(models.FieldCondition(key=key, match=models.MatchValue(value=value)))

        qfilter = models.Filter(must=must_conditions) if must_conditions else None

        results = self.qdrant.query_points(
            collection_name=self.collection,
            prefetch=[
                models.Prefetch(
                    query=models.Document(text=query, model="Qdrant/bm25"),
                    using="bm25",
                    limit=top_k * 2,
                ),
                models.Prefetch(
                    query=self._embed(query),
                    using="dense",
                    limit=top_k * 2,
                ),
            ],
            query=models.FusionQuery(fusion=models.Fusion.RRF),
            query_filter=qfilter,
            limit=top_k,
            with_payload=True,
        )
        content = self._format_results(results.points)
        return ToolResult(content=content, metadata={"n_results": len(results.points), "filters": filters})

    def text_search(self, phrase: str, top_k: int = 5) -> ToolResult:
        """Full-text search on indexed text payloads."""
        results, _ = self.qdrant.scroll(
            collection_name=self.collection,
            scroll_filter=models.Filter(
                must=[models.FieldCondition(key="text", match=models.MatchText(text=phrase))]
            ),
            limit=top_k,
            with_payload=True,
        )
        content = self._format_results(results)
        return ToolResult(content=content, metadata={"n_results": len(results)})

    def read_document(self, page_id: str) -> ToolResult:
        """Retrieve all chunks from a document by page_id."""
        results, _ = self.qdrant.scroll(
            collection_name=self.collection,
            scroll_filter=models.Filter(
                must=[models.FieldCondition(key="page_id", match=models.MatchValue(value=page_id))]
            ),
            limit=50,
            with_payload=True,
            order_by=models.OrderBy(key="section_idx", direction=models.Direction.ASC),
        )
        content = self._format_results(results)
        return ToolResult(content=content, metadata={"n_results": len(results), "page_id": page_id})

    def group_search(self, query: str, group_by: str, top_k: int = 5) -> ToolResult:
        """Search with results grouped by a payload field."""
        results = self.qdrant.query_points_groups(
            collection_name=self.collection,
            using="bm25",
            query=models.Document(text=query, model="Qdrant/bm25"),
            group_by=group_by,
            group_size=1,
            limit=top_k,
            with_payload=True,
        )
        chunks = []
        for g in results.groups:
            for p in g.hits:
                title = p.payload.get("title", "")
                text = p.payload.get("text", "")
                chunk_id = str(p.id)
                chunks.append(f"[chunk_id={chunk_id}] [{title}] (group={g.id})\n{text}")
        content = "\n\n---\n\n".join(chunks) if chunks else "No results found."
        return ToolResult(content=content, metadata={"n_groups": len(results.groups)})

    def refine_search(self, positive_ids: list[int], negative_ids: list[int], top_k: int = 5) -> ToolResult:
        """Relevance feedback: re-score based on positive/negative examples."""
        results = self.qdrant.query_points(
            collection_name=self.collection,
            query=models.RecommendQuery(
                recommend=models.RecommendInput(
                    positive=positive_ids,
                    negative=negative_ids,
                ),
            ),
            using="dense",
            limit=top_k,
            with_payload=True,
        )
        content = self._format_results(results.points)
        return ToolResult(content=content, metadata={"n_results": len(results.points)})

    def prune_chunks(self, chunk_ids: list[str]) -> ToolResult:
        """Remove chunks from context. Returns freed count."""
        return ToolResult(
            content=f"Pruned {len(chunk_ids)} chunks from context.",
            metadata={"pruned": chunk_ids},
        )

    def get_tool_schemas(self) -> list[dict]:
        """OpenAI-compatible tool definitions for all seven tools."""
        return [
            {
                "type": "function",
                "function": {
                    "name": "search_corpus",
                    "description": "Hybrid search combining keyword (BM25) and semantic matching. Use for general queries.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Search query"},
                        },
                        "required": ["query"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "filter_search",
                    "description": "Hybrid search scoped by metadata filters. Use to narrow results by corpus, date, category, etc.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Search query"},
                            "filters": {"type": "object", "description": 'Payload filters as key-value pairs. e.g. {"title": "Krebs Cycle"} or {"section_idx": {"gte": 0, "lte": 5}}'},
                        },
                        "required": ["query", "filters"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "text_search",
                    "description": "Exact text matching. Finds documents containing a specific phrase or term.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "phrase": {"type": "string", "description": "Exact phrase to find"},
                        },
                        "required": ["phrase"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "read_document",
                    "description": "Retrieve all chunks from a specific document by its page_id.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "page_id": {"type": "string", "description": "The page_id of the document to read"},
                        },
                        "required": ["page_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "group_search",
                    "description": "Search with results grouped by a payload field. Returns top result per group for breadth.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Search query"},
                            "group_by": {"type": "string", "description": "Payload field to group by (e.g. 'title', 'page_id')"},
                        },
                        "required": ["query", "group_by"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "refine_search",
                    "description": "Relevance feedback. Provide chunk IDs of good and bad results to improve next search.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "positive_ids": {"type": "array", "items": {"type": "integer"}, "description": "Chunk IDs of relevant results"},
                            "negative_ids": {"type": "array", "items": {"type": "integer"}, "description": "Chunk IDs of irrelevant results"},
                        },
                        "required": ["positive_ids", "negative_ids"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "prune_chunks",
                    "description": "Remove chunks from your working context to free token budget. Use when context is getting full.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "chunk_ids": {"type": "array", "items": {"type": "string"}, "description": "IDs of chunks to remove"},
                        },
                        "required": ["chunk_ids"],
                    },
                },
            },
        ]
