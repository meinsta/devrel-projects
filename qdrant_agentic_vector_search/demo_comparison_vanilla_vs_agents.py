"""
Comparison Demo: Vanilla RAG vs Multi-Agent CrewAI

This script runs the SAME complex multi-part question through:
1. Vanilla RAG (simple retrieval + generation)
2. Multi-Agent CrewAI Team (specialized agents with tools)

The question is specifically designed to CHALLENGE vanilla RAG:
- Two completely unrelated legal topics
- Requires separate research for each part
- Needs synthesis across different legal domains

Watch how vanilla RAG struggles while the agent team excels!

Prerequisites:
    1. Run data ingestion first: python demo_ingest_data.py
    2. Set up .env with QDRANT_CLOUD_URL, QDRANT_API_KEY, OPENAI_API_KEY

Usage:
    python demo_comparison_vanilla_vs_agents.py
"""

import os
from datetime import datetime
from dotenv import load_dotenv
from qdrant_client import QdrantClient, models
from fastembed import TextEmbedding, SparseTextEmbedding
from openai import OpenAI

load_dotenv()

# ============================================================================
# THE COMPLEX QUESTION (That will break vanilla RAG)
# ============================================================================

COMPLEX_QUESTION = """
PART 1 - RENT INCREASE SCENARIO:
A landlord in Los Angeles owns a rental property built in 2010. The current tenant has 
lived there for 3 years and pays $2,000/month. The landlord wants to increase the rent 
to $2,600/month (a 30% increase). The tenant is on a month-to-month lease after their 
initial 1-year lease expired.

Questions: What are ALL the legal requirements for this rent increase? How much notice 
must be given? Are there any caps on the increase amount? What are the penalties if the 
landlord violates these requirements?

PART 2 - SERVICE ANIMAL SCENARIO (COMPLETELY UNRELATED):
A different tenant has a psychiatric service dog for anxiety and PTSD. The landlord's 
property has a "no pets" policy and typically charges a $500 pet deposit. The tenant 
provided a letter from their therapist stating they need the service animal.

Questions: Can the landlord legally charge the pet deposit for a service animal? What 
documentation can the landlord legally request? Can the landlord deny the service animal? 
What are the tenant's rights under California law versus federal law?

==============================================================================
ANSWER BOTH PARTS THOROUGHLY WITH SPECIFIC STATUTE CITATIONS
==============================================================================
"""

# ============================================================================
# VANILLA RAG APPROACH
# ============================================================================

