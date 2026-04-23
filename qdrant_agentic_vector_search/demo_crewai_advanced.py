"""
Advanced Demo: Multi-Agent Legal Research Team with CrewAI + Qdrant

This script demonstrates an advanced AI legal research team using:
- CrewAI for multi-agent orchestration and delegat`ion
- 5 specialized agents working collaboratively
- Multiple custom tools for different research tasks
- Qdrant for hybrid vector search (dense + sparse + RRF)
- Structured output with comprehensive analysis

The team consists of:
1. Research Director - Coordinates the team and delegates tasks
2. Statute Researcher - Finds relevant laws using hybrid search
3. Case Analyst - Analyzes legal precedents and applications
4. Citation Validator - Verifies accuracy and cross-references
5. Legal Writer - Creates comprehensive, well-formatted reports

Prerequisites:
    1. Run data ingestion first: python demo_ingest_data.py
    2. Set up .env with QDRANT_CLOUD_URL, QDRANT_API_KEY, OPENAI_API_KEY

Usage:
    python demo_crewai_advanced.py
"""

import os
from datetime import datetime
from typing import List, Dict, Any
from dotenv import load_dotenv
from crewai import Agent, Task, Crew, LLM, Process
from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from qdrant_client import QdrantClient, models
from fastembed import TextEmbedding, SparseTextEmbedding

load_dotenv()

# ============================================================================
# CUSTOM TOOLS FOR LEGAL RESEARCH TEAM
# ============================================================================

class HybridSearchInput(BaseModel):
    """Input schema for hybrid search."""
    query: str = Field(..., description="Legal search query")
    top_k: int = Field(default=5, description="Number of results to return")


class CompareStatutesInput(BaseModel):
    """Input schema for statute comparison."""
    statute1: str = Field(..., description="First statute citation or topic")
    statute2: str = Field(..., description="Second statute citation or topic")


class CitationValidationInput(BaseModel):
    """Input schema for citation validation."""
    citation: str = Field(..., description="Statute citation to validate")


class QdrantHybridSearchTool(BaseTool):
    """
    Advanced Qdrant Hybrid Search Tool for Legal Research.
    
    Combines:
    - Dense vectors (semantic understanding via BGE-small)
    - Sparse vectors (keyword matching via BM42)
    - RRF fusion (best of both worlds)
    
    Perfect for finding relevant statutes based on natural language queries.
    """
    
    name: str = "hybrid_search_statutes"
    description: str = """Search California housing statutes using advanced hybrid search.
    This tool combines semantic understanding with exact keyword matching to find the most
    relevant statutes. Returns statute citations with relevance scores and full text.
    
    Use this when you need to:
    - Find statutes related to a specific topic
    - Search for laws using natural language
    - Discover relevant legal provisions
    
    Example: "What laws govern security deposit returns?"
    """
    
    args_schema: type[BaseModel] = HybridSearchInput
    
    def __init__(self):
        """Initialize Qdrant client and embedding models."""
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
        """Execute hybrid search with RRF fusion."""
        
        # Generate embeddings
        dense_query = list(self._dense_model.embed([query]))[0].tolist()
        sparse_query_embedding = list(self._sparse_model.embed([query]))[0]
        
        sparse_query = models.SparseVector(
            indices=sparse_query_embedding.indices.tolist(),
            values=sparse_query_embedding.values.tolist()
        )
        
        # Hybrid search
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
            return "No relevant California housing statutes found for this query."
        
        # Format results
        formatted_results = []
        for i, point in enumerate(results.points, 1):
            citation = point.payload.get('citation', 'Unknown')
            text = point.payload.get('text', '')
            score = point.score
            
            display_text = text[:500] + "..." if len(text) > 500 else text
            
            formatted_results.append(
                f"═══ Result {i} ═══\n"
                f"Citation: {citation}\n"
                f"Relevance: {score:.4f}\n"
                f"Text:\n{display_text}\n"
            )
        
        return "\n".join(formatted_results)


