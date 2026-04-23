"""Retrieval module for querying Qdrant vector store."""

from typing import List, Dict, Any, Optional
from qdrant_client.models import Filter, FieldCondition, MatchValue
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Phoenix tracing support (optional)
try:
    from opentelemetry import trace
    from opentelemetry.semconv.ai import SpanAttributes
    from openinference.semconv.trace import OpenInferenceSpanKindValues
    PHOENIX_AVAILABLE = True
except ImportError:
    PHOENIX_AVAILABLE = False
    trace = None


class StatuteRetriever:
    """Retrieve relevant statute chunks from Qdrant."""
    
    def __init__(self, vector_store):
        """
        Initialize retriever with a vector store.
        
        Args:
            vector_store: QdrantVectorStore instance
        """
        self.vector_store = vector_store
        self.client = vector_store.client
        self.collection_name = vector_store.collection_name
    
    def retrieve(
        self,
        query: str,
        state: Optional[str] = None,
        top_k: int = 5,
        score_threshold: Optional[float] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieve relevant statute chunks for a query.
        
        Args:
            query: Query text
            state: Optional state filter
            top_k: Number of results to return
            score_threshold: Minimum similarity score (0-1)
            
        Returns:
            List of retrieved chunks with metadata and scores
        """
        logger.info(f"Retrieving top {top_k} chunks for query: '{query[:50]}...'")
        
        # Check if collection is state-specific (e.g., "housing_statutes_wyoming")
        # If so, skip filtering since all data is already for that state
        collection_name_lower = self.collection_name.lower()
        # Pattern: housing_statutes_{state} or similar
        is_state_specific = (
            'housing_statutes_' in collection_name_lower and 
            collection_name_lower != 'housing_statutes'  # Not the default multi-state collection
        )
        
        # Build filter if state is specified AND collection is not state-specific
        query_filter = None
        if state and not is_state_specific:
            # Normalize state name to lowercase (as stored in database)
            state_normalized = state.lower().strip()
            logger.info(f"Filtering by state: {state_normalized}")
            
            query_filter = Filter(
                must=[
                    FieldCondition(
                        key="state",
                        match=MatchValue(value=state_normalized)
                    )
                ]
            )
        elif is_state_specific:
            logger.info(f"Collection '{self.collection_name}' is state-specific, skipping state filter")
        
        try:
            # Create Phoenix trace span for retrieval if available
            # Use context manager to ensure span is properly closed
            if PHOENIX_AVAILABLE and trace:
                tracer = trace.get_tracer(__name__)
                span_context = tracer.start_as_current_span("qdrant.retrieve")
                span_context.__enter__()
                span = trace.get_current_span()
                if span:
                    span.set_attribute(SpanAttributes.OPENINFERENCE_SPAN_KIND, OpenInferenceSpanKindValues.RETRIEVER.value)
                    span.set_attribute(SpanAttributes.INPUT_VALUE, query)
                    if state:
                        span.set_attribute("retrieval.state_filter", state_normalized)
                    span.set_attribute("retrieval.top_k", top_k)
                    span.set_attribute("retrieval.collection", self.collection_name)
            else:
                span = None
                span_context = None
            
            # Query using FastEmbed (Qdrant will embed the query automatically)
            results = self.client.query(
                collection_name=self.collection_name,
                query_text=query,
                query_filter=query_filter,
                limit=top_k,
                score_threshold=score_threshold
            )
            
            # Format results
            retrieved = []
            for i, result in enumerate(results):
                chunk = {
                    'text': result.metadata.get('text', ''),
                    'citation': result.metadata.get('citation', ''),
                    'state': result.metadata.get('state', ''),
                    'statute_idx': result.metadata.get('statute_idx', ''),
                    'chunk_idx': result.metadata.get('chunk_idx', 0),
                    'path': result.metadata.get('path', ''),
                    'score': result.score
                }
                retrieved.append(chunk)
                
                # Add document to Phoenix trace span
                if span:
                    doc_base = f"retrieval.documents.{i}.document"
                    span.set_attribute(f"{doc_base}.id", str(chunk.get('statute_idx', '')))
                    span.set_attribute(f"{doc_base}.score", float(result.score))
                    span.set_attribute(f"{doc_base}.content", chunk['text'][:1000])  # Limit content length
                    # Add metadata
                    metadata = {
                        'citation': chunk.get('citation', ''),
                        'state': chunk.get('state', ''),
                        'statute_idx': str(chunk.get('statute_idx', '')),
                        'chunk_idx': chunk.get('chunk_idx', 0)
                    }
                    import json
                    span.set_attribute(f"{doc_base}.metadata", json.dumps(metadata, default=str))
            
            # Set output on span and close
            if span:
                span.set_attribute(SpanAttributes.OUTPUT_VALUE, f"Retrieved {len(retrieved)} documents")
                span.set_attribute("retrieval.count", len(retrieved))
            if span_context:
                span_context.__exit__(None, None, None)
            
            logger.info(f"Retrieved {len(retrieved)} chunks")
            return retrieved
            
        except Exception as e:
            logger.error(f"Error during retrieval: {e}")
            raise
    
    def retrieve_unique_statutes(
        self,
        query: str,
        state: Optional[str] = None,
        top_k: int = 5,
        max_chunks_per_statute: int = 2
    ) -> List[Dict[str, Any]]:
        """
        Retrieve chunks but deduplicate by statute.
        
        Args:
            query: Query text
            state: Optional state filter
            top_k: Number of unique statutes to return
            max_chunks_per_statute: Maximum chunks per statute
            
        Returns:
            List of unique statutes with their best chunks
        """
        # Retrieve more chunks than needed to account for duplicates
        chunks = self.retrieve(
            query=query,
            state=state,
            top_k=top_k * 3,  # Get 3x chunks to ensure enough unique statutes
            score_threshold=None
        )
        
        # Group by statute_idx
        statute_groups = {}
        for chunk in chunks:
            statute_idx = chunk['statute_idx']
            if statute_idx not in statute_groups:
                statute_groups[statute_idx] = []
            statute_groups[statute_idx].append(chunk)
        
        # Take top statutes and limit chunks per statute
        unique_statutes = []
        for statute_idx, statute_chunks in list(statute_groups.items())[:top_k]:
            # Sort chunks by score and take top N
            sorted_chunks = sorted(statute_chunks, key=lambda x: x['score'], reverse=True)
            top_chunks = sorted_chunks[:max_chunks_per_statute]
            
            statute = {
                'statute_idx': statute_idx,
                'citation': top_chunks[0]['citation'],
                'state': top_chunks[0]['state'],
                'path': top_chunks[0]['path'],
                'chunks': top_chunks,
                'max_score': max(c['score'] for c in top_chunks)
            }
            unique_statutes.append(statute)
        
        # Sort by max score
        unique_statutes.sort(key=lambda x: x['max_score'], reverse=True)
        
        logger.info(f"Retrieved {len(unique_statutes)} unique statutes")
        return unique_statutes
    
    def format_retrieved_context(
        self,
        retrieved_chunks: List[Dict[str, Any]],
        include_citations: bool = True
    ) -> str:
        """
        Format retrieved chunks into a readable context string.
        
        Args:
            retrieved_chunks: List of retrieved chunk dictionaries
            include_citations: Include citations in output
            
        Returns:
            Formatted context string
        """
        if not retrieved_chunks:
            return "No relevant statutes found."
        
        context_parts = []
        for i, chunk in enumerate(retrieved_chunks, 1):
            if include_citations:
                part = f"[{i}] {chunk['citation']}\n{chunk['text']}"
            else:
                part = f"[{i}] {chunk['text']}"
            context_parts.append(part)
        
        return "\n\n".join(context_parts)


def retrieve_for_query(
    vector_store,
    query: str,
    state: Optional[str] = None,
    top_k: int = 5
) -> List[Dict[str, Any]]:
    """
    Convenience function to retrieve chunks.
    
    Args:
        vector_store: QdrantVectorStore instance
        query: Query text
        state: Optional state filter
        top_k: Number of results
        
    Returns:
        List of retrieved chunks
    """
    retriever = StatuteRetriever(vector_store)
    return retriever.retrieve(query=query, state=state, top_k=top_k)

