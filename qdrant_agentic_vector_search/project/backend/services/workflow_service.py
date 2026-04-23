"""
Workflow Service - Generate procedural workflows using CrewAI agents
"""

import os
import json
import asyncio
from typing import AsyncGenerator
from crewai import Agent, Task, Crew, LLM
import logging

from tools import (
    HybridSearchTool,
    FollowRefTool,
    DefinitionTool,
    DateMathTool,
    LocalRuleTool
)

logger = logging.getLogger(__name__)


class WorkflowService:
    """Service for generating legal procedural workflows."""
    
    def __init__(self):
        """Initialize workflow service."""
        self.openai_api_key = os.getenv('OPENAI_API_KEY')
        logger.info("Workflow service initialized")
    
    async def generate_workflow(
        self,
        query: str,
        city: str = None
    ) -> AsyncGenerator[str, None]:
        """
        Generate a step-by-step legal workflow for a housing law issue.
        
        Streams the agent's process in real-time.
        """
        
        # Yield initial step
        yield f"data: {json.dumps({'type': 'step', 'action': 'analyze', 'title': 'Analyzing Request', 'description': f'Understanding: {query[:60]}...'})}\n\n"
        await asyncio.sleep(0.3)
        
        # Initialize tools
        yield f"data: {json.dumps({'type': 'step', 'action': 'search', 'title': 'Loading Tools', 'description': 'Hybrid search, cross-refs, date math, local rules'})}\n\n"
        
        tools = [
            HybridSearchTool(),
            FollowRefTool(),
            DefinitionTool(),
            DateMathTool(),
        ]
        
        # Add local rule tool if city specified
        if city:
            tools.append(LocalRuleTool())
        
        await asyncio.sleep(0.3)
        
        # Create LLM
        llm = LLM(
            model="gpt-4o-mini",
            temperature=0.1,
            api_key=self.openai_api_key
        )
        
        # Create research agent
        yield f"data: {json.dumps({'type': 'step', 'action': 'retrieve', 'title': 'Creating Legal Research Agent', 'description': 'California Housing Law Expert with specialized tools'})}\n\n"
        
        research_agent = Agent(
            role="California Housing Law Expert",
            goal="Generate accurate, step-by-step legal workflows with verified citations",
            backstory="""You are an expert California housing law attorney with deep knowledge of:
            - California Civil Code (landlord-tenant law)
            - California Code of Civil Procedure (eviction procedures)
            - Local rent control ordinances (LA, SF, Oakland, etc.)
            
            You excel at:
            - Finding the controlling statute quickly
            - Following cross-references and exceptions
            - Computing exact deadlines
            - Flagging local rule variations
            - Creating actionable checklists with citations
            
            Your outputs are defensible in court.""",
            tools=tools,
            llm=llm,
            verbose=True,
            allow_delegation=False
        )
        
        # Create task
        city_context = f" The property is located in {city}." if city else ""
        
        task_description = f"""Generate a step-by-step procedural workflow for this California housing law issue:

{query}{city_context}

Requirements:
1. Use hybrid_search to find the controlling statutes
2. Use follow_ref if statutes reference other sections (e.g., "except as provided in §")
3. Use get_definition for any legal terms that need clarification
4. Use compute_deadline to calculate exact due dates (if timeline-based)
5. Use check_local_rules if a city is mentioned (check for stricter local ordinances)

Output format:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[ISSUE TYPE] Procedure

Step 1: [ACTION]
  Due: [DATE if applicable]
  Required: [What's needed]
  Cite: [Statute § with line-level quote]
  
Step 2: [ACTION]
  ...

⚠️ LOCAL ALERTS: [If applicable]

📎 Required Documents: [List]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Ensure every step has:
- Exact statute citation
- Verbatim quote (critical language)
- Deadline (if time-sensitive)
- Required documents/forms"""
        
        task = Task(
            description=task_description,
            agent=research_agent,
            expected_output="Step-by-step workflow with citations, deadlines, and local rule flags"
        )
        
        # Create crew
        crew = Crew(
            agents=[research_agent],
            tasks=[task],
            verbose=True
        )
        
        # Yield that agent is starting
        yield f"data: {json.dumps({'type': 'step', 'action': 'rank', 'title': 'Agent Researching', 'description': 'Running multi-step legal analysis...'})}\n\n"
        await asyncio.sleep(0.5)
        
        # Run crew WITHOUT streaming verbose output (much faster)
        try:
            # Set verbose to False for cleaner, faster execution
            crew.verbose = False
            legal_agent.verbose = False
            
            # Run the crew
            result = crew.kickoff()
            workflow = str(result)
            
            # Just send clean status updates
            yield f"data: {json.dumps({'type': 'step', 'action': 'analyze', 'title': 'Analysis Complete', 'description': 'Workflow generated with citations'})}\n\n"
            await asyncio.sleep(0.2)
            
        except Exception as e:
            logger.error(f"Workflow generation error: {e}")
            workflow = f"Error generating workflow: {str(e)}"
        
        # Send final result
        yield f"data: {json.dumps({'type': 'result', 'workflow': workflow})}\n\n"