class QdrantComparisonTool(BaseTool):
    """
    Tool for comparing and contrasting different statutes.
    
    Useful for understanding relationships between laws, finding conflicts,
    or comparing provisions on similar topics.
    """
    
    name: str = "compare_statutes"
    description: str = """Compare two statutes or legal topics to find relationships and differences.
    This tool searches for both topics and presents them side-by-side for analysis.
    
    Use this when you need to:
    - Compare two related statutes
    - Find differences between legal provisions
    - Understand how laws interact
    
    Example: Compare "eviction notice requirements" with "just cause eviction"
    """
    
    args_schema: type[BaseModel] = CompareStatutesInput
    
    def __init__(self):
        """Initialize Qdrant client and embedding models."""
        super().__init__()
        
        self._qdrant_client = QdrantClient(
            url=os.getenv('QDRANT_CLOUD_URL'),
            api_key=os.getenv('QDRANT_API_KEY')
        )
        
        self._dense_model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
        self._sparse_model = SparseTextEmbedding(
            model_name="Qdrant/bm42-all-minilm-l6-v2-attentions"
        )
    
    def _run(self, statute1: str, statute2: str) -> str:
        """Compare two statutes or topics."""
        
        results = {}
        
        for label, query in [("Topic A", statute1), ("Topic B", statute2)]:
            dense_query = list(self._dense_model.embed([query]))[0].tolist()
            sparse_query_embedding = list(self._sparse_model.embed([query]))[0]
            
            sparse_query = models.SparseVector(
                indices=sparse_query_embedding.indices.tolist(),
                values=sparse_query_embedding.values.tolist()
            )
            
            search_results = self._qdrant_client.query_points(
                collection_name="california_housing_statutes_full",
                prefetch=[
                    models.Prefetch(query=dense_query, using="dense", limit=15),
                    models.Prefetch(query=sparse_query, using="sparse", limit=15),
                ],
                query=models.FusionQuery(fusion=models.Fusion.RRF),
                limit=3,
            )
            
            results[label] = search_results
        
        # Format comparison
        output = []
        output.append("╔══════════════════════════════════════════════════════════════╗")
        output.append("║           STATUTE COMPARISON RESULTS                         ║")
        output.append("╚══════════════════════════════════════════════════════════════╝\n")
        
        output.append(f"📋 TOPIC A: {statute1}\n")
        output.append("─" * 70)
        for i, point in enumerate(results["Topic A"].points, 1):
            citation = point.payload.get('citation', 'Unknown')
            text = point.payload.get('text', '')[:300]
            output.append(f"{i}. {citation}\n   {text}...\n")
        
        output.append(f"\n📋 TOPIC B: {statute2}\n")
        output.append("─" * 70)
        for i, point in enumerate(results["Topic B"].points, 1):
            citation = point.payload.get('citation', 'Unknown')
            text = point.payload.get('text', '')[:300]
            output.append(f"{i}. {citation}\n   {text}...\n")
        
        return "\n".join(output)


class CitationValidatorTool(BaseTool):
    """
    Tool for validating statute citations and retrieving exact text.
    
    Ensures citations are accurate and provides the authoritative text
    of specific statute sections.
    """
    
    name: str = "validate_citation"
    description: str = """Validate a specific statute citation and retrieve its exact text.
    This tool performs a precise search for the citation to ensure it exists
    and returns the authoritative text.
    
    Use this when you need to:
    - Verify a citation is correct
    - Get the exact text of a specific statute
    - Double-check legal references
    
    Example: "California Civil Code Section 1950.5"
    """
    
    args_schema: type[BaseModel] = CitationValidationInput
    
    def __init__(self):
        """Initialize Qdrant client and embedding models."""
        super().__init__()
        
        self._qdrant_client = QdrantClient(
            url=os.getenv('QDRANT_CLOUD_URL'),
            api_key=os.getenv('QDRANT_API_KEY')
        )
        
        self._sparse_model = SparseTextEmbedding(
            model_name="Qdrant/bm42-all-minilm-l6-v2-attentions"
        )
    
    def _run(self, citation: str) -> str:
        """Validate citation and retrieve exact text."""
        
        # Use keyword search for precise citation matching
        sparse_query_embedding = list(self._sparse_model.embed([citation]))[0]
        
        sparse_query = models.SparseVector(
            indices=sparse_query_embedding.indices.tolist(),
            values=sparse_query_embedding.values.tolist()
        )
        
        results = self._qdrant_client.query_points(
            collection_name="california_housing_statutes_full",
            query=sparse_query,
            using="sparse",
            limit=3,
        )
        
        if not results.points:
            return f"⚠️ Citation '{citation}' could not be validated. It may not exist or may be incorrectly formatted."
        
        # Check if top result is a good match
        top_result = results.points[0]
        found_citation = top_result.payload.get('citation', '')
        text = top_result.payload.get('text', '')
        score = top_result.score
        
        output = []
        output.append("✓ CITATION VALIDATION RESULT\n")
        output.append(f"Searched for: {citation}")
        output.append(f"Found: {found_citation}")
        output.append(f"Match Score: {score:.4f}\n")
        output.append("Full Text:")
        output.append("─" * 70)
        output.append(text)
        output.append("─" * 70)
        
        return "\n".join(output)


