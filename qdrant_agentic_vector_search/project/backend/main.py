"""
FastAPI backend for Agentic RAG Demo.
Provides three search approaches: Simple Search, Simple RAG, and Agentic RAG.
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from contextlib import asynccontextmanager
import logging
from dotenv import load_dotenv
import os

from models import (
    SearchRequest,
    SimpleSearchResponse,
    SimpleRAGResponse,
    HealthResponse,
    DocumentListResponse
)
from services.qdrant_service import QdrantService
from services.search_service import SearchService
from services.crew_service import CrewService
from services.california_service import CaliforniaService
from services.quiz_service_simple import QuizServiceSimple
from services.workflow_service import WorkflowService
from services.eval_service import EvaluationService

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize services
qdrant_service = None
search_service = None
crew_service = None
california_service = None
quiz_service = None
workflow_service = None
eval_service = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize services on startup."""
    global qdrant_service, search_service, crew_service, california_service, quiz_service, workflow_service, eval_service
    
    logger.info("Initializing services...")
    
    # Initialize Qdrant service
    qdrant_url = os.getenv("QDRANT_CLOUD_URL") or os.getenv("QDRANT_URL", "http://localhost:6333")
    qdrant_api_key = os.getenv("QDRANT_API_KEY")
    collection_name = os.getenv("QDRANT_COLLECTION", "legal_docs")
    
    qdrant_service = QdrantService(
        url=qdrant_url,
        api_key=qdrant_api_key,
        collection_name=collection_name
    )
    
    # Initialize search service
    search_service = SearchService(qdrant_service)
    
    # Initialize crew service
    crew_service = CrewService(qdrant_service)
    
    # Initialize California service
    california_service = CaliforniaService()
    
    # Initialize quiz service (simple version for faster responses)
    quiz_service = QuizServiceSimple()
    
    # Initialize workflow service
    workflow_service = WorkflowService()
    
    # Initialize evaluation service
    eval_service = EvaluationService(
        qdrant_url=qdrant_url,
        collection_name="california_housing_test"
    )
    
    logger.info("Services initialized successfully")
    
    yield
    
    logger.info("Shutting down services...")


# Create FastAPI app
app = FastAPI(
    title="Agentic RAG Demo API",
    description="Backend API for demonstrating Simple Search, Simple RAG, and Agentic RAG",
    version="1.0.0",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "https://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    try:
        # Check Qdrant connection
        is_connected = await qdrant_service.health_check()
        
        return HealthResponse(
            status="healthy" if is_connected else "unhealthy",
            services={
                "qdrant": "connected" if is_connected else "disconnected",
                "openai": "configured" if os.getenv("OPENAI_API_KEY") else "not configured"
            }
        )
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return HealthResponse(
            status="unhealthy",
            services={"error": str(e)}
        )


@app.get("/api/documents", response_model=DocumentListResponse)
async def list_documents():
    """List all available documents in the collection."""
    try:
        documents = await qdrant_service.get_all_documents()
        return DocumentListResponse(
            documents=documents,
            total=len(documents)
        )
    except Exception as e:
        logger.error(f"Error listing documents: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/search/simple", response_model=SimpleSearchResponse)
async def simple_search(request: SearchRequest):
    """
    Simple keyword search using BM25.
    Returns top matching documents without semantic understanding.
    """
    try:
        logger.info(f"Simple search: {request.query}")
        results = await search_service.simple_search(
            query=request.query,
            top_k=request.top_k or 3
        )
        return results
    except Exception as e:
        logger.error(f"Simple search error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/search/simple-rag", response_model=SimpleRAGResponse)
async def simple_rag(request: SearchRequest):
    """
    Simple RAG: Single vector search + LLM generation.
    Retrieves relevant chunks and generates answer in one step.
    """
    try:
        logger.info(f"Simple RAG: {request.query}")
        results = await search_service.simple_rag(
            query=request.query,
            top_k=request.top_k or 5
        )
        return results
    except Exception as e:
        logger.error(f"Simple RAG error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/search/agentic-rag")
async def agentic_rag(request: SearchRequest):
    """
    Agentic RAG: Multi-step reasoning with CrewAI.
    Streams the agent's reasoning process in real-time.
    """
    try:
        logger.info(f"Agentic RAG: {request.query}")
        
        # Return streaming response
        return StreamingResponse(
            crew_service.run_agentic_search(query=request.query),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"
            }
        )
    except Exception as e:
        logger.error(f"Agentic RAG error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/research")
async def california_research(request: SearchRequest):
    """
    California Housing Law Research with Hybrid Search.
    Streams the agent's reasoning process with RRF hybrid search.
    """
    try:
        logger.info(f"California Research: {request.query}")
        
        # Return streaming response
        return StreamingResponse(
            california_service.research_flow(query=request.query),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"
            }
        )
    except Exception as e:
        logger.error(f"California research error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/quiz/question")
async def get_quiz_question():
    """Get a random California question for quiz mode."""
    try:
        question = quiz_service.get_random_question()
        return question
    except Exception as e:
        logger.error(f"Quiz question error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/quiz/answer")
async def submit_quiz_answer(request: dict):
    """
    Submit quiz answer and get AI's answer + evaluation with verbose CrewAI output.
    
    Streams the agent's reasoning process in real-time.
    
    Request:
        - question: str
        - golden_answer: str
        - golden_statute_ids: List[int]
        - user_answer: str
    """
    try:
        logger.info(f"Quiz answer submission: {request['question'][:50]}...")
        
        return StreamingResponse(
            quiz_service.evaluate_answer_streaming(
                question=request['question'],
                golden_answer=request['golden_answer'],
                golden_statute_ids=request['golden_statute_ids'],
                user_answer=request['user_answer']
            ),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"
            }
        )
    except Exception as e:
        logger.error(f"Quiz answer error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/workflow")
async def generate_workflow(request: dict):
    """
    Generate procedural workflow using CrewAI agent with custom legal tools.
    
    Streams the agent's process showing tool calls and reasoning.
    
    Request:
        - query: str (e.g., "How do I evict for nonpayment?")
        - city: str (optional, e.g., "Los Angeles")
    """
    try:
        logger.info(f"Workflow generation: {request.get('query', '')[:50]}...")
        
        return StreamingResponse(
            workflow_service.generate_workflow(
                query=request['query'],
                city=request.get('city')
            ),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"
            }
        )
    except Exception as e:
        logger.error(f"Workflow generation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/eval/run")
async def run_evaluation(request: dict):
    """
    Run an evaluation experiment.
    
    Request:
        - embedding_model: str (e.g., "bge-small")
        - retrieval_mode: str (e.g., "Dense (Semantic)")
        - top_k: int (e.g., 5)
        - noise_level: int (0-100)
    """
    try:
        logger.info(f"Running evaluation: {request}")
        
        result = await eval_service.run_experiment(
            embedding_model=request["embedding_model"],
            retrieval_mode=request["retrieval_mode"],
            top_k=request["top_k"],
            noise_level=request.get("noise_level", 0)
        )
        
        return result
    except Exception as e:
        logger.error(f"Evaluation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/eval/results")
async def get_eval_results():
    """Get all evaluation results."""
    try:
        results = eval_service.get_all_results()
        return {"results": results, "total": len(results)}
    except Exception as e:
        logger.error(f"Error getting results: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/eval/leaderboard")
async def get_eval_leaderboard():
    """Get evaluation leaderboard sorted by recall."""
    try:
        leaderboard = eval_service.get_leaderboard(limit=10)
        return {"leaderboard": leaderboard}
    except Exception as e:
        logger.error(f"Error getting leaderboard: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )

