"""
Demo: Vanilla RAG (Qdrant Search + LLM Answer)

Simple RAG pipeline:
1. Search Qdrant (hybrid search with RRF)
2. Build context from results
3. Generate answer with LLM

No agents, no tools - just retrieval + generation.

Prerequisites:
    1. Run data ingestion first: python demo_ingest_data.py
    2. Set up .env with QDRANT_CLOUD_URL, QDRANT_API_KEY, OPENAI_API_KEY

Usage:
    python demo_vanilla_rag.py
"""

import os
from dotenv import load_dotenv
from qdrant_client import QdrantClient, models
from fastembed import TextEmbedding, SparseTextEmbedding
from openai import OpenAI

load_dotenv()

# Configuration
QDRANT_URL = os.getenv('QDRANT_CLOUD_URL')
QDRANT_API_KEY = os.getenv('QDRANT_API_KEY')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
COLLECTION_NAME = "california_housing_statutes_full"

print("\n" + "="*80)
print("VANILLA RAG DEMO")
print("Qdrant Hybrid Search + LLM Generation")
print("="*80)

# STEP 1: Initialize Clients
print("\nInitializing clients...")
client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
dense_model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
sparse_model = SparseTextEmbedding(model_name="Qdrant/bm42-all-minilm-l6-v2-attentions")
openai_client = OpenAI(api_key=OPENAI_API_KEY)
print("✓ Qdrant, FastEmbed, OpenAI ready\n")

# STEP 2: Retrieval - Qdrant Hybrid Search
question = "Can a landlord evict a tenant without providing written notice?"
print(f"Question: {question}\n")

print("STEP 1: RETRIEVAL (Qdrant Hybrid Search)")
print("-" * 80)

# Generate embeddings
dense_query = list(dense_model.embed([question]))[0].tolist()
sparse_query_embedding = list(sparse_model.embed([question]))[0]
sparse_query = models.SparseVector(
    indices=sparse_query_embedding.indices.tolist(),
    values=sparse_query_embedding.values.tolist()
)

# Hybrid search with RRF
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

# Show retrieved statutes
print("Retrieved Statutes:\n")
for i, point in enumerate(results.points, 1):
    citation = point.payload.get('citation', 'Unknown')
    text = point.payload.get('text', '')
    score = point.score
    
    print(f"[{i}] {citation} (score: {score:.3f})")
    print(f"    {text[:150]}...")
    print()

# STEP 3: Generation - Build Context and Prompt LLM
print("\nSTEP 2: GENERATION (LLM Answer)")
print("-" * 80)

# Build context
context_parts = []
for i, point in enumerate(results.points, 1):
    citation = point.payload.get('citation', 'Unknown')
    text = point.payload.get('text', '')
    context_parts.append(f"[{i}] {citation}\n{text}")

context = "\n\n".join(context_parts)

# Simple prompt
prompt = f"""Based on these California housing law statutes, answer the question clearly.

Question: {question}

Statutes:
{context}

Instructions:
- Provide a clear, direct answer
- Cite specific statute sections
- Quote relevant language

Answer:"""

print("  → Building context from 5 statutes...")
print("  → Calling OpenAI GPT-4o-mini...")

# Generate answer
response = openai_client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": prompt}],
    temperature=0.3,
    max_tokens=300
)

answer = response.choices[0].message.content.strip()
print("✓ Answer generated\n")

# Display Answer``
print("="*80)
print("ANSWER")
print("="*80)
print(f"\n{answer}\n")

# Summary
print("="*80)
print("VANILLA RAG PIPELINE SUMMARY")
print("="*80)
print(f"""
Pipeline Steps:
  1. Retrieval: Qdrant hybrid search (dense + sparse + RRF)
  2. Context: Build from top 5 statutes
  3. Generation: LLM synthesizes answer with citations

Simple, Fast, Effective

This is "vanilla RAG":
  • No agents
  • No tools  
  • No multi-step reasoning
  • Just: Search → Context → Answer

Compare to:
  • Pure search: Faster but no synthesis
  • Agentic RAG: Slower but has tools, workflows, multi-step
""")

