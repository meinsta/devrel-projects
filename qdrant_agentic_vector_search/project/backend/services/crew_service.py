"""
CrewAI service for agentic RAG with multi-step reasoning.
Includes custom callbacks for streaming agent thoughts and actions.
"""

from typing import AsyncGenerator, Dict, Any, List
import json
import time
import logging
import asyncio
from datetime import datetime
from crewai import Agent, Task, Crew, LLM
from crewai.tools import BaseTool
from pydantic import BaseModel, Field
import os

from services.qdrant_service import QdrantService
from models import SSEEvent, AgenticStep, VectorSearchStep, SearchResult, DocumentMetadata

logger = logging.getLogger(__name__)


class LegalSearchInput(BaseModel):
    """Input schema for legal search tool."""
    query: str = Field(..., description="Search query for legal documents")
    top_k: int = Field(5, description="Number of results to return")


class LegalSearchTool(BaseTool):
    """Custom tool for searching legal documents with event streaming."""
    
    name: str = "legal_search"
    description: str = "Search legal documents database for relevant statutes, cases, and regulations"
    args_schema: type[BaseModel] = LegalSearchInput
    
    # Custom attributes
    qdrant_service: Any
    event_queue: Any  # asyncio.Queue for streaming events
    
    class Config:
        arbitrary_types_allowed = True
    
    def _run(self, query: str, top_k: int = 5, **kwargs) -> str:
        """Execute search and emit event."""
        try:
            # Run async search in sync context
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            results = loop.run_until_complete(
                self.qdrant_service.search(query=query, top_k=top_k)
            )
            loop.close()
            
            # Format results for agent
            formatted = []
            for i, result in enumerate(results, 1):
                formatted.append(
                    f"[{i}] {result['metadata']['citation']}\n"
                    f"Score: {result['score']:.3f}\n"
                    f"Text: {result['text'][:300]}...\n"
                )
            
            result_text = "\n".join(formatted)
            
            # Emit search event (non-blocking)
            if self.event_queue:
                try:
                    # Create event data
                    event_data = {
                        "query_text": query,
                        "retrieved_count": len(results),
                        "results": [
                            {
                                "text": r['text'][:200],
                                "score": r['score'],
                                "citation": r['metadata']['citation']
                            }
                            for r in results
                        ]
                    }
                    
                    # Put in queue without blocking
                    self.event_queue.put_nowait({
                        "type": "vector_search",
                        "data": event_data
                    })
                except Exception as e:
                    logger.warning(f"Failed to emit search event: {e}")
            
            return result_text if result_text else "No relevant documents found."
        
        except Exception as e:
            logger.error(f"Search tool error: {e}")
            return f"Error searching: {str(e)}"


