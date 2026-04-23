# Repository Structure - Visual Guide

## 📁 Complete Directory Tree

```
qdrant_agentic_vector_search/
│
├── 🎥 dev_rel/                          # Everything for Demos/Videos!
│   ├── README.md                        # Demo package guide
│   ├── CHEATSHEET.md                    # Quick reference during demos
│   ├── scripts/
│   │   ├── compare_vanilla_vs_agentic.py # → Side-by-side comparison
│   │   └── run_demo.sh                  # → One-command demo!
│   └── guides/
│       ├── QUICK_START.md               # → 5-minute setup
│       └── PRESENTATION_STRATEGY.md     # → Presentation script
│
├── 📚 examples/                          # Educational Examples (Progressive Learning)
│   ├── __init__.py
│   │
│   ├── 1_data_exploration/              # Step 1: Understand Your Data
│   │   ├── inspect_collections.py       # → View Qdrant collections
│   │   └── explore_dataset.py           # → Browse HousingQA questions
│   │
│   ├── 2_vanilla_rag/                   # Step 2: Traditional Baseline
│   │   └── simple_rag.py                # → Single-shot RAG (70% accuracy)
│   │
│   └── 3_agentic_rag/                   # Step 3: Intelligent Approach
│       ├── agentic_rag.py               # → Multi-agent RAG (80-90% accuracy)
│       └── tools/
│           ├── __init__.py
│           └── qdrant_tool.py           # → Custom Qdrant search tool
│
├── 📖 docs/                             # Technical Documentation
│   ├── AGENTIC_RAG_VALUE.md             # → Technical deep dive
│   ├── REPOSITORY_GUIDE.md              # → Structure explanation
│   └── EVALUATION_STATUS.md             # → Benchmark results
│
├── 🔧 src/                              # Core Utilities
│   ├── __init__.py
│   ├── chunker.py                       # → Document chunking
│   ├── data_loader.py                   # → Dataset loading
│   ├── retriever.py                     # → Retrieval logic
│   ├── vector_store.py                  # → Qdrant wrapper
│   ├── qdrant_tool.py                   # → Search tool
│   ├── rag.py                           # → RAG components
│   └── logger.py                        # → Logging utilities
│
├── 🚀 setup/                            # Data Ingestion (One-time)
│   ├── README.md
│   ├── 01_ingest_data.py                # → Load data to Qdrant
│   └── 02_verify_collections.py         # → Verify setup
│
├── 💾 data/                             # Dataset Cache
│   ├── README.md
│   └── chunks_cache_512_50.json         # → Cached chunks
│
├── 📊 evaluation/                       # Evaluation Framework
│   └── README.md
│
├── 📦 evaluation_results/               # Test Results (Gitignored)
│   └── [Generated JSON/Parquet files]
│
├── 🗄️ archive/                          # Historical Files (Gitignored)
│   ├── README.md
│   ├── old_scripts/                     # → Deprecated code
│   ├── logs/                            # → Execution logs
│   └── test_scripts/                    # → One-off tests
│
├── 🌐 backend/                          # API Backend (Optional)
│   ├── main.py
│   ├── models.py
│   └── services/
│       ├── crew_service.py
│       ├── qdrant_service.py
│       └── search_service.py
│
├── 🧪 experiments/                      # Research Experiments (Gitignored)
│   └── [Various experiment scripts]
│
├── 📄 README.md                         # Main Documentation
├── 📄 REPO_TRANSFORMATION_SUMMARY.md    # What Changed
├── 📄 STRUCTURE.md                      # This File!
│
├── 📦 requirements.txt                  # Python Dependencies
├── 📦 pyproject.toml                    # Project Configuration
├── 🔒 uv.lock                           # UV Lock File
│
├── 🙈 .gitignore                        # Git Ignore Rules
├── 📝 .env.example                      # Environment Template
└── 🔑 .env                              # Your API Keys (Not in Git)
```

---

## 🎯 Files by Purpose

### Start Here (First Time)
1. `README.md` - Understand what this is
2. `dev_rel/guides/QUICK_START.md` - Get set up (5 minutes)
3. `cd dev_rel/scripts && ./run_demo.sh wyoming 5` - Run your first demo

### For Demos & Videos (👉 Everything in `dev_rel/`!)
1. `dev_rel/CHEATSHEET.md` - Keep open during presentation
2. `dev_rel/guides/PRESENTATION_STRATEGY.md` - Plan your presentation
3. `dev_rel/scripts/compare_vanilla_vs_agentic.py` - Main demo script
4. `dev_rel/scripts/run_demo.sh` - Quick runner

### For Learning
1. `examples/1_data_exploration/` - Start here
2. `examples/2_vanilla_rag/` - Then this
3. `examples/3_agentic_rag/` - Then this
4. `demos/compare_vanilla_vs_agentic.py` - Finally this

