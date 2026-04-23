# Quick Start Guide

Get up and running with the Agentic Vector Search demo in 5 minutes.

## 1. Prerequisites

Make sure you have:

- ✅ Python 3.12 or higher
- ✅ OpenAI API key ([get one here](https://platform.openai.com/api-keys))
- ✅ Qdrant Cloud instance ([sign up free](https://cloud.qdrant.io))

## 2. Installation

```bash
# Clone the repository
git clone <your-repo-url>
cd qdrant_agentic_vector_search

# Install dependencies (using pip)
pip install -r requirements.txt

# OR using uv (faster)
uv pip install -e .
```

## 3. Configuration

Create a `.env` file in the root directory:

```bash
OPENAI_API_KEY=sk-your-key-here
QDRANT_CLOUD_URL=https://your-instance.qdrant.io
QDRANT_API_KEY=your-key-here
```

## 4. Verify Setup

Check that your Qdrant collections are accessible:

```bash
python examples/1_data_exploration/inspect_collections.py
```

You should see three collections:
- ✅ Iowa Housing Statutes
- ✅ Idaho Housing Statutes
- ✅ Wyoming Housing Statutes

## 5. Run Your First Demo

**Try the side-by-side comparison:**

```bash
python demos/compare_vanilla_vs_agentic.py --state wyoming --limit 3
```

This will:
1. Load 3 Wyoming housing law questions
2. Run vanilla RAG on them
3. Run agentic RAG on them
4. Show you the accuracy difference

Expected output:
```
═══════════════════════════════════════════════
                COMPARISON RESULTS              
═══════════════════════════════════════════════

Approach          Correct    Accuracy    Strategy
────────────────────────────────────────────────
Vanilla RAG         2/3       66.7%      Single search
Agentic RAG         3/3      100.0%      Multi-step reasoning

✓ Agentic RAG improvement: +33.3 percentage points
```

## 6. Explore More

### Browse the Dataset

```bash
# See sample questions for Wyoming
python examples/1_data_exploration/explore_dataset.py --state wyoming
```

### Try Vanilla RAG Only

```bash
python examples/2_vanilla_rag/simple_rag.py --state wyoming --limit 5
```

### Try Agentic RAG Only

```bash
python examples/3_agentic_rag/agentic_rag.py --state wyoming --limit 5
```

### Try Different States

All demos support `--state` flag:

```bash
python demos/compare_vanilla_vs_agentic.py --state idaho --limit 5
python demos/compare_vanilla_vs_agentic.py --state iowa --limit 5
```

## Troubleshooting

### "No such collection" error

Make sure your Qdrant instance has the required collections:
- `housing_statutes_wyoming`
- `housing_statutes_idaho`
- `iowa_statutes_baseline`

### "API key not found" error

Check your `.env` file is in the root directory and contains all required keys.

### Import errors

Make sure you installed all dependencies:
```bash
pip install -r requirements.txt
```

## Next Steps

- 📖 Read [DEMO_STRATEGY.md](DEMO_STRATEGY.md) for presentation tips
- 🎯 Read [AGENTIC_RAG_VALUE.md](AGENTIC_RAG_VALUE.md) to understand the architecture
- 🎥 Adapt the demos for your own use case

## Need Help?

Open an issue on GitHub or check the main [README.md](../README.md) for more details.

---

**Ready to demo agentic vector search?** 🚀

