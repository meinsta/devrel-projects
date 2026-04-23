"""
Demo: Pure Qdrant Hybrid Search (No Agents, No LLM)

This script demonstrates Qdrant's hybrid search capabilities:
- Dense vectors (semantic similarity via BGE-small)
- Sparse vectors (keyword matching via BM42)
- RRF fusion (Reciprocal Rank Fusion)
No CrewAI, no OpenAI - just pure vector search.
Prerequisites:
    1. Run data ingestion first: python demo_ingest_data.py
    2. Set up .env with QDRANT_CLOUD_URL, QDRANT_API_KEY

Usage:
    python demo_qdrant_hybrid_search.py
"""

import os
from dotenv import load_dotenv
from qdrant_client import QdrantClient, models
from fastembed import TextEmbedding, SparseTextEmbedding

load_dotenv()

# Configuration
QDRANT_URL = os.getenv('QDRANT_CLOUD_URL')
QDRANT_API_KEY = os.getenv('QDRANT_API_KEY')
COLLECTION_NAME = "california_housing_statutes_full"

print("\n" + "="*80)
print("QDRANT HYBRID SEARCH DEMO")
print("Dense + Sparse vectors with RRF fusion")
print("="*80)

# STEP 1: Initialize Qdrant Client
print("\nStep 1: Connecting to Qdrant...")
client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
print("✓ Connected to Qdrant Cloud\n")

# STEP 2: Load Embedding Models
print("Step 2: Loading embedding models...")
dense_model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
sparse_model = SparseTextEmbedding(model_name="Qdrant/bm42-all-minilm-l6-v2-attentions")
print("✓ Models loaded (Dense: BGE-small, Sparse: BM42)\n")

# STEP 3: Define Search Query
query = "Can a landlord evict a tenant without notice?"
print(f"Query: {query}\n")

# STEP 4: Generate Query Embeddings
print("Step 3: Generating query embeddings...")
dense_query = list(dense_model.embed([query]))[0].tolist()
sparse_query_embedding = list(sparse_model.embed([query]))[0]
sparse_query = models.SparseVector(
    indices=sparse_query_embedding.indices.tolist(),
    values=sparse_query_embedding.values.tolist()
)
print(f"  → Dense vector: {len(dense_query)} dimensions")
print(f"  → Sparse vector: {len(sparse_query.indices)} tokens")
print("✓ Query embeddings generated\n")

# STEP 5: Execute Hybrid Search with RRF
print("Step 4: Executing Qdrant hybrid search...")
print("  → Prefetch: Dense search (top 20)")
print("  → Prefetch: Sparse search (top 20)")
print("  → Fusion: RRF (Reciprocal Rank Fusion)\n")

results = client.query_points(
    collection_name=COLLECTION_NAME,
    prefetch=[
        models.Prefetch(query=dense_query, using="dense", limit=20),
        models.Prefetch(query=sparse_query, using="sparse", limit=20),
    ],
    query=models.FusionQuery(fusion=models.Fusion.RRF),
    limit=5,
)

print(f"✓ Retrieved {len(results.points)} statutes\n")

# STEP 6: Display Results
print("="*80)
print("SEARCH RESULTS")
print("="*80 + "\n")

for i, point in enumerate(results.points, 1):
    citation = point.payload.get('citation', 'Unknown')
    text = point.payload.get('text', '')
    score = point.score
    
    print(f"[{i}] {citation}")
    print(f"    RRF Score: {score:.3f}")
    print(f"    {text[:200]}...")
    print()

# Summary
print("="*80)
print("SUMMARY")
print("="*80)
print("""
✓ Qdrant Hybrid Search Complete!

What This Demonstrated:
  1. Dense Vector Search (semantic understanding)
  2. Sparse Vector Search (keyword matching)  
  3. RRF Fusion (best of both)

Technology:
  • Qdrant: Vector database
  • BGE-small-en-v1.5: Dense embeddings (384D)
  • BM42: Sparse embeddings (attention-based)
  • RRF: Reciprocal Rank Fusion

Performance:
  • Collection: 155,974+ California statutes
  • Search time: <300ms
  • Single API call (server-side fusion)

Next Steps:
  • Add LLM → Vanilla RAG (answers with citations)
  • Add Agents → Agentic RAG (workflows with tools)
""")