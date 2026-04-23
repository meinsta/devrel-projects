"""
Custom Qdrant Vector Search Tool for CrewAI that supports named vectors.

This tool enables CrewAI agents to perform semantic search against Qdrant collections.
"""

from typing import Any, Optional, Type
from pydantic import BaseModel, Field
from crewai.tools import BaseTool
from qdrant_client import QdrantClient
from fastembed import TextEmbedding


class QdrantSearchInput(BaseModel):
    """Input schema for Qdrant search."""
    query: str = Field(..., description="Query to search in Qdrant DB")
    filter_by: Optional[str] = Field(None, description="Parameter to filter the search by")
    filter_value: Optional[Any] = Field(None, description="Value to filter the search by")


class CustomQdrantTool(BaseTool):
    """Custom Qdrant tool that supports named vectors and BGE embeddings."""
    
    name: str = "QdrantVectorSearch"
    description: str = "Search Qdrant vector DB for relevant housing statutes using semantic search. Use this to find relevant legal documents."
    args_schema: Type[BaseModel] = QdrantSearchInput
    
    # Custom configuration
    qdrant_url: str
    qdrant_api_key: str
    collection_name: str
    vector_name: str = "fast-bge-small-en"  # Named vector in the collection
    limit: int = 5
    score_threshold: float = 0.0
    
    # Internal clients (initialized in model_post_init)
    _client: Optional[QdrantClient] = None
    _embedding_model: Optional[TextEmbedding] = None
    
    class Config:
        arbitrary_types_allowed = True
    
    def model_post_init(self, __context: Any) -> None:
        """Initialize Qdrant client and embedding model after instantiation."""
        super().model_post_init(__context)
        
        # Initialize Qdrant client
        self._client = QdrantClient(
            url=self.qdrant_url,
            api_key=self.qdrant_api_key
        )
        
        # Initialize BGE-small embedding model to match the collection
        self._embedding_model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
    
    def _embed_text(self, text: str) -> list[float]:
        """Generate embedding for text using BGE-small model."""
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
        Execute the Qdrant search with named vector support.
        
        Args:
            query: The search query text
            filter_by: Optional field to filter by
            filter_value: Optional value to filter by
            
        Returns:
            Formatted string with search results for the agent
        """
        try:
            # Generate embedding for the query
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
            
            # Search using named vector
            results = self._client.query_points(
                collection_name=self.collection_name,
                query=query_vector,
                using=self.vector_name,  # Specify the named vector
                limit=self.limit,
                query_filter=search_filter,
                score_threshold=self.score_threshold
            ).points
            
            # Format results for the agent
            if not results:
                return "No relevant statutes found for the query."
            
            output = []
            output.append(f"Found {len(results)} relevant statutes:\n")
            
            for i, result in enumerate(results, 1):
                citation = result.payload.get("citation", "Unknown")
                text = result.payload.get("text", "")
                score = result.score
                
                # Truncate long text for readability
                text_preview = text[:300] + "..." if len(text) > 300 else text
                
                output.append(
                    f"\n[{i}] {citation} (Relevance: {score:.3f})\n"
                    f"{text_preview}\n"
                )
            
            return "\n".join(output)
            
        except Exception as e:
            return f"Error searching Qdrant: {str(e)}"