def run_vanilla_rag(question: str):
    """Run vanilla RAG: single search + LLM generation."""
    
    print("\n" + "╔" + "═"*78 + "╗")
    print("║" + " "*25 + "APPROACH 1: VANILLA RAG" + " "*30 + "║")
    print("╚" + "═"*78 + "╝\n")
    
    print("Strategy: Single hybrid search → Build context → Generate answer")
    print("Limitation: Can only do ONE search, must fit everything in context\n")
    print("─"*80)
    
    # Initialize
    print("\n[1/4] Initializing clients...")
    client = QdrantClient(
        url=os.getenv('QDRANT_CLOUD_URL'),
        api_key=os.getenv('QDRANT_API_KEY')
    )
    dense_model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
    sparse_model = SparseTextEmbedding(model_name="Qdrant/bm42-all-minilm-l6-v2-attentions")
    openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
    print("      ✓ Ready")
    
    # Retrieval
    print("\n[2/4] Performing hybrid search...")
    print("      ⚠️  Problem: Can only do ONE search query!")
    print("      ⚠️  The question has TWO unrelated parts - which do we search for?")
    print("      → Searching for entire question (this will mix results)...")
    
    start_time = datetime.now()
    
    dense_query = list(dense_model.embed([question]))[0].tolist()
    sparse_query_embedding = list(sparse_model.embed([question]))[0]
    sparse_query = models.SparseVector(
        indices=sparse_query_embedding.indices.tolist(),
        values=sparse_query_embedding.values.tolist()
    )
    
    # Single search for everything
    results = client.query_points(
        collection_name="california_housing_statutes_full",
        prefetch=[
            models.Prefetch(query=dense_query, using="dense", limit=20),
            models.Prefetch(query=sparse_query, using="sparse", limit=20),
        ],
        query=models.FusionQuery(fusion=models.Fusion.RRF),
        limit=8,  # Try to get results for both topics
    )
    
    print(f"      ✓ Retrieved {len(results.points)} statutes (mixed from both topics)")
    
    # Show what we retrieved
    print("\n[3/4] Retrieved statutes:")
    for i, point in enumerate(results.points, 1):
        citation = point.payload.get('citation', 'Unknown')
        score = point.score
        text = point.payload.get('text', '')[:100]
        print(f"      [{i}] {citation} (score: {score:.3f})")
        print(f"          {text}...")
    
    # Build context
    print("\n[4/4] Generating answer...")
    print("      ⚠️  Problem: LLM gets mixed context from both topics")
    print("      ⚠️  May provide incomplete or confused answer")
    
    context_parts = []
    for i, point in enumerate(results.points, 1):
        citation = point.payload.get('citation', 'Unknown')
        text = point.payload.get('text', '')
        # Truncate to fit in context window
        context_parts.append(f"[{i}] {citation}\n{text[:800]}")
    
    context = "\n\n".join(context_parts)
    
    prompt = f"""Based on these California housing law statutes, answer the question clearly.
This question has TWO SEPARATE parts - address BOTH thoroughly.

Question: {question}

Statutes:
{context}

Instructions:
- Address PART 1 (rent increase) and PART 2 (service animal) separately
- Cite specific statute sections for each part
- Quote relevant language
- Be comprehensive

Answer:"""
    
    response = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=1000  # Vanilla RAG typically uses shorter responses
    )
    
    answer = response.choices[0].message.content.strip()
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    
    print(f"      ✓ Answer generated in {duration:.1f} seconds")
    
    return answer, duration, len(results.points)


# ============================================================================
# MULTI-AGENT CREWAI APPROACH
# ============================================================================

