# Demo Quick Start Guide

This guide shows you how to quickly set up and run the Qdrant hybrid search demos.

## Prerequisites

1. **Python 3.12+** installed
2. **API Keys** ready:
   - OpenAI API key (for LLM)
   - Qdrant Cloud instance (for vector search)

## Step-by-Step Setup

### 1. Install Dependencies

```bash
# Install using pip
pip install -r requirements.txt

# OR use uv (faster)
uv pip install -e .
```

### 2. Configure Environment

Create a `.env` file in the project root:

```bash
OPENAI_API_KEY=sk-your-key-here
QDRANT_CLOUD_URL=https://your-instance.qdrant.io
QDRANT_API_KEY=your-qdrant-api-key
```

### 3. Ingest Demo Data

**Option A: Quick Test (100 statutes, ~30 seconds)**

Perfect for testing the setup:

```bash
python demo_ingest_data.py --limit 100
```

**Option B: Full Dataset (156k statutes, ~10-15 minutes)**

For production demos and accurate results:

```bash
python demo_ingest_data.py
```

This creates the `california_housing_statutes_full` collection with:
- Dense vectors (BGE-small-en-v1.5, 384D)
- Sparse vectors (BM42)
- Hybrid search ready with RRF fusion

### 4. Run Demos

#### Demo 1: Pure Qdrant Hybrid Search

No LLM, just vector search:

```bash
python demo_qdrant_hybrid_search.py
```

**Shows:**
- Dense vector search (semantic)
- Sparse vector search (keyword)
- RRF fusion combining both
- Retrieved statute chunks

**Duration:** ~2 seconds

---

#### Demo 2: Vanilla RAG

Traditional RAG: single search + LLM answer:

```bash
python demo_vanilla_rag.py
```

**Shows:**
- Hybrid search for context
- LLM generates answer with citations
- Simple, fast approach

**Duration:** ~3-5 seconds

---

#### Demo 3: Agentic RAG

Multi-agent system with intelligent search:

```bash
python demo_crewai_qdrant_agent.py
```

**Shows:**
- Multiple strategic searches
- Agent reasoning and planning
- Follow-up queries based on gaps
- More accurate answers

**Duration:** ~20-30 seconds

## Understanding the Progression

### Demo 1: Pure Search
```
Query → [Hybrid Search] → Results
```
- **Pros:** Blazing fast, simple
- **Cons:** No synthesis, raw results only

### Demo 2: Vanilla RAG
```
Query → [Single Search] → [LLM Synthesis] → Answer
```
- **Pros:** Fast, human-readable answers
- **Cons:** Limited by single search, may miss context

### Demo 3: Agentic RAG
```
Query → [Agent Plans] → [Multi-angle Search] 
      → [Identify Gaps] → [Follow-up Search] 
      → [Reasoning] → Answer
```
- **Pros:** Most accurate, finds hidden context
- **Cons:** Slower, more expensive

## Typical Results Comparison

| Approach | Speed | Accuracy | Use Case |
|----------|-------|----------|----------|
| Pure Search | 2s | N/A | Document retrieval |
| Vanilla RAG | 5s | 70-75% | Simple Q&A |
| Agentic RAG | 25s | 85-90% | Complex research |

## Demo Data

All demos use the **HousingQA dataset** from Stanford RegLab:
- 156,000+ California housing law statutes
- Real legal citations and text
- Perfect for demonstrating RAG capabilities

## Troubleshooting

### "Collection not found" error
**Solution:** Run `python demo_ingest_data.py` first

### "Rate limit exceeded"
**Solution:** Check your OpenAI API key has quota

### "Connection refused" to Qdrant
**Solution:** Verify `QDRANT_CLOUD_URL` and `QDRANT_API_KEY` in `.env`

### Slow ingestion
**Solution:** Use `--limit 100` for testing, or check your network connection

## Re-ingesting Data

### Append to existing collection:
```bash
python demo_ingest_data.py
# Will ask if you want to continue
```

### Delete and recreate:
```bash
python demo_ingest_data.py --recreate
```

## Next Steps

1. **Run all three demos** to see the progression
2. **Modify the questions** in each demo script to test your own queries
3. **Check the archive/** folder for more advanced examples
4. **Read the docs/** folder for detailed architecture information

## For Presentations

The best demo flow:
1. Show pure search results (fast but raw)
2. Show vanilla RAG (better, but misses context)
3. Show agentic RAG (slower but accurate)
4. Compare side-by-side to highlight the value

**Tip:** Use `--limit 100` for faster demos if you don't need perfect accuracy.

---

**Questions?** Check the main [README.md](README.md) or [TROUBLESHOOTING.md](project/dev_rel/TROUBLESHOOTING.md)


