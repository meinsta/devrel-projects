"""
California Housing Law Research Service
Provides streaming agentic flow with hybrid search (RRF)
"""

import os
import time
import json
import asyncio
from typing import AsyncGenerator
from qdrant_client import QdrantClient, models
from fastembed import TextEmbedding, SparseTextEmbedding
from openai import OpenAI
import logging

logger = logging.getLogger(__name__)

COLLECTION_NAME = "california_housing_statutes_full"
DENSE_VECTOR_NAME = "dense"
SPARSE_VECTOR_NAME = "sparse"


class CaliforniaService:
    """Service for California housing law research with hybrid search."""
    
    def __init__(self):
        """Initialize California research service."""
        self.qdrant_client = None
        self.dense_model = None
        self.sparse_model = None
        self.openai_client = None
        
        # Get credentials from environment
        self.qdrant_url = os.getenv('QDRANT_CLOUD_URL')
        self.qdrant_api_key = os.getenv('QDRANT_API_KEY')
        self.openai_api_key = os.getenv('OPENAI_API_KEY')
        
        logger.info("California service initialized (lazy loading)")
    
    def _get_qdrant_client(self):
        """Lazy load Qdrant client."""
        if self.qdrant_client is None:
            self.qdrant_client = QdrantClient(
                url=self.qdrant_url,
                api_key=self.qdrant_api_key
            )
        return self.qdrant_client
    
    def _get_dense_model(self):
        """Lazy load dense embedding model."""
        if self.dense_model is None:
            self.dense_model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
        return self.dense_model
    
    def _get_sparse_model(self):
        """Lazy load sparse embedding model."""
        if self.sparse_model is None:
            self.sparse_model = SparseTextEmbedding(
                model_name="Qdrant/bm42-all-minilm-l6-v2-attentions"
            )
        return self.sparse_model
    
    def _get_openai_client(self):
        """Lazy load OpenAI client."""
        if self.openai_client is None and self.openai_api_key:
            self.openai_client = OpenAI(api_key=self.openai_api_key)
        return self.openai_client
    
    async def research_flow(self, query: str) -> AsyncGenerator[str, None]:
        """
        Streaming agentic research flow.
        Yields SSE events for each step of the process.
        """
        
        # Step 1: Analyze query
        yield f"data: {json.dumps({'type': 'step', 'action': 'analyze', 'title': 'Analyzing Query', 'description': f'Understanding legal intent: {query[:50]}...'})}\n\n"
        await asyncio.sleep(0.5)
        
        # Step 2: Generate embeddings
        start_time = time.time()
        yield f"data: {json.dumps({'type': 'step', 'action': 'search', 'title': 'Generating Embeddings', 'description': 'Creating dense and sparse vector representations'})}\n\n"
        
        try:
            dense_model = self._get_dense_model()
            sparse_model = self._get_sparse_model()
            
            dense_query = list(dense_model.embed([query]))[0].tolist()
            sparse_query_embedding = list(sparse_model.embed([query]))[0]
            sparse_query = models.SparseVector(
                indices=sparse_query_embedding.indices.tolist(),
                values=sparse_query_embedding.values.tolist()
            )
            
            embedding_time = int((time.time() - start_time) * 1000)
            
        except Exception as e:
            logger.error(f"Embedding generation error: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': f'Embedding error: {str(e)}'})}\n\n"
            return
        
        # Step 3: Hybrid search
        yield f"data: {json.dumps({'type': 'step', 'action': 'retrieve', 'title': 'Hybrid Search (RRF)', 'description': 'Searching with dense + sparse vectors, fusing with Reciprocal Rank Fusion'})}\n\n"
        await asyncio.sleep(0.5)
        
        search_start = time.time()
        
        try:
            qdrant_client = self._get_qdrant_client()
            
            results = qdrant_client.query_points(
                collection_name=COLLECTION_NAME,
                prefetch=[
                    models.Prefetch(
                        query=dense_query,
                        using=DENSE_VECTOR_NAME,
                        limit=20
                    ),
                    models.Prefetch(
                        query=sparse_query,
                        using=SPARSE_VECTOR_NAME,
                        limit=20
                    ),
                ],
                query=models.FusionQuery(fusion=models.Fusion.RRF),
                limit=10,
            )
            
            search_time = int((time.time() - search_start) * 1000)
            
            yield f"data: {json.dumps({'type': 'step', 'action': 'rank', 'title': 'Retrieved Statutes', 'description': f'Found {len(results.points)} relevant statutes', 'metadata': {'count': len(results.points), 'time': search_time}})}\n\n"
            
        except Exception as e:
            logger.error(f"Search error: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': f'Search error: {str(e)}'})}\n\n"
            return
        
        # Step 4: Generate answer (optional)
        answer = None
        if self.openai_api_key and results.points:
            yield f"data: {json.dumps({'type': 'step', 'action': 'analyze', 'title': 'Generating Analysis', 'description': 'Synthesizing legal analysis with GPT-4'})}\n\n"
            await asyncio.sleep(0.5)
            
            try:
                context = "\n\n".join([
                    f"[{i+1}] {p.payload.get('citation', 'Unknown')}\n{p.payload.get('text', '')[:400]}"
                    for i, p in enumerate(results.points[:5])
                ])
                
                prompt = f"""Based on these California housing law statutes, provide a clear legal analysis.

Question: {query}

Statutes:
{context}

Provide a comprehensive answer citing specific statutes:"""
                
                openai_client = self._get_openai_client()
                response = openai_client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.3,
                    max_tokens=500
                )
                
                answer = response.choices[0].message.content.strip()
                
            except Exception as e:
                logger.warning(f"Answer generation error: {e}")
                # Continue without answer
        
        # Step 5: Return results
        statutes = [
            {
                'citation': p.payload.get('citation', 'Unknown'),
                'text': p.payload.get('text', ''),
                'path': p.payload.get('path', ''),
                'score': p.score,
                'statute_idx': p.payload.get('statute_idx'),
            }
            for p in results.points
        ]
        
        avg_score = sum(p.score for p in results.points) / len(results.points) if results.points else 0
        
        yield f"data: {json.dumps({'type': 'result', 'statutes': statutes, 'answer': answer, 'search_time': search_time + embedding_time, 'avg_score': avg_score})}\n\n"