### For Understanding
1. `docs/AGENTIC_RAG_VALUE.md` - Why agents help
2. `docs/REPOSITORY_GUIDE.md` - How repo is organized
3. `REPO_TRANSFORMATION_SUMMARY.md` - What changed

### For Development
1. `src/` - Core utilities
2. `examples/3_agentic_rag/tools/` - Custom tools
3. `backend/` - API server (optional)

---

## 🔀 Typical User Flows

### 1. Video Demo Creator
```
README.md
  ↓
dev_rel/guides/QUICK_START.md (setup)
  ↓
dev_rel/guides/PRESENTATION_STRATEGY.md (plan)
  ↓
dev_rel/CHEATSHEET.md (during recording)
  ↓
cd dev_rel/scripts && ./run_demo.sh wyoming 5 (record this!)
```

### 2. Developer Learning
```
README.md
  ↓
examples/1_data_exploration/inspect_collections.py
  ↓
examples/1_data_exploration/explore_dataset.py
  ↓
examples/2_vanilla_rag/simple_rag.py
  ↓
examples/3_agentic_rag/agentic_rag.py
  ↓
demos/compare_vanilla_vs_agentic.py
  ↓
docs/AGENTIC_RAG_VALUE.md (deep understanding)
```

### 3. Workshop Instructor
```
docs/REPOSITORY_GUIDE.md (understand structure)
  ↓
docs/QUICK_START.md (prep student setup)
  ↓
Have students run examples/ in order
  ↓
Then demos/compare_vanilla_vs_agentic.py
  ↓
Then modify code for their use cases
```

---

## 📊 File Sizes Guide

### Small Files (<100 lines)
- `__init__.py` files
- `README.md` files in subdirectories
- Configuration files

### Medium Files (100-300 lines)
- Example scripts
- Demo scripts
- Documentation files
- Utility modules

### Large Files (300+ lines)
- `src/rag.py`
- `src/vector_store.py`
- `docs/REPOSITORY_GUIDE.md`

---

## 🎨 Color-Coded Purposes

| Icon | Purpose | Examples |
|------|---------|----------|
| 📚 | Learning | `examples/` |
| 🎬 | Presenting | `demos/` |
| 📖 | Reading | `docs/` |
| 🔧 | Utilities | `src/` |
| 🚀 | Running | Scripts |
| 💾 | Storage | `data/` |
| 🗄️ | Archive | `archive/` |

---

## 🚦 What To Show In Demos

### ✅ Always Show
- `dev_rel/scripts/compare_vanilla_vs_agentic.py`
- Results table
- Question-by-question comparison

### 🟡 Sometimes Show
- `examples/2_vanilla_rag/simple_rag.py` (if explaining baseline)
- `examples/3_agentic_rag/agentic_rag.py` (if deep dive)
- `examples/1_data_exploration/explore_dataset.py` (if showing data)

### ❌ Don't Show
- `src/` internals (too technical)
- `archive/` (old code)
- `experiments/` (research code)
- `backend/` (not relevant to core demo)

---

## 📍 Key Entry Points

### For Presenters
→ `dev_rel/` (everything you need in one folder!)

### For Quick Demo
→ `dev_rel/scripts/run_demo.sh`

### For Learners
→ `examples/1_data_exploration/inspect_collections.py`

### For Developers
→ `src/` and `examples/3_agentic_rag/tools/`

### For Researchers
→ `docs/AGENTIC_RAG_VALUE.md`

---

## 🎯 Dependencies Map

```
dev_rel/scripts/compare_vanilla_vs_agentic.py
  ↓ uses
examples/3_agentic_rag/tools/qdrant_tool.py
  ↓ uses
src/vector_store.py
  ↓ uses
Qdrant Cloud

examples/2_vanilla_rag/simple_rag.py
  ↓ uses
src/data_loader.py
  ↓ uses
HuggingFace datasets
```

---

## 🔍 Find Files By Need

**Need to understand the data?**
→ `examples/1_data_exploration/`

**Need a quick demo?**
→ `dev_rel/scripts/run_demo.sh` or `dev_rel/scripts/compare_vanilla_vs_agentic.py`

**Need to understand why agents help?**
→ `docs/AGENTIC_RAG_VALUE.md`

**Need setup instructions?**
→ `dev_rel/guides/QUICK_START.md`

**Need presentation talking points?**
→ `dev_rel/CHEATSHEET.md`

**Need to customize for your domain?**
→ `examples/3_agentic_rag/agentic_rag.py` (modify agent prompts)

**Need to see benchmarks?**
→ `docs/EVALUATION_STATUS.md`

**Need the full story?**
→ `README.md`

---

## 🎉 Summary

This repository is organized for **maximum clarity** and **demo-readiness**.

- **Examples** progress from simple to complex
- **Demos** are presentation-ready
- **Docs** are comprehensive
- **Scripts** are self-contained
- **Structure** is logical

Everything you need to showcase agentic vector search! 🚀