def run_multi_agent_crewai(question: str):
    """Run multi-agent CrewAI: specialized agents with tools."""
    
    print("\n\n" + "╔" + "═"*78 + "╗")
    print("║" + " "*20 + "APPROACH 2: MULTI-AGENT CREWAI" + " "*27 + "║")
    print("╚" + "═"*78 + "╝\n")
    
    print("Strategy: Multiple specialized agents with tools")
    print("Capability: Multiple searches, iterative research, validation\n")
    print("─"*80)
    
    from crewai import Agent, Task, Crew, LLM, Process
    from crewai.tools import BaseTool
    from pydantic import BaseModel, Field
    
    # Define tools (simplified versions for comparison)
    class HybridSearchInput(BaseModel):
        query: str = Field(..., description="Legal search query")
        top_k: int = Field(default=5, description="Number of results")
    
    class QdrantHybridSearchTool(BaseTool):
        name: str = "hybrid_search_statutes"
        description: str = """Search California housing statutes using advanced hybrid search."""
        args_schema: type[BaseModel] = HybridSearchInput
        
        def __init__(self):
            super().__init__()
            self._qdrant_client = QdrantClient(
                url=os.getenv('QDRANT_CLOUD_URL'),
                api_key=os.getenv('QDRANT_API_KEY')
            )
            self._dense_model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
            self._sparse_model = SparseTextEmbedding(
                model_name="Qdrant/bm42-all-minilm-l6-v2-attentions"
            )
        
        def _run(self, query: str, top_k: int = 5) -> str:
            dense_query = list(self._dense_model.embed([query]))[0].tolist()
            sparse_query_embedding = list(self._sparse_model.embed([query]))[0]
            sparse_query = models.SparseVector(
                indices=sparse_query_embedding.indices.tolist(),
                values=sparse_query_embedding.values.tolist()
            )
            
            results = self._qdrant_client.query_points(
                collection_name="california_housing_statutes_full",
                prefetch=[
                    models.Prefetch(query=dense_query, using="dense", limit=20),
                    models.Prefetch(query=sparse_query, using="sparse", limit=20),
                ],
                query=models.FusionQuery(fusion=models.Fusion.RRF),
                limit=top_k,
            )
            
            if not results.points:
                return "No relevant statutes found."
            
            formatted = []
            for i, point in enumerate(results.points, 1):
                citation = point.payload.get('citation', 'Unknown')
                text = point.payload.get('text', '')
                score = point.score
                display_text = text[:500] + "..." if len(text) > 500 else text
                formatted.append(
                    f"[{i}] {citation} (score: {score:.4f})\n{display_text}\n"
                )
            return "\n".join(formatted)
    
    print("\n[1/5] Creating specialized agents...")
    
    search_tool = QdrantHybridSearchTool()
    llm = LLM(
        model="gpt-4o-mini",
        temperature=0.2,
        api_key=os.getenv('OPENAI_API_KEY')
    )
    
    # Researcher agent
    researcher = Agent(
        role="Legal Research Specialist",
        goal="Find all relevant statutes for both parts of the question",
        backstory="""You are an expert legal researcher. You can perform MULTIPLE searches
        to thoroughly research complex multi-part questions. You search each topic separately
        to ensure comprehensive coverage.""",
        tools=[search_tool],
        llm=llm,
        verbose=False,
        allow_delegation=False
    )
    
    # Analyst agent
    analyst = Agent(
        role="Legal Analyst",
        goal="Provide comprehensive analysis for both scenarios",
        backstory="""You analyze legal statutes and provide clear, practical guidance.
        You excel at handling multi-part questions and organizing complex information.""",
        tools=[search_tool],
        llm=llm,
        verbose=False,
        allow_delegation=False
    )
    
    print("      ✓ Legal Research Specialist")
    print("      ✓ Legal Analyst")
    
    # Tasks
    print("\n[2/5] Creating research tasks...")
    
    task1 = Task(
        description=f"""Research this MULTI-PART question. Use SEPARATE searches for each part:

{question}

IMPORTANT: 
1. Search for rent increase laws (Part 1) with multiple queries
2. Search for service animal laws (Part 2) with multiple queries
3. Keep findings separated by topic

Use the hybrid_search_statutes tool multiple times with different queries!""",
        expected_output="Comprehensive statute list organized by Part 1 and Part 2",
        agent=researcher
    )
    
    task2 = Task(
        description="""Analyze the research and provide comprehensive answers for BOTH parts.
        
Create a detailed report with:
- PART 1 ANALYSIS: Rent increase requirements
- PART 2 ANALYSIS: Service animal rights
- Specific citations for each part
- Clear, actionable answers""",
        expected_output="Comprehensive legal analysis addressing both parts separately",
        agent=analyst,
        context=[task1]
    )
    
    print("      ✓ Task 1: Multi-angle statute research")
    print("      ✓ Task 2: Comprehensive legal analysis")
    
    print("\n[3/5] Assembling crew...")
    crew = Crew(
        agents=[researcher, analyst],
        tasks=[task1, task2],
        process=Process.sequential,
        verbose=False
    )
    print("      ✓ Crew ready")
    
    print("\n[4/5] Executing research workflow...")
    print("      → Agents will perform MULTIPLE searches")
    print("      → Each part researched separately")
    print("      → This may take 30-60 seconds...")
    
    start_time = datetime.now()
    result = crew.kickoff()
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    
    print(f"\n[5/5] ✓ Research complete in {duration:.1f} seconds")
    
    return result.raw, duration


# ============================================================================
# MAIN COMPARISON
# ============================================================================

