"""
Quiz Service - Interactive quiz mode with golden questions and CrewAI verbose output
"""

import os
import random
import asyncio
import json
from typing import Dict, List, AsyncGenerator, Any
from qdrant_client import QdrantClient, models
from fastembed import TextEmbedding, SparseTextEmbedding
from openai import OpenAI
from crewai import Agent, Task, Crew, LLM
from crewai.tools import BaseTool
from pydantic import BaseModel, Field
import logging

logger = logging.getLogger(__name__)

QUESTIONS_COLLECTION = "california_housing_questions"
STATUTES_COLLECTION = "california_housing_statutes_full"
DENSE_VECTOR_NAME = "dense"
SPARSE_VECTOR_NAME = "sparse"


class HybridSearchInput(BaseModel):
    """Input schema for hybrid search tool."""
    query: str = Field(..., description="Search query for statutes")
    top_k: int = Field(5, description="Number of results to return")


class HybridSearchTool(BaseTool):
    """Tool for hybrid search with RRF."""
    
    name: str = "hybrid_search"
    description: str = "Search California housing statutes using hybrid search (dense + sparse + RRF fusion)"
    args_schema: type[BaseModel] = HybridSearchInput
    
    qdrant_client: Any = None
    dense_model: Any = None
    sparse_model: Any = None
    
    class Config:
        arbitrary_types_allowed = True
    
    def _run(self, query: str, top_k: int = 5, **kwargs) -> str:
        """Execute hybrid search."""
        try:
            # Generate embeddings
            dense_query = list(self.dense_model.embed([query]))[0].tolist()
            sparse_query_embedding = list(self.sparse_model.embed([query]))[0]
            sparse_query = models.SparseVector(
                indices=sparse_query_embedding.indices.tolist(),
                values=sparse_query_embedding.values.tolist()
            )
            
            # Hybrid search with RRF
            results = self.qdrant_client.query_points(
                collection_name=STATUTES_COLLECTION,
                prefetch=[
                    models.Prefetch(query=dense_query, using=DENSE_VECTOR_NAME, limit=20),
                    models.Prefetch(query=sparse_query, using=SPARSE_VECTOR_NAME, limit=20),
                ],
                query=models.FusionQuery(fusion=models.Fusion.RRF),
                limit=top_k,
            )
            
            # Format results
            formatted = []
            for i, point in enumerate(results.points, 1):
                formatted.append(
                    f"[{i}] {point.payload.get('citation', 'Unknown')}\n"
                    f"Score: {point.score:.3f}\n"
                    f"Text: {point.payload.get('text', '')[:300]}...\n"
                )
            
            return "\n".join(formatted) if formatted else "No results found."
            
        except Exception as e:
            logger.error(f"Hybrid search error: {e}")
            return f"Error: {str(e)}"


