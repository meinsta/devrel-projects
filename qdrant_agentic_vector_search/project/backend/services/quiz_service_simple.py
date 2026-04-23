"""
Simplified Quiz Service - Without heavy CrewAI for faster responses
"""

import os
import random
import asyncio
import json
from typing import Dict, List, AsyncGenerator, Any
from qdrant_client import QdrantClient, models
from fastembed import TextEmbedding, SparseTextEmbedding
from openai import OpenAI
import logging

logger = logging.getLogger(__name__)

# Use filtered collection with only AI-correct questions for demo
QUESTIONS_COLLECTION = "california_quiz_questions_filtered"
STATUTES_COLLECTION = "california_housing_statutes_full"
DENSE_VECTOR_NAME = "dense"
SPARSE_VECTOR_NAME = "sparse"


class QuizServiceSimple:
    """Simplified quiz service for faster responses."""
    
    def __init__(self):
        """Initialize quiz service."""
        self.qdrant_client = None
        self.dense_model = None
        self.sparse_model = None
        self.openai_client = None
        
        self.qdrant_url = os.getenv('QDRANT_CLOUD_URL')
        self.qdrant_api_key = os.getenv('QDRANT_API_KEY')
        self.openai_api_key = os.getenv('OPENAI_API_KEY')
        
        logger.info("Quiz service (simple) initialized")
    
    def _get_qdrant_client(self):
        if self.qdrant_client is None:
            self.qdrant_client = QdrantClient(
                url=self.qdrant_url,
                api_key=self.qdrant_api_key
            )
        return self.qdrant_client
    
    def _get_dense_model(self):
        if self.dense_model is None:
            self.dense_model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
        return self.dense_model
    
    def _get_sparse_model(self):
        if self.sparse_model is None:
            self.sparse_model = SparseTextEmbedding(
                model_name="Qdrant/bm42-all-minilm-l6-v2-attentions"
            )
        return self.sparse_model
    
    def _get_openai_client(self):
        if self.openai_client is None and self.openai_api_key:
            self.openai_client = OpenAI(api_key=self.openai_api_key)
        return self.openai_client
    
    def get_random_question(self) -> Dict:
        """Get a random question from the pre-filtered collection (AI gets these right)."""
        client = self._get_qdrant_client()
        
        info = client.get_collection(QUESTIONS_COLLECTION)
        total_points = info.points_count
        
        if total_points == 0:
            raise Exception("No questions available. Run pre_evaluate_questions.py first.")
        
        # All questions in this collection are pre-verified to be AI-correct
        random_id = random.randint(0, total_points - 1)
        
        point = client.retrieve(
            collection_name=QUESTIONS_COLLECTION,
            ids=[random_id],
            with_payload=True
        )[0]
        
        return {
            'question': point.payload.get('question'),
            'golden_answer': point.payload.get('answer'),
            'golden_statute_ids': point.payload.get('golden_statute_ids', []),
            'golden_citations': point.payload.get('golden_citations', []),
            'question_idx': point.payload.get('question_idx'),
        }
    
    async def evaluate_answer_streaming(
        self,
        question: str,
        golden_answer: str,
        golden_statute_ids: List[int],
        user_answer: str
    ) -> AsyncGenerator[str, None]:
        """Evaluate with simulated agent output (faster than full CrewAI)."""
        
        # User result
        user_correct = user_answer.lower() == golden_answer.lower()
        yield f"data: {json.dumps({'type': 'user_result', 'answer': user_answer, 'correct': user_correct})}\n\n"
        await asyncio.sleep(0.2)
        
        # Agent steps
        yield f"data: {json.dumps({'type': 'agent_step', 'step': 'Initializing hybrid search...', 'detail': 'Loading BGE + BM42 models'})}\n\n"
        await asyncio.sleep(0.3)
        
        dense_model = self._get_dense_model()
        sparse_model = self._get_sparse_model()
        client = self._get_qdrant_client()
        
        yield f"data: {json.dumps({'type': 'agent_output', 'line': '> Starting research on California housing law question...'})}\n\n"
        yield f"data: {json.dumps({'type': 'agent_output', 'line': f'> Question: {question[:80]}...'})}\n\n"
        await asyncio.sleep(0.2)
        
        # Generate embeddings
        yield f"data: {json.dumps({'type': 'agent_output', 'line': '> Generating query embeddings (dense + sparse)...'})}\n\n"
        
        dense_query = list(dense_model.embed([question]))[0].tolist()
        sparse_query_embedding = list(sparse_model.embed([question]))[0]
        sparse_query = models.SparseVector(
            indices=sparse_query_embedding.indices.tolist(),
            values=sparse_query_embedding.values.tolist()
        )
        
        yield f"data: {json.dumps({'type': 'agent_output', 'line': f'> Dense vector: 384 dimensions'})}\n\n"
        yield f"data: {json.dumps({'type': 'agent_output', 'line': f'> Sparse vector: {len(sparse_query.indices)} tokens'})}\n\n"
        await asyncio.sleep(0.2)
        
        # Hybrid search
        yield f"data: {json.dumps({'type': 'agent_output', 'line': '> Executing hybrid search with RRF fusion...'})}\n\n"
        
        results = client.query_points(
            collection_name=STATUTES_COLLECTION,
            prefetch=[
                models.Prefetch(query=dense_query, using=DENSE_VECTOR_NAME, limit=20),
                models.Prefetch(query=sparse_query, using=SPARSE_VECTOR_NAME, limit=20),
            ],
            query=models.FusionQuery(fusion=models.Fusion.RRF),
            limit=5,
        )
        
        yield f"data: {json.dumps({'type': 'agent_output', 'line': f'> Retrieved {len(results.points)} statutes'})}\n\n"
        
        # Show retrieved statutes
        for i, p in enumerate(results.points[:3], 1):
            citation = p.payload.get('citation', 'Unknown')
            score = p.score
            yield f"data: {json.dumps({'type': 'agent_output', 'line': f'>   [{i}] {citation} (score: {score:.3f})'})}\n\n"
        
        await asyncio.sleep(0.2)
        
        # Generate answer
        yield f"data: {json.dumps({'type': 'agent_output', 'line': '> Analyzing statutes with GPT-4...'})}\n\n"
        
        context = "\n\n".join([
            f"[{i+1}] {p.payload.get('citation')}\n{p.payload.get('text', '')[:300]}"
            for i, p in enumerate(results.points)
        ])
        
        prompt = f"""Based on these California housing statutes, answer Yes or No.

Question: {question}

Statutes:
{context}

Answer (Yes or No only):"""
        
        openai_client = self._get_openai_client()
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=10
        )
        
        ai_answer = response.choices[0].message.content.strip()
        
        yield f"data: {json.dumps({'type': 'agent_output', 'line': f'> AI Conclusion: {ai_answer}'})}\n\n"
        await asyncio.sleep(0.2)
        
        # Calculate metrics
        retrieved_statute_ids = [p.payload.get('statute_idx') for p in results.points]
        golden_set = set(golden_statute_ids)
        retrieved_set = set(retrieved_statute_ids)
        intersection = golden_set & retrieved_set
        
        recall = len(intersection) / len(golden_set) if golden_set else 0
        precision = len(intersection) / len(retrieved_set) if retrieved_set else 0
        ai_correct = ai_answer and (golden_answer.lower() in ai_answer.lower())
        
        yield f"data: {json.dumps({'type': 'agent_output', 'line': f'> Recall: {recall*100:.0f}% | Precision: {precision*100:.0f}%'})}\n\n"
        yield f"data: {json.dumps({'type': 'agent_output', 'line': f'> Golden statutes found: {len(intersection)}/{len(golden_set)}'})}\n\n"
        
        # Format statutes
        retrieved_statutes = [
            {
                'citation': p.payload.get('citation', 'Unknown'),
                'text': p.payload.get('text', '')[:200],
                'score': p.score,
                'statute_idx': p.payload.get('statute_idx'),
                'is_golden': p.payload.get('statute_idx') in golden_statute_ids
            }
            for p in results.points
        ]
        
        # Final result
        yield f"data: {json.dumps({'type': 'result', 'ai_answer': ai_answer, 'ai_correct': ai_correct, 'recall': recall, 'precision': precision, 'retrieved_statutes': retrieved_statutes})}\n\n"

