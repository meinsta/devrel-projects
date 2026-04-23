# Agentic Vector Search Demo with Qdrant

A developer relations demo showcasing **agentic RAG** (Retrieval-Augmented Generation) using Qdrant vector search for legal document retrieval.

> **Perfect for videos and presentations**: This repo demonstrates why multi-agent search systems outperform traditional RAG approaches.

## 🎯 What This Demo Shows

This repository demonstrates the difference between:

1. **Vanilla RAG** (Traditional approach)
   - Single vector search
   - Simple prompt to LLM
   - Fast but limited

2. **Agentic RAG** (Intelligent approach)
   - Multiple strategic searches
   - Agents that reason about what to search next
   - Slower but more accurate

**Real-world use case**: Answering complex legal questions about housing law across three states (Wyoming, Idaho, Iowa).

## 🚀 Quick Start

> **📖 For a detailed step-by-step guide, see [DEMO_QUICKSTART.md](DEMO_QUICKSTART.md)**

### 1. Prerequisites

- Python 3.12+
- OpenAI API key (for LLM)
- Qdrant Cloud instance (for vector search)

### 2. Installation

```bash
# Clone the repo
git clone <your-repo-url>
cd qdrant_agentic_vector_search

# Install dependencies
pip install -r requirements.txt
# OR use uv (faster)
uv pip install -e .
```

### 3. Configuration

Create a `.env` file:

```bash
cp .env.example .env
```

Edit `.env` with your credentials:

```
OPENAI_API_KEY=sk-...
QDRANT_CLOUD_URL=https://your-instance.qdrant.io
QDRANT_API_KEY=your-qdrant-key
```

### 4. Ingest Demo Data

First, load California housing statutes into Qdrant:

```bash
python demo_ingest_data.py
```

This will:
- Download California housing statutes from HuggingFace
- Create embeddings (dense + sparse vectors)
- Upload to Qdrant collection: `california_housing_statutes_full`
- Takes ~10-15 minutes for full dataset (~156k statutes)

**Quick test** (only 100 statutes, ~30 seconds):
```bash
python demo_ingest_data.py --limit 100
```

### 5. Run the Demos!

**Option A: Quick Demos** (Single-file demos at root level)

```bash
# Pure Qdrant hybrid search (no LLM)
python demo_qdrant_hybrid_search.py

# Vanilla RAG (search + LLM answer)
python demo_vanilla_rag.py

# Agentic RAG (multi-agent with tools)
python demo_crewai_qdrant_agent.py
```

**Option B: Full Comparison Demo** (Recommended for presentations!)

```bash
cd dev_rel/scripts
./run_demo.sh wyoming 5
```

This runs BOTH approaches on the same questions and shows you:
- Accuracy comparison
- Question-by-question results
- When agentic search wins

**Option C: Individual Examples**

```bash
# Vanilla RAG only
python examples/2_vanilla_rag/simple_rag.py --state wyoming --limit 10

# Agentic RAG only
python examples/3_agentic_rag/agentic_rag.py --state wyoming --limit 10

# Manual comparison
python dev_rel/scripts/compare_vanilla_vs_agentic.py --state wyoming --limit 5
```

## 📁 Repository Structure

```
qdrant_agentic_vector_search/
│
├── dev_rel/                         # 🎥 Everything for demos/videos!
│   ├── README.md                    # Demo package guide
│   ├── CHEATSHEET.md                # Quick reference during demos
│   ├── scripts/
│   │   ├── compare_vanilla_vs_agentic.py
│   │   └── run_demo.sh              # One-command demo!
│   └── guides/
│       ├── QUICK_START.md
│       └── PRESENTATION_STRATEGY.md
│
├── examples/
│   ├── 1_data_exploration/          # Explore datasets and collections
│   │   ├── inspect_collections.py   # See what's in Qdrant
│   │   └── explore_dataset.py       # Browse HousingQA questions
│   │
│   ├── 2_vanilla_rag/               # Traditional RAG approach
│   │   └── simple_rag.py            # Single-shot retrieval + generation
│   │
│   └── 3_agentic_rag/               # Intelligent multi-agent approach
│       ├── agentic_rag.py           # Multi-step reasoning system
│       └── tools/
│           └── qdrant_tool.py       # Custom Qdrant tool for CrewAI
│
├── src/                             # Core utilities
│   ├── chunker.py
│   ├── data_loader.py
│   └── vector_store.py
│
├── docs/                            # Technical documentation
│   ├── AGENTIC_RAG_VALUE.md         # Why agentic RAG matters
│   └── REPOSITORY_GUIDE.md          # Structure explanation
│
└── README.md                        # You are here!
```

## 🎓 Learn by Example

### Step 1: Explore the Data

```bash
# See what collections are available in Qdrant
python examples/1_data_exploration/inspect_collections.py

# Browse sample questions for each state
python examples/1_data_exploration/explore_dataset.py --state wyoming
```

