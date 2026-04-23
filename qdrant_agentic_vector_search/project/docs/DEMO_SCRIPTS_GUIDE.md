# Demo Scripts Guide - Three Approaches

## 📚 Scripts Created

### 1. **Pure Qdrant Search** (No LLM, No Agents)
**File:** `demo_qdrant_hybrid_search.py`

**What it does:**
- Qdrant hybrid search only
- Shows dense + sparse + RRF
- Returns statute citations
- **No answer generation**

**Use when:**
- Demonstrating Qdrant capabilities
- Showing hybrid search speed
- Explaining RRF fusion

**Output:**
```
Query: "Can a landlord evict without notice?"
→ Retrieved 5 statutes
→ Citations with scores
→ No synthesis (just results)
```

**Run:**
```bash
python demo_qdrant_hybrid_search.py
```

---

### 2. **Vanilla RAG** (Qdrant + LLM, No Agents)
**File:** `demo_vanilla_rag.py`

**What it does:**
- Qdrant hybrid search
- Build context from results
- LLM generates answer
- Single-step pipeline

**Use when:**
- Showing basic RAG
- Comparing to agentic approach
- Fast, simple answers needed

**Output:**
```
Query: "Can a landlord evict without notice?"
→ Search Qdrant (5 statutes)
→ Build context
→ GPT-4o-mini answer:
   "No, California law requires written notice..."
   [cites § 1946.2, § 1161b]
```

**Run:**
```bash
python demo_vanilla_rag.py
```

---

### 3. **Agentic RAG** (Qdrant + CrewAI + Tools)
**File:** `demo_crewai_qdrant_agent.py`

**What it does:**
- CrewAI agent with custom tools
- Uses Qdrant as a tool
- Multi-step reasoning
- Can follow refs, compute dates, check local rules

**Use when:**
- Demonstrating full capabilities
- Showing agent reasoning
- Complex workflows needed

**Output:**
```
Query: "Can a landlord evict without notice?"
→ Agent thinks...
→ Calls search_california_statutes tool
→ Qdrant returns statutes
→ Agent analyzes
→ Agent formulates answer with citations
→ "No, based on § 1946.2..."
```

**Run:**
```bash
python demo_crewai_qdrant_agent.py
```

---

## 🎯 Comparison Matrix

| Feature | Pure Search | Vanilla RAG | Agentic RAG |
|---------|-------------|-------------|-------------|
| **Qdrant Search** | ✅ Hybrid RRF | ✅ Hybrid RRF | ✅ Hybrid RRF |
| **Answer Generation** | ❌ | ✅ LLM | ✅ LLM |
| **Citations** | ✅ Raw | ✅ In answer | ✅ Verified |
| **Multi-step** | ❌ | ❌ | ✅ |
| **Custom Tools** | ❌ | ❌ | ✅ (5 tools) |
| **Follow Refs** | ❌ | ❌ | ✅ |
| **Compute Dates** | ❌ | ❌ | ✅ |
| **Local Rules** | ❌ | ❌ | ✅ |
| **Speed** | Fastest | Fast | Slower |
| **Complexity** | Simple | Medium | Complex |
| **Use Case** | Search demo | Quick answers | Workflows |

---

## 🚀 Demo Flow Recommendation

### For a Complete Demo:

**1. Start with Pure Search (2 min)**
```bash
python demo_qdrant_hybrid_search.py
```
- Show Qdrant's hybrid search speed
- Explain dense vs sparse vs RRF
- Display raw results

**2. Add Vanilla RAG (2 min)**
```bash
python demo_vanilla_rag.py
```
- Same search, but now with answer
- Show how LLM synthesizes results
- Compare to pure search

**3. Show Agentic RAG (5 min)**
```bash
python demo_crewai_qdrant_agent.py
```
- Agent uses Qdrant as a tool
- Can do multi-step workflows
- Has specialized legal tools
- Show the full capabilities

**Total: ~10 minute progression showing evolution**

---

## 💡 Key Messages

### Pure Search:
**"Qdrant hybrid search finds the right statutes in milliseconds"**
- 155k+ vectors
- Dense + sparse + RRF
- <300ms search time

### Vanilla RAG:
**"Add an LLM and you get synthesized answers with citations"**
- Search → Context → Generate
- Simple, fast, effective
- Single-step pipeline

### Agentic RAG:
**"Add agents and tools to operationalize the law into workflows"**
- CrewAI agent can reason
- Custom tools (FollowRef, DateMath, LocalRule)
- Multi-step procedures
- Defensible outputs

---

## 🎓 Technical Depth by Audience

### For Developers:
- Show all 3 scripts
- Explain progression
- Code walkthrough

### For Legal Professionals:
- Skip pure search
- Focus on vanilla → agentic
- Show practical workflows

### For Business/Execs:
- Just show agentic RAG
- Focus on outcomes
- Demo quiz mode for trust

---

## 📊 Qdrant as the Foundation

All three approaches use **Qdrant hybrid search**:

```python
# The core that powers everything:
results = client.query_points(
    collection_name="california_housing_statutes_full",
    prefetch=[
        Prefetch(query=dense_vector, using="dense", limit=20),
        Prefetch(query=sparse_vector, using="sparse", limit=20),
    ],
    query=FusionQuery(fusion=Fusion.RRF),
    limit=5
)
```

**What changes:**
- Pure search: Stop here
- Vanilla RAG: Add LLM layer
- Agentic RAG: Add CrewAI + custom tools

**What stays the same:**
- ✅ Qdrant hybrid search
- ✅ Dense + sparse vectors
- ✅ RRF fusion
- ✅ <300ms retrieval

This shows **Qdrant is the foundation** that enables everything else. 🎯