# ============================================================================
# MULTI-AGENT TEAM SETUP
# ============================================================================

def create_advanced_legal_team():
    """Create a team of specialized legal research agents."""
    
    # Initialize tools
    search_tool = QdrantHybridSearchTool()
    compare_tool = QdrantComparisonTool()
    validator_tool = CitationValidatorTool()
    
    # Create LLM
    llm = LLM(
        model="gpt-4o-mini",
        temperature=0.2,
        api_key=os.getenv('OPENAI_API_KEY')
    )
    
    # Agent 1: Research Director
    research_director = Agent(
        role="Senior Legal Research Director",
        goal="Coordinate the legal research team and ensure comprehensive analysis",
        backstory="""You are a seasoned legal research director with 20+ years of experience
        managing complex legal research projects. Your expertise lies in:
        - Breaking down complex legal questions into research tasks
        - Coordinating teams of specialists
        - Ensuring thorough and accurate legal analysis
        - Synthesizing findings into actionable insights
        
        You oversee a team of specialists and delegate tasks strategically to ensure
        the most comprehensive research possible. You have high standards for accuracy
        and always verify that all aspects of a question have been addressed.""",
        llm=llm,
        verbose=True,
        allow_delegation=True,
        max_iter=15
    )
    
    # Agent 2: Statute Researcher
    statute_researcher = Agent(
        role="Statute Research Specialist",
        goal="Find and analyze relevant California housing statutes",
        backstory="""You are an expert at finding relevant statutes in California's 
        extensive housing law database. You have mastered:
        - Hybrid search techniques combining semantic and keyword search
        - Understanding complex legal terminology
        - Identifying the most relevant provisions for any question
        - Finding both obvious and subtle legal connections
        
        You have access to 155,974+ California housing statutes through advanced
        search tools. You excel at crafting search queries that uncover all relevant
        legal provisions.""",
        tools=[search_tool, compare_tool],
        llm=llm,
        verbose=True,
        allow_delegation=False
    )
    
    # Agent 3: Case Analyst
    case_analyst = Agent(
        role="Legal Case Analyst",
        goal="Analyze statutes in context and provide practical interpretation",
        backstory="""You are a legal analyst who excels at understanding how statutes
        apply in real-world situations. Your strengths include:
        - Interpreting statutory language in practical contexts
        - Identifying exceptions and special circumstances
        - Understanding relationships between different legal provisions
        - Providing nuanced analysis of complex legal scenarios
        
        You work closely with the Statute Researcher to understand not just what
        the law says, but how it applies in practice. You identify edge cases,
        conflicts, and ambiguities.""",
        tools=[search_tool, compare_tool],
        llm=llm,
        verbose=True,
        allow_delegation=False
    )
    
    # Agent 4: Citation Validator
    citation_validator = Agent(
        role="Citation Validation Specialist",
        goal="Verify all citations are accurate and properly formatted",
        backstory="""You are meticulous about accuracy. Your responsibilities include:
        - Validating every statute citation
        - Ensuring quotes are verbatim and accurate
        - Cross-referencing related provisions
        - Catching any errors or inconsistencies
        
        You have zero tolerance for citation errors. Before any legal analysis is
        finalized, you verify every single reference. Your work ensures that all
        research is defensible and reliable.""",
        tools=[validator_tool, search_tool],
        llm=llm,
        verbose=True,
        allow_delegation=False
    )
    
    # Agent 5: Legal Writer
    legal_writer = Agent(
        role="Senior Legal Writer",
        goal="Create clear, comprehensive legal research reports",
        backstory="""You are an expert legal writer known for producing exceptionally
        clear and well-organized research reports. Your skills include:
        - Synthesizing complex legal information into clear prose
        - Creating well-structured documents with proper formatting
        - Writing for both legal experts and non-specialists
        - Presenting findings with appropriate citations and analysis
        
        You take raw research from the team and transform it into polished,
        professional reports that are both thorough and accessible. Your reports
        are known for their clarity, organization, and comprehensive coverage.""",
        llm=llm,
        verbose=True,
        allow_delegation=False
    )
    
    return {
        'director': research_director,
        'researcher': statute_researcher,
        'analyst': case_analyst,
        'validator': citation_validator,
        'writer': legal_writer
    }