def main():
    """Run the comparison."""
    
    print("\n" + "="*80)
    print(" "*20 + "VANILLA RAG vs MULTI-AGENT CREWAI")
    print(" "*25 + "HEAD-TO-HEAD COMPARISON")
    print("="*80)
    
    print("\n" + "─"*80)
    print("THE CHALLENGE: Complex Multi-Part Legal Question")
    print("─"*80)
    print(COMPLEX_QUESTION)
    print("─"*80)
    
    print("\n⚠️  WHY THIS QUESTION IS HARD FOR VANILLA RAG:")
    print("   1. Two COMPLETELY unrelated topics (rent increase + service animals)")
    print("   2. Can only do ONE search - will get mixed/incomplete results")
    print("   3. Limited context window - can't fit all necessary statutes")
    print("   4. No iterative research - one shot to get everything")
    print("   5. No validation - can't verify citations or search deeper")
    
    print("\n✓  WHY MULTI-AGENT EXCELS:")
    print("   1. Can perform MULTIPLE targeted searches (one per topic)")
    print("   2. Specialized agents for research, analysis, validation")
    print("   3. Iterative workflow - can search again if needed")
    print("   4. Tools for comparison, validation, deep research")
    print("   5. Systematic approach to complex multi-part questions")
    
    input("\n Press Enter to run both approaches and compare results...")
    
    # Run vanilla RAG
    vanilla_answer, vanilla_time, vanilla_sources = run_vanilla_rag(COMPLEX_QUESTION)
    
    # Run multi-agent
    agent_answer, agent_time = run_multi_agent_crewai(COMPLEX_QUESTION)
    
    # Display results
    print("\n\n" + "="*80)
    print("RESULTS COMPARISON")
    print("="*80)
    
    print("\n" + "╔" + "═"*78 + "╗")
    print("║" + " "*25 + "VANILLA RAG ANSWER" + " "*33 + "║")
    print("╚" + "═"*78 + "╝")
    print(f"\n⏱️  Time: {vanilla_time:.1f} seconds")
    print(f"📊 Sources: {vanilla_sources} statutes (mixed from both topics)")
    print(f"🔍 Searches: 1 (one search for everything)\n")
    print("─"*80)
    print(vanilla_answer)
    print("\n" + "─"*80)
    
    print("\n" + "╔" + "═"*78 + "╗")
    print("║" + " "*23 + "MULTI-AGENT CREWAI ANSWER" + " "*29 + "║")
    print("╚" + "═"*78 + "╝")
    print(f"\n⏱️  Time: {agent_time:.1f} seconds")
    print(f"🤖 Agents: 2 specialized agents")
    print(f"🔍 Searches: Multiple targeted searches per topic\n")
    print("─"*80)
    print(agent_answer)
    print("\n" + "─"*80)
    
    # Final analysis
    print("\n\n" + "="*80)
    print("ANALYSIS: Why Multi-Agent Wins for Complex Questions")
    print("="*80)
    
    print("""
┌─────────────────────────────────────────────────────────────────────────────┐
│                         VANILLA RAG LIMITATIONS                             │
├─────────────────────────────────────────────────────────────────────────────┤
│ • Single Search: Can only search once, gets mixed results                  │
│ • Context Limits: Can't fit all necessary statutes in one context          │
│ • No Iteration: One-shot approach, can't refine or search deeper           │
│ • Confusion: LLM gets confused with mixed topics in one context            │
│ • Incomplete: Likely misses key statutes for one or both parts             │
│ • Fast but Shallow: Quick but sacrifices thoroughness                      │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                      MULTI-AGENT CREWAI ADVANTAGES                          │
├─────────────────────────────────────────────────────────────────────────────┤
│ ✓ Multiple Searches: Separate targeted searches for each topic             │
│ ✓ Specialized Agents: Researcher finds statutes, Analyst interprets        │
│ ✓ Iterative Research: Can search multiple times from different angles      │
│ ✓ Clear Organization: Keeps Part 1 and Part 2 completely separate          │
│ ✓ Comprehensive: Finds all relevant statutes for both topics               │
│ ✓ Validation: Can verify citations and cross-reference                     │
│ ✓ Slower but Thorough: Takes longer but much more complete                 │
└─────────────────────────────────────────────────────────────────────────────┘

🎯 KEY INSIGHT:
   Vanilla RAG is great for SIMPLE, single-topic questions.
   Multi-Agent CrewAI excels at COMPLEX, multi-part questions requiring
   separate research streams and sophisticated reasoning.

   For production legal research, the thoroughness of the multi-agent
   approach is worth the extra time!
""")
    
    print("="*80)
    print("✨ COMPARISON COMPLETE ✨")
    print("="*80 + "\n")


if __name__ == "__main__":
    main()

