"""
Pydantic models for API requests and responses.
"""

from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime


# Request Models
class SearchRequest(BaseModel):
    """Request model for all search endpoints."""
    query: str = Field(..., description="Search query text")
    top_k: Optional[int] = Field(5, description="Number of results to return", ge=1, le=20)
    filters: Optional[Dict[str, Any]] = Field(None, description="Optional filters")


# Response Models - Common
class DocumentMetadata(BaseModel):
    """Metadata for a document chunk."""
    document_id: str
    title: str
    section: Optional[str] = None
    source: str
    citation: Optional[str] = None
    chunk_index: int = 0


class SearchResult(BaseModel):
    """Single search result."""
    text: str
    score: float
    metadata: DocumentMetadata
    highlights: Optional[List[str]] = None


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    services: Dict[str, str]
    timestamp: datetime = Field(default_factory=datetime.now)


class DocumentSummary(BaseModel):
    """Summary of a document."""
    document_id: str
    title: str
    source: str
    citation: Optional[str] = None
    num_chunks: int
    total_tokens: Optional[int] = None


class DocumentListResponse(BaseModel):
    """Response for document listing."""
    documents: List[DocumentSummary]
    total: int


# Simple Search Response
class SimpleSearchResponse(BaseModel):
    """Response for simple keyword search."""
    query: str
    results: List[SearchResult]
    search_time_ms: float
    total_found: int
    method: str = "simple_search"
    limitation: str = "Keyword matching only - misses semantic similarity"


# Simple RAG Response
class SimpleRAGResponse(BaseModel):
    """Response for simple RAG."""
    query: str
    answer: str
    retrieved_chunks: List[SearchResult]
    search_time_ms: float
    generation_time_ms: float
    total_time_ms: float
    method: str = "simple_rag"
    limitation: str = "Single retrieval step - may miss nuanced context"


# Agentic RAG Response (streamed as SSE events)
class AgenticStep(BaseModel):
    """Single step in agentic reasoning process."""
    step_number: int
    step_type: str  # "query_analysis", "vector_search", "reasoning", "synthesis"
    agent_name: str
    description: str
    content: Any  # Flexible content based on step type
    timestamp: datetime = Field(default_factory=datetime.now)


class VectorSearchStep(BaseModel):
    """Details of a vector search operation."""
    query_text: str
    retrieved_chunks: List[SearchResult]
    reasoning: str
    search_time_ms: float


class AgenticRAGResponse(BaseModel):
    """Final response for agentic RAG (sent as last event)."""
    query: str
    answer: str
    reasoning_steps: List[AgenticStep]
    documents_accessed: List[str]
    total_searches: int
    total_time_ms: float
    method: str = "agentic_rag"
    confidence: str = "high"  # "low", "medium", "high"


# SSE Event Model
class SSEEvent(BaseModel):
    """Server-Sent Event wrapper."""
    event: str  # "step", "complete", "error"
    data: Dict[str, Any]
    
    def format(self) -> str:
        """Format as SSE message."""
        import json
        return f"event: {self.event}\ndata: {json.dumps(self.data)}\n\n"

