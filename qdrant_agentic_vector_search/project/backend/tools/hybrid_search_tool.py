"""
Hybrid Search Tool for CrewAI Agents
Uses Qdrant's hybrid search with RRF fusion
"""

from typing import Any
from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from qdrant_client import QdrantClient, models
from fastembed import TextEmbedding, SparseTextEmbedding
import os

COLLECTION_NAME = "california_housing_statutes_full"
DENSE_VECTOR_NAME = "dense"
SPARSE_VECTOR_NAME = "sparse"


class HybridSearchInput(BaseModel):
    """Input for hybrid search."""
    query: str = Field(..., description="Search query for California housing statutes")
    top_k: int = Field(default=5, description="Number of results to return")


class HybridSearchTool(BaseTool):
    """Search California housing statutes using Qdrant hybrid search with RRF."""
    
    name: str = "hybrid_search"
    description: str = """Search California housing statutes using hybrid search.
    Combines semantic understanding (dense vectors) with exact keyword matching (sparse vectors).
    Returns statute citations, scores, and full text.
    Use this to find relevant laws for any California housing question."""
    
    args_schema: type[BaseModel] = HybridSearchInput
    
    # Lazy-loaded clients
    qdrant_client: Any = None
    dense_model: Any = None
    sparse_model: Any = None
    
    class Config:
        arbitrary_types_allowed = True
    
    def __init__(self):
        super().__init__()
        self._init_clients()
    
    def _init_clients(self):
        """Initialize Qdrant client and embedding models."""
        if self.qdrant_client is None:
            self.qdrant_client = QdrantClient(
                url=os.getenv('QDRANT_CLOUD_URL'),
                api_key=os.getenv('QDRANT_API_KEY')
            )
        if self.dense_model is None:
            self.dense_model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
        if self.sparse_model is None:
            self.sparse_model = SparseTextEmbedding(
                model_name="Qdrant/bm42-all-minilm-l6-v2-attentions"
            )
    
    def _run(self, query: str, top_k: int = 5) -> str:
        """Execute hybrid search and return formatted results."""
        
        # Generate embeddings
        dense_query = list(self.dense_model.embed([query]))[0].tolist()
        sparse_query_embedding = list(self.sparse_model.embed([query]))[0]
        sparse_query = models.SparseVector(
            indices=sparse_query_embedding.indices.tolist(),
            values=sparse_query_embedding.values.tolist()
        )
        
        # Hybrid search with RRF
        results = self.qdrant_client.query_points(
            collection_name=COLLECTION_NAME,
            prefetch=[
                models.Prefetch(query=dense_query, using=DENSE_VECTOR_NAME, limit=20),
                models.Prefetch(query=sparse_query, using=SPARSE_VECTOR_NAME, limit=20),
            ],
            query=models.FusionQuery(fusion=models.Fusion.RRF),
            limit=top_k,
        )
        
        # Format results for agent
        if not results.points:
            return "No relevant statutes found."
        
        formatted_results = []
        for i, point in enumerate(results.points, 1):
            citation = point.payload.get('citation', 'Unknown')
            text = point.payload.get('text', '')
            score = point.score
            statute_idx = point.payload.get('statute_idx')
            
            # Truncate very long text
            display_text = text[:500] + "..." if len(text) > 500 else text
            
            formatted_results.append(
                f"[{i}] {citation} (Score: {score:.3f}, ID: {statute_idx})\n"
                f"{display_text}\n"
            )
        
        return "\n".join(formatted_results)

