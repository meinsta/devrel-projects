# Repository Guide for Dev Rel Demos

This guide explains the structure and purpose of each component in this demo repository.

## 📂 Repository Organization

### `/examples/` - Educational Examples

The examples directory contains progressive tutorials showing different approaches:

#### `1_data_exploration/`
**Purpose**: Help users understand what data they're working with

**Files**:
- `inspect_collections.py` - Check Qdrant collections (Iowa, Idaho, Wyoming)
- `explore_dataset.py` - Browse HousingQA questions by state

**When to use**: Start here to understand your data before running RAG systems.

**Demo usage**: Show this first in videos to establish context about the dataset.

---

#### `2_vanilla_rag/`
**Purpose**: Demonstrate the traditional/baseline RAG approach

**Files**:
- `simple_rag.py` - Single-shot retrieval + generation

**Key characteristics**:
- ❌ One search per question
- ❌ No iteration or refinement
- ⚡ Fast (~2 seconds)
- 📉 Lower accuracy (~70%)

**Demo usage**: Use this to show the baseline that most people start with, then contrast with agentic approach.

---

#### `3_agentic_rag/`
**Purpose**: Demonstrate intelligent multi-agent search

**Files**:
- `agentic_rag.py` - Multi-step search with reasoning
- `tools/qdrant_tool.py` - Custom Qdrant search tool for CrewAI
- `tools/__init__.py` - Tool exports

**Key characteristics**:
- ✅ Multiple searches per question
- ✅ Adaptive strategy
- ✅ Agents reason about gaps
- 🐢 Slower (~25 seconds)
- 📈 Higher accuracy (~80-90%)

**Demo usage**: Show this after vanilla to demonstrate the improvement. Highlight the multi-step reasoning.

---

### `/demos/` - Presentation-Ready Scripts

**Purpose**: Polished scripts for live demos and videos

**Files**:
- `compare_vanilla_vs_agentic.py` - Side-by-side comparison with metrics

**Demo usage**: Use this as your main demo script. It runs both approaches on the same questions and shows the accuracy improvement.

**Perfect for**:
- 🎥 Video presentations
- 🎤 Conference talks
- 📊 Benchmark comparisons

---

### `/src/` - Core Utilities

**Purpose**: Reusable modules for data processing and vector operations

**Files**:
- `chunker.py` - Document chunking strategies
- `data_loader.py` - HousingQA dataset loading
- `retriever.py` - Retrieval logic
- `vector_store.py` - Qdrant client wrapper
- `rag.py` - RAG pipeline components

**When to use**: Import these if you're building custom workflows or need fine-grained control.

**Demo usage**: Usually not shown in demos, but reference them when explaining the architecture.

---

### `/docs/` - Documentation

**Purpose**: Guides, strategies, and reference materials

**Files**:
- `QUICK_START.md` - 5-minute setup guide
- `DEMO_STRATEGY.md` - Presentation strategy and script
- `AGENTIC_RAG_VALUE.md` - Technical explanation of why agents help
- `REPOSITORY_GUIDE.md` - This file!
- `EVALUATION_STATUS.md` - Benchmark results

**When to use**:
- Before demos: Read DEMO_STRATEGY.md
- For technical audiences: Reference AGENTIC_RAG_VALUE.md
- For new users: Send them to QUICK_START.md

---

### `/archive/` - Historical Files

**Purpose**: Old experiments, logs, and deprecated code

**What's here**:
- Old comparison logs
- Experiment results
- Previous iterations
- Analysis documents

**Demo usage**: Ignore these during demos. Keep for historical reference.

---

## 🎬 Demo Workflows

### Quick Demo (3-5 minutes)

**For**: Quick presentations, social media videos

```bash
# Run side-by-side comparison
python demos/compare_vanilla_vs_agentic.py --state wyoming --limit 3

# Show results table
# Highlight accuracy improvement
```

**Script**:
1. "Here's a complex legal question about Wyoming housing law"
2. "Watch vanilla RAG search once and give wrong answer"
3. "Watch agentic RAG search multiple times intelligently"
4. "Compare results: vanilla 67%, agentic 100%"

---

### Deep Dive Demo (10-15 minutes)

**For**: Technical talks, workshops

```bash
# 1. Show the data
python examples/1_data_exploration/explore_dataset.py --state wyoming

# 2. Run vanilla RAG
python examples/2_vanilla_rag/simple_rag.py --state wyoming --limit 5

# 3. Run agentic RAG
python examples/3_agentic_rag/agentic_rag.py --state wyoming --limit 5

# 4. Compare results
python demos/compare_vanilla_vs_agentic.py --state wyoming --limit 5
```