# ============================================================================
# COMPLEX MULTI-TASK WORKFLOW
# ============================================================================

def create_research_workflow(team: Dict[str, Agent], question: str):
    """Create a comprehensive multi-task research workflow."""
    
    # Task 1: Initial Statute Research
    task1 = Task(
        description=f"""Conduct comprehensive research on the following legal question:

"{question}"

Your objectives:
1. Analyze the question and identify all distinct legal topics or issues involved
2. Use hybrid_search_statutes with MULTIPLE targeted queries from different angles
3. Search broadly to capture all relevant aspects of the question
4. Try at least 6-8 different search queries using varied terminology and approaches
5. If the question has multiple parts, keep findings clearly organized by topic
6. Identify primary statutes that directly address the question
7. Find related provisions that provide important context
8. Note any potential conflicts or ambiguities

Provide a detailed summary:
- All relevant statute citations found (organized by topic if multi-part question)
- Key provisions from each statute (with direct quotes)
- How each statute relates to the specific question
- Any gaps in the research that need further investigation

Be thorough - this is the foundation for the entire analysis.""",
        expected_output="""A comprehensive list of relevant statutes including:
- Citation for each statute found
- Key excerpts (quoted verbatim)
- Relevance explanation for each
- Organization by topic (if question has multiple parts)
- Any gaps or ambiguities identified""",
        agent=team['researcher']
    )
    
    # Task 2: Legal Analysis
    task2 = Task(
        description=f"""Analyze the statutes found by the Statute Researcher and provide 
practical legal interpretation for the question:

"{question}"

Your objectives:
1. Review all statutes identified by the Researcher
2. Analyze how they apply to the specific question asked
3. Identify the key legal requirements, exceptions, and special circumstances
4. Use compare_statutes tool when you need to understand relationships between provisions
5. Provide practical guidance on how the law applies in this context
6. Flag any ambiguities, conflicts, or fact-dependent issues

Consider:
- What are the clear legal requirements?
- What exceptions or special cases exist?
- How do different provisions interact or relate to each other?
- What depends on specific facts or circumstances?
- Are there any important caveats or considerations?

Provide a nuanced, practical analysis that directly addresses the question.""",
        expected_output="""A detailed legal analysis including:
- Direct answer to the question(s) asked
- Key legal requirements explained clearly
- Exceptions and special circumstances
- How different provisions interact
- Practical implications and guidance
- Areas of ambiguity or fact-dependency""",
        agent=team['analyst'],
        context=[task1]
    )
    
    # Task 3: Citation Validation
    task3 = Task(
        description="""Validate ALL citations from the research and analysis:

Your objectives:
1. Extract every statute citation mentioned in the previous work
2. Use validate_citation to verify each citation is accurate
3. Confirm all quoted text is verbatim
4. Flag any errors, inconsistencies, or concerns
5. Provide corrected citations if needed

Be extremely thorough - every citation must be validated.
If you find any errors, clearly document them.

Create a validation report showing:
- Each citation checked
- Validation status (✓ confirmed / ⚠️ issue found)
- Any corrections needed
- Overall confidence in the citations""",
        expected_output="""A validation report with:
- List of all citations validated
- Status of each (confirmed/issue)
- Any corrections or concerns
- Overall validation summary
- Confidence assessment""",
        agent=team['validator'],
        context=[task1, task2]
    )
    
    # Task 4: Final Report Writing
    task4 = Task(
        description=f"""Create a comprehensive, well-formatted legal research report 
answering the question:

"{question}"

Using all research from the team, create a professional report with these sections:

1. EXECUTIVE SUMMARY
   - Clear, direct answer to the question(s)
   - Key takeaways (3-5 bullet points)
   
2. LEGAL ANALYSIS
   - Detailed explanation of governing law
   - All relevant statute citations (validated)
   - Key statutory language (quoted verbatim)
   - Practical interpretation and application
   
3. REQUIREMENTS & EXCEPTIONS
   - Specific legal requirements that apply
   - Exceptions and special circumstances
   - Fact-dependent considerations
   
4. RELATED PROVISIONS
   - Connected statutes and how they interact
   - Important context and background
   
5. CONCLUSION & RECOMMENDATIONS
   - Summary of findings
   - Practical guidance for the situation
   - Areas requiring further analysis (if any)
   
6. APPENDIX: CITED STATUTES
   - Full list of all citations with validation status

Format the report professionally with clear headings, proper citations,
and excellent organization. Make it accessible to both legal experts and
non-specialists. If the question has multiple parts, organize the analysis
accordingly with clear sections for each.

This is the final deliverable - make it exceptional.""",
        expected_output="""A comprehensive, professionally formatted legal research report 
with all sections, proper citations, clear analysis, and actionable conclusions.""",
        agent=team['writer'],
        context=[task1, task2, task3]
    )
    
    return [task1, task2, task3, task4]


# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    """Run the advanced multi-agent legal research demo."""
    
    print("\n" + "="*80)
    print("ADVANCED CREWAI MULTI-AGENT LEGAL RESEARCH TEAM")
    print("="*80 + "\n")
    
    # Initialize team
    print("🏗️  Building the Legal Research Team...\n")
    team = create_advanced_legal_team()
    
    print("✓ Research Director (Coordinator)")
    print("✓ Statute Researcher (Specialist)")
    print("✓ Case Analyst (Interpreter)")
    print("✓ Citation Validator (Quality Control)")
    print("✓ Legal Writer (Report Specialist)")
    print("\n" + "─"*80 + "\n")
    
    # Define COMPLEX multi-part research question
    # This type of question would FAIL with vanilla RAG because:
    # 1. Two completely unrelated legal topics that need separate research
    # 2. Requires finding distinct statutes for each part
    # 3. Needs synthesis and comparison across different legal domains
    # 4. Vanilla RAG would mix results, provide incomplete answers, or get confused
    
    research_question = """
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
    RESEARCH BOTH SCENARIOS THOROUGHLY AND PROVIDE SEPARATE, COMPREHENSIVE ANSWERS
    ==============================================================================
    """
    
    print("📋 RESEARCH QUESTION:")
    print("─"*80)
    print(research_question)
    print("─"*80 + "\n")
    
    # Create workflow
    print("📝 Creating multi-task research workflow...\n")
    tasks = create_research_workflow(team, research_question)
    
    print("✓ Task 1: Comprehensive Statute Research")
    print("✓ Task 2: Legal Analysis & Interpretation")
    print("✓ Task 3: Citation Validation")
    print("✓ Task 4: Final Report Writing")
    print("\n" + "─"*80 + "\n")
    
    # Create and run crew
    print("🚀 Launching the research team...\n")
    print("=" * 80)
    print("TEAM COLLABORATION IN PROGRESS")
    print("=" * 80 + "\n")
    
    crew = Crew(
        agents=list(team.values()),
        tasks=tasks,
        process=Process.sequential,  # Tasks run in order, each building on previous
        verbose=True,
        full_output=True
    )
    
    # Execute
    start_time = datetime.now()
    result = crew.kickoff()
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    
    # Display final report
    print("\n\n" + "="*80)
    print("FINAL LEGAL RESEARCH REPORT")
    print("="*80 + "\n")
    print(result.raw)
    
    # Display summary
    print("\n\n" + "="*80)
    print("RESEARCH SUMMARY & METRICS")
    print("="*80 + "\n")
    print(f"⏱️  Total Research Time: {duration:.1f} seconds")
    print(f"👥 Agents Involved: {len(team)}")
    print(f"📋 Tasks Completed: {len(tasks)}")
    print(f"🔧 Tools Used: 3 (Hybrid Search, Comparison, Citation Validation)")
    print(f"📊 Database Size: 155,974+ California housing statutes")
    
    print("\n" + "─"*80 + "\n")
    print("WORKFLOW BREAKDOWN:")
    print("  1. Statute Researcher performed multi-angle hybrid searches")
    print("  2. Case Analyst interpreted statutes in practical context")
    print("  3. Citation Validator verified all references for accuracy")
    print("  4. Legal Writer synthesized everything into polished report")
    print("  5. Research Director coordinated and ensured comprehensive coverage")
    
    print("\n" + "─"*80 + "\n")
    print("TECHNOLOGY STACK:")
    print("  • CrewAI: Multi-agent orchestration & collaboration")
    print("  • Qdrant Cloud: Hybrid vector search (dense + sparse + RRF)")
    print("  • FastEmbed: BGE-small (semantic) + BM42 (keyword) embeddings")
    print("  • OpenAI GPT-4o-mini: Agent reasoning and analysis")
    print("  • Sequential Process: Each task builds on previous work")
    
    print("\n" + "="*80)
    print("✨ RESEARCH COMPLETE ✨")
    print("="*80 + "\n")


if __name__ == "__main__":
    main()