class QuizService:
    """Service for quiz mode functionality."""
    
    def __init__(self):
        """Initialize quiz service."""
        self.qdrant_client = None
        self.dense_model = None
        self.sparse_model = None
        self.openai_client = None
        
        # Get credentials
        self.qdrant_url = os.getenv('QDRANT_CLOUD_URL')
        self.qdrant_api_key = os.getenv('QDRANT_API_KEY')
        self.openai_api_key = os.getenv('OPENAI_API_KEY')
        
        logger.info("Quiz service initialized (lazy loading)")
    
    def _get_qdrant_client(self):
        """Lazy load Qdrant client."""
        if self.qdrant_client is None:
            self.qdrant_client = QdrantClient(
                url=self.qdrant_url,
                api_key=self.qdrant_api_key
            )
        return self.qdrant_client
    
    def _get_dense_model(self):
        """Lazy load dense model."""
        if self.dense_model is None:
            self.dense_model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
        return self.dense_model
    
    def _get_sparse_model(self):
        """Lazy load sparse model."""
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
    
    def get_random_question(self) -> Dict:
        """Get a random California question from the questions collection."""
        client = self._get_qdrant_client()
        
        # Get total count
        info = client.get_collection(QUESTIONS_COLLECTION)
        total_points = info.points_count
        
        # Pick random point
        random_id = random.randint(0, total_points - 1)
        
        # Retrieve the question
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
        """
        Evaluate answer with verbose CrewAI output streaming.
        Shows the agent's actual reasoning process.
        """
        
        # Yield user's answer first
        user_correct = user_answer.lower() == golden_answer.lower()
        yield f"data: {json.dumps({'type': 'user_result', 'answer': user_answer, 'correct': user_correct})}\n\n"
        await asyncio.sleep(0.3)
        
        # Initialize models
        yield f"data: {json.dumps({'type': 'agent_step', 'step': 'Initializing AI agent...', 'detail': 'Loading hybrid search models'})}\n\n"
        
        dense_model = self._get_dense_model()
        sparse_model = self._get_sparse_model()
        client = self._get_qdrant_client()
        
        # Create hybrid search tool
        search_tool = HybridSearchTool(
            qdrant_client=client,
            dense_model=dense_model,
            sparse_model=sparse_model
        )
        
        # Create CrewAI agent with verbose output
        yield f"data: {json.dumps({'type': 'agent_step', 'step': 'Creating legal research agent...', 'detail': 'Configuring with hybrid search capabilities'})}\n\n"
        await asyncio.sleep(0.3)
        
        llm = LLM(
            model="gpt-4o-mini",
            temperature=0.1,
            api_key=self.openai_api_key
        )
        
        legal_agent = Agent(
            role="California Housing Law Expert",
            goal="Answer legal questions accurately using California housing statutes",
            backstory="""You are an expert legal researcher specializing in California housing law.
            You have access to hybrid search tools that combine semantic and keyword search.
            You must find relevant statutes and answer questions with Yes or No based on the law.""",
            tools=[search_tool],
            llm=llm,
            verbose=True,
            allow_delegation=False
        )
        
        # Create task
        task = Task(
            description=f"""Research this California housing law question and answer with Yes or No:

Question: {question}

Steps:
1. Use hybrid_search to find relevant California housing statutes
2. Analyze the statutes carefully
3. Answer with ONLY "Yes" or "No" based on what the statutes say

Your final answer must be just "Yes" or "No".""",
            agent=legal_agent,
            expected_output="Yes or No"
        )
        
        # Create crew
        crew = Crew(
            agents=[legal_agent],
            tasks=[task],
            verbose=True
        )
        
        # Yield that we're starting the agent
        yield f"data: {json.dumps({'type': 'agent_step', 'step': 'Agent starting research...', 'detail': 'Running CrewAI with hybrid search'})}\n\n"
        await asyncio.sleep(0.3)
        
        # Capture CrewAI output
        import sys
        from io import StringIO
        
        # Redirect stdout to capture verbose output
        old_stdout = sys.stdout
        sys.stdout = captured_output = StringIO()
        
        try:
            # Run crew
            result = crew.kickoff()
            
            # Get the captured output
            verbose_output = captured_output.getvalue()
            
            # Restore stdout
            sys.stdout = old_stdout
            
            # Stream the verbose output line by line
            lines = verbose_output.split('\n')
            for line in lines:
                if line.strip():
                    yield f"data: {json.dumps({'type': 'agent_output', 'line': line})}\n\n"
                    await asyncio.sleep(0.05)  # Small delay for readability
            
            ai_answer = str(result).strip()
            
        except Exception as e:
            sys.stdout = old_stdout
            logger.error(f"CrewAI error: {e}")
            ai_answer = "Error"
        
        # Run retrieval evaluation separately
        dense_query = list(dense_model.embed([question]))[0].tolist()
        sparse_query_embedding = list(sparse_model.embed([question]))[0]
        sparse_query = models.SparseVector(
            indices=sparse_query_embedding.indices.tolist(),
            values=sparse_query_embedding.values.tolist()
        )
        
        results = client.query_points(
            collection_name=STATUTES_COLLECTION,
            prefetch=[
                models.Prefetch(query=dense_query, using=DENSE_VECTOR_NAME, limit=20),
                models.Prefetch(query=sparse_query, using=SPARSE_VECTOR_NAME, limit=20),
            ],
            query=models.FusionQuery(fusion=models.Fusion.RRF),
            limit=5,
        )
        
        # Calculate metrics
        retrieved_statute_ids = [p.payload.get('statute_idx') for p in results.points]
        golden_set = set(golden_statute_ids)
        retrieved_set = set(retrieved_statute_ids)
        intersection = golden_set & retrieved_set
        
        recall = len(intersection) / len(golden_set) if golden_set else 0
        precision = len(intersection) / len(retrieved_set) if retrieved_set else 0
        ai_correct = ai_answer and (golden_answer.lower() in ai_answer.lower())
        
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
        
        # Send final result
        yield f"data: {json.dumps({'type': 'result', 'ai_answer': ai_answer, 'ai_correct': ai_correct, 'recall': recall, 'precision': precision, 'retrieved_statutes': retrieved_statutes})}\n\n"
    
    def evaluate_answer(
        self,
        question: str,
        golden_answer: str,
        golden_statute_ids: List[int],
        user_answer: str
    ) -> Dict:
        """
        Evaluate user's answer and compare with AI's answer.
        
        Returns:
            - AI's answer
            - Retrieved statutes
            - Recall (% of golden statutes found)
            - Precision (% of retrieved that are golden)
            - Whether AI was correct
        """
        
        # Run hybrid search
        dense_model = self._get_dense_model()
        sparse_model = self._get_sparse_model()
        client = self._get_qdrant_client()
        
        # Generate embeddings
        dense_query = list(dense_model.embed([question]))[0].tolist()
        sparse_query_embedding = list(sparse_model.embed([question]))[0]
        sparse_query = models.SparseVector(
            indices=sparse_query_embedding.indices.tolist(),
            values=sparse_query_embedding.values.tolist()
        )
        
        # Hybrid search
        results = client.query_points(
            collection_name=STATUTES_COLLECTION,
            prefetch=[
                models.Prefetch(query=dense_query, using=DENSE_VECTOR_NAME, limit=20),
                models.Prefetch(query=sparse_query, using=SPARSE_VECTOR_NAME, limit=20),
            ],
            query=models.FusionQuery(fusion=models.Fusion.RRF),
            limit=5,
        )
        
        # Extract retrieved statute IDs
        retrieved_statute_ids = [p.payload.get('statute_idx') for p in results.points]
        
        # Calculate metrics
        golden_set = set(golden_statute_ids)
        retrieved_set = set(retrieved_statute_ids)
        
        intersection = golden_set & retrieved_set
        
        recall = len(intersection) / len(golden_set) if golden_set else 0
        precision = len(intersection) / len(retrieved_set) if retrieved_set else 0
        
        # Generate AI answer
        ai_answer = None
        if self.openai_api_key and results.points:
            openai_client = self._get_openai_client()
            
            context = "\n\n".join([
                f"[{i+1}] {p.payload.get('citation', 'Unknown')}\n{p.payload.get('text', '')[:300]}"
                for i, p in enumerate(results.points)
            ])
            
            prompt = f"""Based on these California housing law statutes, answer with Yes or No.

Question: {question}

Statutes:
{context}

Answer (Yes or No only):"""
            
            try:
                response = openai_client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0,
                    max_tokens=10
                )
                ai_answer = response.choices[0].message.content.strip()
            except Exception as e:
                logger.error(f"OpenAI error: {e}")
                ai_answer = "Error"
        
        # Check if AI was correct
        ai_correct = ai_answer and (golden_answer.lower() in ai_answer.lower())
        
        # Format retrieved statutes
        retrieved_statutes = [
            {
                'citation': p.payload.get('citation', 'Unknown'),
                'text': p.payload.get('text', '')[:200],
                'score': p.score,
                'statute_idx': p.payload.get('statute_idx'),
            }
            for p in results.points
        ]
        
        return {
            'ai_answer': ai_answer,
            'retrieved_statutes': retrieved_statutes,
            'recall': recall,
            'precision': precision,
            'ai_correct': ai_correct,
            'retrieved_count': len(retrieved_statute_ids),
            'golden_count': len(golden_statute_ids),
        }