### Step 2: Try Vanilla RAG

```bash
# Run traditional RAG on Wyoming housing questions
python examples/2_vanilla_rag/simple_rag.py --state wyoming --limit 5
```

**What you'll see:**
- ❌ Limited by single search
- ❌ Misses relevant documents when initial query doesn't match perfectly
- ⚡ Fast (~1-2 seconds per question)

### Step 3: Try Agentic RAG

```bash
# Run agentic RAG on the same questions
python examples/3_agentic_rag/agentic_rag.py --state wyoming --limit 5
```

**What you'll see:**
- ✅ Multiple searches from different angles
- ✅ Agents reason about gaps and perform follow-ups
- 🐢 Slower (~20-30 seconds per question)
- ✅ Better accuracy

### Step 4: Compare Side-by-Side

```bash
# Run both approaches on the same questions
cd dev_rel/scripts
./run_demo.sh wyoming 5
```

**What you'll see:**
- 📊 Direct accuracy comparison
- 📋 Question-by-question breakdown
- 💡 When agentic search adds value

## 🎬 Perfect for Video Demos

This repository is designed for developer relations and video content:

### Demo Script (3-5 minutes)

1. **Show the question** (30 seconds)
   - "Let's answer a complex legal question about Wyoming housing law"

2. **Run vanilla RAG** (60 seconds)
   - Show the single search
   - Show the wrong/incomplete answer
   - Explain the limitation

3. **Run agentic RAG** (90 seconds)
   - Show multiple searches
   - Show agent reasoning
   - Show correct answer

4. **Show comparison** (60 seconds)
   - Display accuracy metrics
   - Highlight improvement
   - Explain when to use each approach

**📦 Everything for demos is in the `dev_rel/` folder!** See [`dev_rel/README.md`](dev_rel/README.md) for detailed presentation guidance.

## 📊 Dataset Information

This demo uses the **HousingQA dataset** from HuggingFace:
- 108 housing law questions across multiple states
- Ground truth answers (Yes/No)
- Referenced statute citations for evaluation

**Available states in this demo:**
- 🏔️ Wyoming (99 questions)
- 🌲 Idaho (available)
- 🌽 Iowa (108 questions)

## 🛠️ Technical Stack

- **Vector Database**: Qdrant Cloud
- **Embeddings**: BGE-small-en-v1.5 (via FastEmbed)
- **LLM**: GPT-4o-mini (via OpenAI)
- **Agent Framework**: CrewAI
- **Dataset**: HousingQA (HuggingFace)

## 🔑 Key Concepts Demonstrated

### 1. Vanilla RAG Limitations

```
Question → [Single Search] → [Simple Prompt] → Answer
```

**Problems:**
- ❌ One shot at retrieval
- ❌ If initial search misses key docs, answer is wrong
- ❌ No way to refine or follow up

### 2. Agentic RAG Advantages

```
Question → [Research Agent: Multi-angle search]
        → [Analysis Agent: Identify gaps → Follow-up search]
        → [Reasoning] → Answer
```

**Benefits:**
- ✅ Multiple search perspectives
- ✅ Intelligent query reformulation
- ✅ Finds documents vanilla RAG misses
- ✅ Better accuracy on complex questions

## 📈 Performance Comparison

Typical results on Wyoming housing law (10 questions):

| Approach | Accuracy | Avg. Time/Question |
|----------|----------|-------------------|
| Vanilla RAG | ~70% | ~2 seconds |
| Agentic RAG | ~80-90% | ~25 seconds |

**Key insight**: Agentic search is **10x slower** but **10+ points more accurate** on complex legal questions.

## 🎯 Use Cases

This pattern works well for:

- ✅ **Legal research** (as shown)
- ✅ **Medical literature review**
- ✅ **Technical documentation search**
- ✅ **Policy and compliance questions**
- ✅ **Research paper analysis**

**When accuracy > speed**, agentic search wins.

## 🤝 Contributing

This is a demo repository for developer relations. If you find issues or have suggestions:

1. Open an issue
2. Submit a PR
3. Share your experience!

## 📄 License

[Your license here]

## 🙏 Acknowledgments

- **HousingQA Dataset**: Stanford RegLab
- **Qdrant**: Vector search infrastructure
- **CrewAI**: Agent orchestration framework

---

## 💡 Tips for Your Own Demos

Want to adapt this for your own use case?

1. **Replace the dataset**: Use your domain-specific documents
2. **Adjust the collections**: Create collections for your document types
3. **Modify agent prompts**: Customize for your domain (legal → medical, etc.)
4. **Keep the structure**: The comparison demo format works great for videos!

---

**Ready to see agentic search in action?**

```bash
cd dev_rel/scripts
./run_demo.sh wyoming 5
```

**📦 For presentations and videos**: Everything you need is in `dev_rel/` folder!

🎥 Happy demoing!