**Script**:
1. "Let's explore the HousingQA dataset"
2. "First, traditional RAG: one search, simple prompt"
3. "Now, agentic RAG: multiple searches, intelligent reasoning"
4. "Let's compare them side-by-side on the same questions"
5. "Notice how agents find documents vanilla misses"

---

### Workshop Demo (30+ minutes)

**For**: Hands-on training, hackathons

```bash
# Let participants run everything themselves

# Step 1: Setup
cat docs/QUICK_START.md

# Step 2: Explore data
python examples/1_data_exploration/inspect_collections.py
python examples/1_data_exploration/explore_dataset.py --state wyoming

# Step 3: Try vanilla
python examples/2_vanilla_rag/simple_rag.py --state wyoming --limit 10

# Step 4: Try agentic
python examples/3_agentic_rag/agentic_rag.py --state wyoming --limit 10

# Step 5: Compare
python demos/compare_vanilla_vs_agentic.py --state wyoming --limit 10

# Step 6: Customize
# Have them modify agent prompts, try different states, etc.
```

---

## 🎯 Key Messages for Each Audience

### For Developers
> "Agentic RAG uses multiple specialized agents that can perform follow-up searches based on what they learn. It's slower but finds documents that single-shot search misses."

**Show them**: `examples/3_agentic_rag/agentic_rag.py` code

### For Business/Product
> "Traditional search gets it right 70% of the time. Our agentic approach gets it right 80-90% of the time. For critical applications like legal research, that 10-20 point improvement matters."

**Show them**: `demos/compare_vanilla_vs_agentic.py` results table

### For Researchers/Scientists
> "We implement a multi-agent retrieval system using CrewAI where specialized agents perform iterative refinement. Initial results show 10-20 percentage point improvement in retrieval accuracy on the HousingQA benchmark."

**Show them**: `docs/AGENTIC_RAG_VALUE.md` technical details

---

## 🔧 Customization Guide

Want to adapt this for your domain?

### 1. Change the Dataset
Replace HousingQA with your documents:
- Update `src/data_loader.py`
- Create new Qdrant collections
- Update `COLLECTION_MAP` in demo scripts

### 2. Modify Agent Prompts
Edit the agent backstories in `examples/3_agentic_rag/agentic_rag.py`:
- Research agent strategy
- Analysis agent decision rules
- Task descriptions

### 3. Adjust Evaluation Metrics
Modify how you measure success:
- Change from Yes/No to other answer types
- Add custom metrics
- Update comparison logic

### 4. Create New Demos
Follow the pattern in `demos/`:
- Clear output formatting
- Side-by-side comparisons
- Visual metrics

---

## 📊 Performance Expectations

Based on Wyoming housing law questions (n=99):

| Metric | Vanilla RAG | Agentic RAG |
|--------|-------------|-------------|
| Accuracy | ~70% | ~80-90% |
| Time/Question | ~2 sec | ~25 sec |
| Searches/Question | 1 | 2-4 |
| API Cost/Question | ~$0.001 | ~$0.005 |

**Key Insight**: Agentic is ~10x slower and ~5x more expensive, but **10-20 points more accurate**.

---

## 🚀 Quick Commands Reference

```bash
# Setup
pip install -r requirements.txt

# Explore data
python examples/1_data_exploration/inspect_collections.py
python examples/1_data_exploration/explore_dataset.py --state wyoming

# Run demos
python examples/2_vanilla_rag/simple_rag.py --state wyoming --limit 10
python examples/3_agentic_rag/agentic_rag.py --state wyoming --limit 10
python demos/compare_vanilla_vs_agentic.py --state wyoming --limit 5

# Quick demo script
./run_demo.sh wyoming 5
./run_demo.sh idaho 10
./run_demo.sh iowa 5
```

---

## 📝 Tips for Great Demos

1. **Start with the problem**: "Legal research is hard. Traditional search misses things."

2. **Show, don't tell**: Run live code, don't just show slides.

3. **Use small numbers**: 3-5 questions is enough to see the difference.

4. **Highlight the wins**: Point out when agentic gets it right and vanilla doesn't.

5. **Address the cost**: "Yes, it's slower and more expensive, but accuracy matters for legal work."

6. **Make it interactive**: Let the audience suggest questions to test.

---

**Ready to demo?**

```bash
./run_demo.sh wyoming 5
```

🎥 Good luck with your presentation!

