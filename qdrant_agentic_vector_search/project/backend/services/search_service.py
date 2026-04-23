"""
Search service implementing three search approaches:
1. Simple Search (BM25/keyword matching)
2. Simple RAG (single vector search + LLM)
3. Agentic RAG (handled by crew_service)
"""

from typing import List, Dict, Any
import time
import logging
from openai import OpenAI
import os
import re

from models import (
    SimpleSearchResponse,
    SimpleRAGResponse,
    SearchResult,
    DocumentMetadata
)
from services.qdrant_service import QdrantService

logger = logging.getLogger(__name__)


class SearchService:
    """Service for different search implementations."""
    
    def __init__(self, qdrant_service: QdrantService):
        """Initialize search service."""
        self.qdrant_service = qdrant_service
        self.openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        logger.info("Search service initialized")
    
    def _extract_keywords(self, query: str) -> List[str]:
        """Extract keywords from query for BM25-style matching."""
        # Remove common words and extract meaningful terms
        stop_words = {
            'a', 'an', 'and', 'are', 'as', 'at', 'be', 'by', 'for',
            'from', 'has', 'he', 'in', 'is', 'it', 'its', 'of', 'on',
            'that', 'the', 'to', 'was', 'will', 'with', 'can', 'does'
        }
        
        # Extract words
        words = re.findall(r'\b\w+\b', query.lower())
        keywords = [w for w in words if w not in stop_words and len(w) > 2]
        
        return keywords
    
    def _keyword_score(self, text: str, keywords: List[str]) -> float:
        """Calculate simple keyword matching score."""
        text_lower = text.lower()
        score = 0.0
        
        for keyword in keywords:
            # Count occurrences
            count = text_lower.count(keyword)
            score += count
        
        # Normalize by text length
        if len(text) > 0:
            score = score / (len(text) / 100)
        
        return score
    
    def _highlight_text(self, text: str, keywords: List[str]) -> List[str]:
        """Extract highlighted snippets containing keywords."""
        highlights = []
        text_lower = text.lower()
        
        for keyword in keywords:
            pos = text_lower.find(keyword)
            if pos != -1:
                # Extract 100 chars around keyword
                start = max(0, pos - 50)
                end = min(len(text), pos + 50)
                snippet = text[start:end]
                if start > 0:
                    snippet = "..." + snippet
                if end < len(text):
                    snippet = snippet + "..."
                highlights.append(snippet)
        
        return highlights[:3]  # Top 3 highlights
    
    async def simple_search(self, query: str, top_k: int = 3) -> SimpleSearchResponse:
        """
        Simple keyword search using BM25-style matching.
        
        This demonstrates the limitation of keyword-only search:
        - Misses semantically similar content
        - No understanding of synonyms or context
        - Only finds exact keyword matches
        """
        start_time = time.time()
        
        try:
            # Extract keywords from query
            keywords = self._extract_keywords(query)
            logger.info(f"Simple search keywords: {keywords}")
            
            # Get documents from Qdrant (we'll do keyword matching ourselves)
            # In a real BM25 system, this would use a proper inverted index
            all_results = await self.qdrant_service.search(
                query=query,
                top_k=50  # Get more candidates for keyword filtering
            )
            
            # Score each result based on keyword matching
            scored_results = []
            for result in all_results:
                keyword_score = self._keyword_score(result['text'], keywords)
                if keyword_score > 0:  # Only include if keywords match
                    result['keyword_score'] = keyword_score
                    result['highlights'] = self._highlight_text(result['text'], keywords)
                    scored_results.append(result)
            
            # Sort by keyword score
            scored_results.sort(key=lambda x: x['keyword_score'], reverse=True)
            
            # Take top_k
            top_results = scored_results[:top_k]
            
            # Format results
            search_results = []
            for result in top_results:
                search_results.append(SearchResult(
                    text=result['text'],
                    score=result['keyword_score'],
                    metadata=DocumentMetadata(**result['metadata']),
                    highlights=result.get('highlights')
                ))
            
            search_time_ms = (time.time() - start_time) * 1000
            
            return SimpleSearchResponse(
                query=query,
                results=search_results,
                search_time_ms=search_time_ms,
                total_found=len(scored_results)
            )
        
        except Exception as e:
            logger.error(f"Simple search error: {e}")
            raise
    
    async def simple_rag(self, query: str, top_k: int = 5) -> SimpleRAGResponse:
        """
        Simple RAG: Single vector search + LLM generation.
        
        This demonstrates the limitation of single-step RAG:
        - Only one retrieval step
        - May miss important context from other documents
        - No iterative refinement
        - Cannot reason across multiple sources
        """
        search_start = time.time()
        
        try:
            # Single vector search
            results = await self.qdrant_service.search(
                query=query,
                top_k=top_k
            )
            
            search_time_ms = (time.time() - search_start) * 1000
            
            # Format retrieved chunks
            retrieved_chunks = []
            context_parts = []
            
            for i, result in enumerate(results, 1):
                retrieved_chunks.append(SearchResult(
                    text=result['text'],
                    score=result['score'],
                    metadata=DocumentMetadata(**result['metadata'])
                ))
                
                # Build context for LLM
                citation = result['metadata'].get('citation', 'Unknown')
                context_parts.append(f"[{i}] {citation}\n{result['text']}")
            
            context = "\n\n".join(context_parts)
            
            # Generate answer with LLM
            gen_start = time.time()
            
            prompt = f"""You are a legal expert. Answer the following question based ONLY on the provided legal documents.

Question: {query}

Legal Documents:
{context}

Instructions:
- Provide a clear, concise answer
- Cite specific documents using [number] references
- If the documents don't contain enough information, say so
- Be precise and legally accurate

Answer:"""
            
            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a legal expert assistant."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=500
            )
            
            answer = response.choices[0].message.content.strip()
            generation_time_ms = (time.time() - gen_start) * 1000
            total_time_ms = search_time_ms + generation_time_ms
            
            return SimpleRAGResponse(
                query=query,
                answer=answer,
                retrieved_chunks=retrieved_chunks,
                search_time_ms=search_time_ms,
                generation_time_ms=generation_time_ms,
                total_time_ms=total_time_ms
            )
        
        except Exception as e:
            logger.error(f"Simple RAG error: {e}")
            raise

