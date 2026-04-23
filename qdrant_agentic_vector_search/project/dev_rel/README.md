# 🎥 Dev Rel Demo Package

**Everything you need for presentations, videos, and demos - all in one place!**

This folder contains all the materials for showcasing agentic vector search with Qdrant.

---

## 📁 What's In This Folder

```
dev_rel/
├── README.md                          # This file - start here!
├── CHEATSHEET.md                      # Quick reference during demos
│
├── scripts/                           # Demo scripts
│   ├── compare_vanilla_vs_agentic.py  # Main comparison demo
│   └── run_demo.sh                    # One-command runner
│
└── guides/                            # Presentation guides
    ├── QUICK_START.md                 # 5-minute setup
    └── PRESENTATION_STRATEGY.md       # Presentation tips & script
```

---

## 🚀 Quick Start (30 seconds)

### Prerequisites
- Python 3.12+
- API keys in `.env` file (see `guides/QUICK_START.md`)

### Run Your First Demo
```bash
cd dev_rel/scripts
./run_demo.sh wyoming 5
```

That's it! You'll see a side-by-side comparison of vanilla vs agentic RAG.

---

## 🎬 Demo Scenarios

### 1. Quick Video (3-5 minutes)
**Perfect for**: Social media, quick presentations

```bash
cd dev_rel/scripts
./run_demo.sh wyoming 3
```

**What to show**:
- Run the comparison
- Show accuracy difference (vanilla ~70%, agentic ~80-90%)
- Explain: "Agents search multiple times, find docs vanilla misses"

---

### 2. Deep Dive (10-15 minutes)
**Perfect for**: Conference talks, technical demos

```bash
# Step 1: Show the data
python ../../examples/1_data_exploration/explore_dataset.py --state wyoming

# Step 2: Vanilla RAG baseline
python ../../examples/2_vanilla_rag/simple_rag.py --state wyoming --limit 5

# Step 3: Agentic RAG
python ../../examples/3_agentic_rag/agentic_rag.py --state wyoming --limit 5

# Step 4: Compare side-by-side
cd scripts && ./run_demo.sh wyoming 5
```

**What to show**:
- Dataset structure
- Vanilla's single search limitation
- Agentic's multi-step reasoning
- Accuracy comparison

---

### 3. Workshop (30+ minutes)
**Perfect for**: Hands-on training, hackathons

Let participants run everything themselves:
1. Setup (see `guides/QUICK_START.md`)
2. Explore examples (in `../../examples/`)
3. Run comparison (in `scripts/`)
4. Modify agent prompts for their use case

---

## 📋 Before Your Demo

### Checklist
- [ ] Read `CHEATSHEET.md` (quick reference)
- [ ] Read `guides/PRESENTATION_STRATEGY.md` (talking points)
- [ ] Test the demo: `cd scripts && ./run_demo.sh wyoming 3`
- [ ] Prepare for Q&A (see `CHEATSHEET.md`)
- [ ] Have backup screenshots ready (in case of technical issues)

### Setup Verification
```bash
# From dev_rel/ directory
cd scripts
./run_demo.sh wyoming 1
```

If this works, you're ready!

---

## 🎯 Key Messages

### The Problem
> "Traditional RAG does ONE search. If that search misses key documents, you get the wrong answer. No second chances."

### The Solution
> "Agentic RAG uses intelligent agents that search MULTIPLE times from different angles. They find documents vanilla misses."

### The Results
> "On Wyoming housing law: Vanilla RAG 70% accurate, Agentic RAG 80-90% accurate. That's 10-20 points better."

### The Trade-off
> "Yes, it's 10x slower. But for accuracy-critical tasks like legal research, finding the right answer matters more than speed."

---

## 📊 Expected Demo Results

Running on Wyoming housing law (5-10 questions):

| Approach | Accuracy | Time/Question | Searches |
|----------|----------|---------------|----------|
| Vanilla RAG | ~70% | ~2 sec | 1 |
| Agentic RAG | ~80-90% | ~25 sec | 2-4 |

**Improvement**: +10-20 percentage points

---

## 🎤 During Your Presentation

### Keep Open
- `CHEATSHEET.md` - Quick reference
- Terminal ready in `dev_rel/scripts/`
- Backup screenshots

### Quick Commands
```bash
# 3 questions (quick demo)
./run_demo.sh wyoming 3

# 5 questions (standard demo)
./run_demo.sh wyoming 5

# 10 questions (full demo)
./run_demo.sh wyoming 10

# Different states
./run_demo.sh idaho 5
./run_demo.sh iowa 5
```

### If Demo Breaks
1. Stay calm
2. Show backup screenshots
3. Explain what should have happened
4. Continue with the story

---

## 📖 Additional Resources

### In This Folder
- `CHEATSHEET.md` - Quick reference during demos
- `guides/QUICK_START.md` - Setup instructions
- `guides/PRESENTATION_STRATEGY.md` - Detailed presentation guide

### In Parent Repository
- `../README.md` - Main project documentation
- `../examples/` - Code examples to reference
- `../docs/` - Technical documentation

---

## 🎥 Recording Tips

1. **Test everything first** - Run the demo at least once before recording
2. **Use small numbers** - 3-5 questions is enough to show the difference
3. **Show, don't tell** - Run live code, not just slides
4. **Highlight wins** - Point out when agentic gets it right and vanilla doesn't
5. **Address cost** - Be upfront about the speed/cost trade-off
6. **Keep it simple** - Focus on one key message: agents find docs vanilla misses

---

## 🌟 Three States Available

Try demos with different states:

- **Wyoming** - 99 housing law questions
- **Idaho** - Housing law questions available
- **Iowa** - 108 housing law questions

All use the HousingQA dataset with ground truth answers for evaluation.

---

## 💡 Customization Tips

### For Your Domain
1. Replace HousingQA dataset with your documents
2. Update Qdrant collections
3. Modify agent prompts in `../../examples/3_agentic_rag/agentic_rag.py`
4. Keep the comparison demo structure

### For Your Audience
- **Developers**: Show code, explain architecture
- **Business**: Show accuracy metrics, ROI
- **Researchers**: Show benchmarks, methodology

---

## 🚀 Quick Commands Reference

```bash
# Navigate to scripts
cd dev_rel/scripts

# Quick 3-question demo
./run_demo.sh wyoming 3

# Standard 5-question demo
./run_demo.sh wyoming 5

# Full 10-question demo
./run_demo.sh wyoming 10

# Different states
./run_demo.sh idaho 5
./run_demo.sh iowa 5

# Manual run (with more control)
python compare_vanilla_vs_agentic.py --state wyoming --limit 5
```

---

## 📞 Need Help?

1. **Demo gets stuck?** → `TROUBLESHOOTING.md` ⚠️ START HERE!
2. **Setup issues?** → `guides/QUICK_START.md`
3. **Presentation prep?** → `guides/PRESENTATION_STRATEGY.md` + `CHEATSHEET.md`
4. **Technical questions?** → `../docs/AGENTIC_RAG_VALUE.md`
5. **Code structure?** → `../docs/REPOSITORY_GUIDE.md`

---

## ✅ Success Checklist

Your demo is ready when:
- [ ] You can run `./run_demo.sh wyoming 3` successfully
- [ ] You understand the key message (agents find docs vanilla misses)
- [ ] You can explain the accuracy difference
- [ ] You can address the speed/cost trade-off
- [ ] You have backup screenshots
- [ ] You've practiced your timing

---

**Ready to demo? 🎬**

```bash
cd scripts
./run_demo.sh wyoming 5
```

**Good luck with your presentation!** 🌟

---

## 📦 Sharing This Demo

To share with others:
1. Copy this entire `dev_rel/` folder
2. Include `../examples/` for code reference
3. Include `../requirements.txt` for dependencies
4. Include `../.env.example` as template

That's all they need to run the demo!