class CrewService:
    """Service for agentic RAG using CrewAI."""
    
    def __init__(self, qdrant_service: QdrantService):
        """Initialize crew service."""
        self.qdrant_service = qdrant_service
        self.llm = LLM(model="gpt-4o-mini", temperature=0.2)
        logger.info("Crew service initialized")
    
    def _create_agents_and_tasks(
        self,
        query: str,
        search_tool: LegalSearchTool
    ) -> tuple[List[Agent], List[Task]]:
        """Create agents and tasks for the crew."""
        
        # Agent 1: Research Agent - Formulates queries and retrieves documents
        research_agent = Agent(
            role="Legal Research Specialist",
            goal="Find all relevant legal documents by formulating multiple search queries",
            backstory="""You are an expert legal researcher. You break down complex 
            questions into multiple search queries to ensure comprehensive document retrieval.
            You think about synonyms, related concepts, and different ways to phrase searches.""",
            tools=[search_tool],
            verbose=True,
            llm=self.llm,
            max_iter=4
        )
        
        # Agent 2: Analysis Agent - Examines documents and identifies gaps
        analysis_agent = Agent(
            role="Legal Document Analyzer",
            goal="Analyze retrieved documents and identify missing information",
            backstory="""You are a meticulous legal analyst. You examine documents carefully,
            identify what information is present, what is missing, and what additional 
            searches might be needed. You think critically about context and cross-references.""",
            tools=[search_tool],
            verbose=True,
            llm=self.llm,
            max_iter=3
        )
        
        # Agent 3: Synthesis Agent - Provides final answer
        synthesis_agent = Agent(
            role="Legal Expert",
            goal="Synthesize information and provide accurate legal answer",
            backstory="""You are a senior legal expert. You synthesize information from 
            multiple sources, reason across documents, and provide well-supported answers.
            You cite specific sources and acknowledge limitations in your analysis.""",
            verbose=True,
            llm=self.llm,
            allow_delegation=False
        )
        
        # Task 1: Initial Research
        research_task = Task(
            description=f"""Research the following legal question by searching the database:

Question: {query}

Your task:
1. Break down the question into 2-3 different search queries
2. Search for each query to gather relevant documents
3. Summarize what you found and what might be missing

Be thorough and think about different angles to search from.""",
            agent=research_agent,
            expected_output="Summary of search queries used and key documents found"
        )
        
        # Task 2: Analysis
        analysis_task = Task(
            description=f"""Analyze the documents found by the researcher for this question:

Question: {query}

Your task:
1. Review the documents that were retrieved
2. Identify any gaps in information
3. Perform additional targeted searches if needed
4. Prepare a comprehensive analysis of relevant information

Focus on finding all necessary context and cross-references.""",
            agent=analysis_agent,
            expected_output="Analysis of documents with identified gaps and additional findings",
            context=[research_task]
        )
        
        # Task 3: Synthesis
        synthesis_task = Task(
            description=f"""Provide a final answer to this legal question:

Question: {query}

Your task:
1. Synthesize all information gathered by the research and analysis teams
2. Provide a clear, well-reasoned answer
3. Cite specific documents and sections
4. Acknowledge any limitations or uncertainties

Be precise and legally accurate.""",
            agent=synthesis_agent,
            expected_output="Clear answer with citations and reasoning",
            context=[research_task, analysis_task]
        )
        
        return (
            [research_agent, analysis_agent, synthesis_agent],
            [research_task, analysis_task, synthesis_task]
        )
    
    async def run_agentic_search(
        self,
        query: str
    ) -> AsyncGenerator[str, None]:
        """
        Run agentic search with streaming updates.
        
        Yields SSE-formatted events with agent reasoning steps.
        """
        start_time = time.time()
        step_number = 0
        
        try:
            # Create event queue for streaming
            event_queue = asyncio.Queue()
            
            # Create search tool with event queue
            search_tool = LegalSearchTool(
                qdrant_service=self.qdrant_service,
                event_queue=event_queue
            )
            
            # Emit start event
            step_number += 1
            event = SSEEvent(
                event="step",
                data={
                    "step_number": step_number,
                    "step_type": "query_analysis",
                    "agent_name": "System",
                    "description": "Starting agentic search",
                    "content": {
                        "message": f"Analyzing query: {query}",
                        "query": query
                    },
                    "timestamp": datetime.now().isoformat()
                }
            )
            yield event.format()
            
            # Create agents and tasks
            agents, tasks = self._create_agents_and_tasks(query, search_tool)
            
            # Create crew
            crew = Crew(
                agents=agents,
                tasks=tasks,
                verbose=True
            )
            
            # Emit agent initialization
            step_number += 1
            event = SSEEvent(
                event="step",
                data={
                    "step_number": step_number,
                    "step_type": "reasoning",
                    "agent_name": "System",
                    "description": "Initializing multi-agent crew",
                    "content": {
                        "agents": [
                            {"name": a.role, "goal": a.goal}
                            for a in agents
                        ]
                    },
                    "timestamp": datetime.now().isoformat()
                }
            )
            yield event.format()
            
            # Run crew in background and monitor event queue
            crew_task = asyncio.create_task(
                asyncio.to_thread(crew.kickoff)
            )
            
            # Stream events as they come
            documents_accessed = set()
            total_searches = 0
            
            while not crew_task.done():
                try:
                    # Check for events with timeout
                    event_data = await asyncio.wait_for(
                        event_queue.get(),
                        timeout=0.5
                    )
                    
                    step_number += 1
                    total_searches += 1
                    
                    # Process vector search event
                    if event_data["type"] == "vector_search":
                        data = event_data["data"]
                        
                        # Track documents
                        for result in data["results"]:
                            documents_accessed.add(result["citation"])
                        
                        # Emit event
                        event = SSEEvent(
                            event="step",
                            data={
                                "step_number": step_number,
                                "step_type": "vector_search",
                                "agent_name": "Search System",
                                "description": f"Vector search: {data['query_text'][:50]}...",
                                "content": {
                                    "query": data["query_text"],
                                    "results_count": data["retrieved_count"],
                                    "results": data["results"]
                                },
                                "timestamp": datetime.now().isoformat()
                            }
                        )
                        yield event.format()
                
                except asyncio.TimeoutError:
                    # No events, continue waiting
                    continue
            
            # Get final result
            result = await crew_task
            
            # Emit final answer
            step_number += 1
            total_time_ms = (time.time() - start_time) * 1000
            
            event = SSEEvent(
                event="complete",
                data={
                    "step_number": step_number,
                    "step_type": "synthesis",
                    "agent_name": "Legal Expert",
                    "description": "Final answer",
                    "content": {
                        "query": query,
                        "answer": str(result),
                        "documents_accessed": list(documents_accessed),
                        "total_searches": total_searches,
                        "total_time_ms": total_time_ms,
                        "confidence": "high"
                    },
                    "timestamp": datetime.now().isoformat()
                }
            )
            yield event.format()
        
        except Exception as e:
            logger.error(f"Agentic search error: {e}", exc_info=True)
            
            # Emit error event
            event = SSEEvent(
                event="error",
                data={
                    "error": str(e),
                    "timestamp": datetime.now().isoformat()
                }
            )
            yield event.format()

