"""
Custom Qdrant Vector Search Tool for CrewAI

Enables AI agents to perform semantic search on Qdrant collections
using BGE embeddings and named vectors.
"""

from typing import Any, Optional, Type
from pydantic import BaseModel, Field
from crewai.tools import BaseTool
from qdrant_client import QdrantClient
from fastembed import TextEmbedding


class QdrantSearchInput(BaseModel):
    """Input schema for Qdrant search."""
    query: str = Field(..., description="Search query to find relevant statutes")
    filter_by: Optional[str] = Field(None, description="Optional field name to filter by")
    filter_value: Optional[Any] = Field(None, description="Optional value to filter by")


class QdrantSearchTool(BaseTool):
    """Tool for semantic search in Qdrant vector database."""
    
    name: str = "qdrant_search"
    description: str = (
        "Search housing law statutes using semantic vector search. "
        "Use this to find relevant legal statutes based on any query. "
        "The tool returns the most semantically similar statutes."
    )
    args_schema: Type[BaseModel] = QdrantSearchInput
    
    # Configuration
    qdrant_url: str
    qdrant_api_key: str
    collection_name: str
    vector_name: str = "fast-bge-small-en"
    limit: int = 5
    score_threshold: float = 0.0
    
    # Internal clients
    _client: Optional[QdrantClient] = None
    _embedding_model: Optional[TextEmbedding] = None
    
    class Config:
        arbitrary_types_allowed = True
    
    def model_post_init(self, __context: Any) -> None:
        """Initialize Qdrant client and embedding model."""
        super().model_post_init(__context)
        
        self._client = QdrantClient(
            url=self.qdrant_url,
            api_key=self.qdrant_api_key
        )
        
        self._embedding_model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
    
    def _embed_text(self, text: str) -> list[float]:
        """Generate embedding for text."""
        embeddings = list(self._embedding_model.embed([text]))
        return embeddings[0].tolist()
    
    def _run(
        self,
        query: str,
        filter_by: Optional[str] = None,
        filter_value: Optional[Any] = None,
        **kwargs: Any
    ) -> str:
        """
        Execute semantic search in Qdrant.
        
        Args:
            query: Search query text
            filter_by: Optional field to filter results
            filter_value: Optional value to filter by
            
        Returns:
            Formatted string with search results
        """
        try:
            # Generate query embedding
            query_vector = self._embed_text(query)
            
            # Build filter if specified
            search_filter = None
            if filter_by and filter_value is not None:
                from qdrant_client.models import Filter, FieldCondition, MatchValue
                search_filter = Filter(
                    must=[
                        FieldCondition(
                            key=filter_by,
                            match=MatchValue(value=filter_value)
                        )
                    ]
                )
            
            # Perform search
            results = self._client.query_points(
                collection_name=self.collection_name,
                query=query_vector,
                using=self.vector_name,
                limit=self.limit,
                query_filter=search_filter,
                score_threshold=self.score_threshold
            ).points
            
            # Format results
            if not results:
                return "No relevant statutes found for this query."
            
            formatted = []
            for i, result in enumerate(results, 1):
                citation = result.payload.get("citation", "Unknown")
                text = result.payload.get("text", "")
                score = result.score
                
                formatted.append(
                    f"{i}. {citation} (Relevance: {score:.3f})\n"
                    f"   {text[:300]}...\n"
                )
            
            return "\n".join(formatted)
            
        except Exception as e:
            return f"Error during search: {str(e)}"

