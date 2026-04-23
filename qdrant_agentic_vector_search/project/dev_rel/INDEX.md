# 📦 Dev Rel Package - Complete Index

Everything for presentations, demos, and videos in one organized folder!

---

## 📂 What's Here

```
dev_rel/
├── README.md           ← Start here! Complete demo guide
├── CHEATSHEET.md       ← Quick reference during demos
├── INDEX.md            ← This file
│
├── scripts/            ← Runnable demo scripts
│   ├── compare_vanilla_vs_agentic.py
│   └── run_demo.sh     ← One command to run demo!
│
└── guides/             ← Preparation materials
    ├── QUICK_START.md
    └── PRESENTATION_STRATEGY.md
```

---

## 🚀 Quick Start

```bash
# From dev_rel/scripts/ directory
./run_demo.sh wyoming 5
```

That's it! You'll see vanilla vs agentic RAG comparison.

---

## 📖 Reading Order

### Before Your First Demo
1. **README.md** - Overview of what's available
2. **guides/QUICK_START.md** - Setup (5 minutes)
3. **guides/PRESENTATION_STRATEGY.md** - Plan your presentation
4. **CHEATSHEET.md** - Review talking points

### During Demo Prep
1. **CHEATSHEET.md** - Quick reference (keep this open!)
2. Test run: `cd scripts && ./run_demo.sh wyoming 3`
3. Have backup screenshots ready

### During Recording/Presentation
1. **CHEATSHEET.md** - Keep visible
2. Terminal in `scripts/` directory
3. Run: `./run_demo.sh wyoming 5`

---

## 📋 File Purposes

### `README.md`
- **What**: Complete demo package guide
- **When**: First time exploring this folder
- **Length**: ~5 minutes to read
- **Contains**: All demo scenarios, commands, tips

### `CHEATSHEET.md`
- **What**: Quick reference card
- **When**: During live demos/recordings
- **Length**: ~2 minutes to scan
- **Contains**: Commands, talking points, Q&A prep

### `INDEX.md` (this file)
- **What**: Navigation guide
- **When**: Finding specific files
- **Length**: ~1 minute to scan

### `scripts/compare_vanilla_vs_agentic.py`
- **What**: Main demo script
- **When**: Run this for demos
- **Usage**: `python compare_vanilla_vs_agentic.py --state wyoming --limit 5`
- **Output**: Side-by-side accuracy comparison

### `scripts/run_demo.sh`
- **What**: One-command demo runner
- **When**: Quick demos
- **Usage**: `./run_demo.sh wyoming 5`
- **Does**: Checks setup + runs comparison

### `guides/QUICK_START.md`
- **What**: Setup instructions
- **When**: First time setup
- **Length**: ~5 minutes
- **Contains**: Installation, configuration, verification

### `guides/PRESENTATION_STRATEGY.md`
- **What**: Presentation guide
- **When**: Planning your demo
- **Length**: ~10 minutes to read
- **Contains**: Demo scripts, talking points, tips

---

## 🎯 Use Cases

### Quick Video (3 min)
```bash
cd scripts
./run_demo.sh wyoming 3
```
Show comparison, explain improvement.

### Conference Talk (10 min)
```bash
# Show examples progression
cd ../../examples
python 1_data_exploration/explore_dataset.py --state wyoming
python 2_vanilla_rag/simple_rag.py --state wyoming --limit 5
python 3_agentic_rag/agentic_rag.py --state wyoming --limit 5

# Then comparison
cd ../dev_rel/scripts
./run_demo.sh wyoming 5
```

### Workshop (30+ min)
Let participants:
1. Run examples themselves
2. Modify agent prompts
3. Try their own questions
4. Compare results

---

## 🎬 Quick Commands

```bash
# Navigate here
cd dev_rel/scripts

# Quick demo (3 questions)
./run_demo.sh wyoming 3

# Standard demo (5 questions)
./run_demo.sh wyoming 5

# Full demo (10 questions)
./run_demo.sh wyoming 10

# Different states
./run_demo.sh idaho 5
./run_demo.sh iowa 5

# Manual (more control)
python compare_vanilla_vs_agentic.py --state wyoming --limit 5 --help
```

---

## 💡 Pro Tips

1. **Always test first**: Run `./run_demo.sh wyoming 1` before recording
2. **Keep CHEATSHEET open**: Have it visible during presentation
3. **Use small numbers**: 3-5 questions is enough
4. **Have backups**: Screenshots in case of tech issues
5. **Know your audience**: Adjust complexity based on who's watching

---

## 🎨 Customization

### For Your Domain
Adapt for medical, technical, policy docs:
1. Replace dataset (still use HousingQA structure)
2. Update collection names in scripts
3. Modify agent prompts in `../../examples/3_agentic_rag/`

### For Your Style
1. Adjust talking points in CHEATSHEET.md
2. Add your branding to slides
3. Create your own demo scenarios

---

## 📦 Sharing This Package

To share with colleagues:

**Minimal (demo only)**:
- Copy entire `dev_rel/` folder
- Include `../requirements.txt`
- Include `../.env.example`

**Complete (with code)**:
- Copy entire repository root
- They can explore examples too

---

## 🆘 Troubleshooting

### "Command not found: ./run_demo.sh"
```bash
chmod +x run_demo.sh
```

### "ModuleNotFoundError"
```bash
pip install -r ../../requirements.txt
```

### ".env file not found"
Create `.env` in repository root with:
```
OPENAI_API_KEY=sk-...
QDRANT_CLOUD_URL=https://...
QDRANT_API_KEY=...
```

### "No such collection"
Verify Qdrant collections exist:
```bash
python ../../examples/1_data_exploration/inspect_collections.py
```

---

## 📚 Additional Resources

### In This Folder
- `README.md` - Complete guide
- `CHEATSHEET.md` - Quick reference
- `guides/` - Setup & strategy

### In Parent Repository
- `../README.md` - Project overview
- `../examples/` - Code to show/modify
- `../docs/` - Technical documentation

---

## ✅ Pre-Demo Checklist

- [ ] Read `README.md` for overview
- [ ] Read `CHEATSHEET.md` for talking points
- [ ] Test: `cd scripts && ./run_demo.sh wyoming 1`
- [ ] Verify output looks correct
- [ ] Have backup screenshots ready
- [ ] Know your 3 key messages
- [ ] Prepared for Q&A

---

## 🎯 Success = Clear Message

Your demo is successful when viewers understand:

1. **The Problem**: Traditional RAG misses documents (one search only)
2. **The Solution**: Agents search multiple times from different angles
3. **The Benefit**: 10-20% accuracy improvement on complex questions
4. **The Trade-off**: Slower but worth it for accuracy-critical tasks

---

**Ready to demo?** 🚀

```bash
cd scripts
./run_demo.sh wyoming 5
```

**Good luck!** 🎥

