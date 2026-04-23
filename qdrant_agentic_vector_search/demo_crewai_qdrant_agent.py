"""
Demo: AI Agent with CrewAI + Qdrant Hybrid Search

This script demonstrates how` to build an AI legal research agent using:
- CrewAI for agentic workflows`
- Qdrant for hybrid vector search (dense + sparse + RRF)

The agent has access to California housing statutes and can answer legal questions
with verified citations.

Prerequisites:
    1. Run data ingestion first: python demo_ingest_data.py
    2. Set up .env with QDRANT_CLOUD_URL, QDRANT_API_KEY, OPENAI_API_KEY

Usage:
    python demo_crewai_qdrant_agent.py
"""

import os
from dotenv import load_dotenv
from crewai import Agent, Task, Crew, LLM
from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from qdrant_client import QdrantClient, models
from fastembed import TextEmbedding, SparseTextEmbedding

load_dotenv()

# ============================================================================
# STEP 1: Create Qdrant Hybrid Search Tool for CrewAI
# ============================================================================

class HybridSearchInput(BaseModel):
    """Input schema for hybrid search."""
    query: str = Field(..., description="Legal search query")
    top_k: int = Field(default=5, description="Number of results")


class QdrantHybridSearchTool(BaseTool):
    """
    Qdrant Hybrid Search Tool for CrewAI Agents.
    
    Combines:
    - Dense vectors (semantic understanding via BGE-small)
    - Sparse vectors (keyword matching via BM42)
    - RRF fusion (best of both worlds)
    """
    
    name: str = "search_california_statutes"
    description: str = """Search California housing statutes using advanced hybrid search.
    Combines semantic understanding with exact keyword matching.
    Returns statute citations with scores and full text.
    Use this to find re`levant California housing laws for any question."""
    
    args_schema: type[BaseModel] = HybridSearchInput
    
    def __init__(self):
        """Initialize Qdrant client and embedding models."""
        super().__init__()
        
        # Qdrant setup - use private attributes for Pydantic compatibility
        self._qdrant_client = QdrantClient(
            url=os.getenv('QDRANT_CLOUD_URL'),
            api_key=os.getenv('QDRANT_API_KEY')
        )
        
        # Embedding models
        self._dense_model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
        self._sparse_model = SparseTextEmbedding(
            model_name="Qdrant/bm42-all-minilm-l6-v2-attentions"
        )
        
        print("  ✓ Qdrant hybrid search tool initialized")
    
    def _run(self, query: str, top_k: int = 5) -> str:
        """Execute hybrid search with RRF fusion."""
        
        # Generate query embeddings
        dense_query = list(self._dense_model.embed([query]))[0].tolist()
        sparse_query_embedding = list(self._sparse_model.embed([query]))[0]
        
        sparse_query = models.SparseVector(
            indices=sparse_query_embedding.indices.tolist(),
            values=sparse_query_embedding.values.tolist()
        )
        
        # Hybrid search with RRF fusion
        results = self._qdrant_client.query_points(
            collection_name="california_housing_statutes_full",
            prefetch=[
                # Dense search (semantic)
                models.Prefetch(
                    query=dense_query,
                    using="dense",
                    limit=20
                ),
                # Sparse search (keywords)
                models.Prefetch(
                    query=sparse_query,
                    using="sparse",
                    limit=20
                ),
            ],
            # Fuse results with Reciprocal Rank Fusion
            query=models.FusionQuery(fusion=models.Fusion.RRF),
            limit=top_k,
        )
        
        if not results.points:
            return "No relevant California housing statutes found."
        
        # Format results for the agent
        formatted_results = []
        for i, point in enumerate(results.points, 1):
            citation = point.payload.get('citation', 'Unknown')
            text = point.payload.get('text', '')
            score = point.score
            
            # Truncate long text
            display_text = text[:400] + "..." if len(text) > 400 else text
            
            formatted_results.append(
                f"[{i}] {citation} (Relevance Score: {score:.3f})\n"
                f"{display_text}\n"
            )
        
        return "\n".join(formatted_results)


# ============================================================================
# STEP 2: Create CrewAI Agent with Qdrant Tool
# ============================================================================

def create_legal_agent():
    """Create a California housing law expert agent."""
    
    # Initialize the Qdrant tool
    qdrant_tool = QdrantHybridSearchTool()
    
    # Create LLM
    llm = LLM(
        model="gpt-4o-mini",
        temperature=0.1,
        api_key=os.getenv('OPENAI_API_KEY')
    )
    
    # Define the agent
    legal_agent = Agent(
        role="California Housing Law Expert",
        goal="Answer legal questions accurately using California housing statutes",
        backstory="""You are an expert legal researcher specializing in California housing law.
       
        You have access to a comprehensive database of 155,974+ California housing statutes
        through an advanced hybrid search tool that combines:
        - Semantic understanding (finds related concepts)
        - Keyword matching (finds exact terms)
        - Smart fusion (best of both approaches)`
        
        Your responsibilities:
        - Find the most relevant statutes for each question
        - Cite statutes accurately with section numbers
        - Quote key language verbatim
        - Answer based strictly on what the law says
        - Flag when the law is unclear or requires fact-specific analysis
        
        You are trusted to provide defensible legal research.""",
        tools=[qdrant_tool],
        llm=llm,
        verbose=False,  # Set to True to see agent thinking
        allow_delegation=False
    )
    
    return legal_agent


# STEP 3: Run the Agent
print("\n" + "="*80)
print("CREWAI AGENT + QDRANT DEMO")
print("="*80 + "\n")

print("Creating legal research agent...")
agent = create_legal_agent()
print("✓ Agent created with Qdrant hybrid search tool\n")

# Define the legal question
question = "Can a landlord evict a tenant without providing written notice in California?"
print(f"Question: {question}\n")

print("Creating research task...")

task = Task(
    description=f"""Research this California housing law question and provide a clear answer:

Question: {question}

Instructions:
1. Use the search_california_statutes tool to find relevant statutes
2. Analyze the statutes carefully
3. Provide a clear Yes or No answer
4. Cite specific statute sections
5. Quote key language verbatim

Format your answer as:
**Answer:** [Yes/No]

**Governing Statutes:**
- [Citation]: [Key quote]

**Reasoning:**
[Brief explanation based on the statutes]""",
    expected_output="Clear answer with statute citations and quotes",
    agent=agent
)

# Create crew
crew = Crew(
    agents=[agent],
    tasks=[task],
    verbose=False
)

print("✓ Task created\n")

# Run the agent
print("🤖 Agent researching...\n")
result = crew.kickoff()

# Display results
print("="*80)
print("AGENT'S ANSWER")
print("="*80)
print(f"\n{result}\n")

print("="*80)
print("WHAT JUST HAPPENED")
print("="*80)
print("""
1. Agent received the legal question
2. Agent decided to use search_california_statutes tool
3. Qdrant performed hybrid search:
   • Dense vector search (semantic similarity)
   • Sparse vector search (BM42 keywords)
   • RRF fusion of top 20 from each
4. Agent analyzed the retrieved statutes
5. Agent formulated answer with citations

Technology Stack:
  • CrewAI: Agentic reasoning & task execution
  • Qdrant: Hybrid search (155k+ vectors)
  • FastEmbed: Dense (BGE) + Sparse (BM42) embeddings
  • OpenAI: GPT-4o-mini for reasoning
""")

