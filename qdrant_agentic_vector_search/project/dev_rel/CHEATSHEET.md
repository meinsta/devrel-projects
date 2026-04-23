# 🎯 Demo Cheatsheet - Quick Reference

Keep this handy during your presentation!

## ⚡ Quick Commands

```bash
# Quick demo (3-5 questions)
./run_demo.sh wyoming 3

# Full demo (10 questions)
./run_demo.sh wyoming 10

# Try different states
./run_demo.sh idaho 5
./run_demo.sh iowa 5

# Explore data first
python examples/1_data_exploration/inspect_collections.py
python examples/1_data_exploration/explore_dataset.py --state wyoming

# Run individually
python examples/2_vanilla_rag/simple_rag.py --state wyoming --limit 5
python examples/3_agentic_rag/agentic_rag.py --state wyoming --limit 5
python demos/compare_vanilla_vs_agentic.py --state wyoming --limit 5
```

---

## 💬 Key Talking Points

### Opening
> "Today I'll show you why multi-agent search beats traditional RAG for complex questions."

### Vanilla RAG Problems
> "Vanilla RAG does ONE search. If that search misses key documents, you get the wrong answer. No second chances."

### Agentic RAG Solution
> "Agentic RAG uses intelligent agents that search MULTIPLE times from different angles. They find documents vanilla misses."

### Results
> "On Wyoming housing law, vanilla RAG: 70% accurate. Agentic RAG: 80-90% accurate. That's a 10-20 point improvement."

### Trade-offs
> "Yes, it's 10x slower. But for critical applications like legal research, accuracy matters more than speed."

### When to Use
> "Use vanilla for quick searches. Use agentic for accuracy-critical tasks where missing a document has consequences."

---

## 📊 Expected Results (Wyoming)

| Metric | Vanilla | Agentic |
|--------|---------|---------|
| Accuracy | ~70% | ~80-90% |
| Time/Q | ~2s | ~25s |
| Searches/Q | 1 | 2-4 |

---

## 🎬 3-Minute Demo Script

**[0:00-0:30] Setup**
- "Let me show you a housing law question from Wyoming"
- Show the question on screen

**[0:30-1:30] Vanilla RAG**
- Run: `python examples/2_vanilla_rag/simple_rag.py --state wyoming --limit 1`
- "Watch vanilla do ONE search"
- "It retrieves these 5 documents"
- "Gets answer: [show result]"
- "But that's wrong! It missed key statutes."

**[1:30-2:30] Agentic RAG**
- Run: `python examples/3_agentic_rag/agentic_rag.py --state wyoming --limit 1`
- "Now watch agentic RAG"
- "Search 1: Direct question"
- "Search 2: Key legal terms"
- "Search 3: Related concepts"
- "Gets answer: [show result]"
- "That's CORRECT!"

**[2:30-3:00] Comparison**
- Run: `python demos/compare_vanilla_vs_agentic.py --state wyoming --limit 5`
- Show accuracy table
- "Across multiple questions, agentic wins"
- "This is the power of intelligent search"

---

## 🎯 Visual Highlights

### Vanilla RAG Flow
```
Question → [1 Search] → [5 Documents] → [LLM] → Wrong Answer ❌
```

### Agentic RAG Flow
```
Question → [Research Agent: 2-3 searches]
        → [More documents found]
        → [Analysis Agent: follow-up search if needed]
        → [LLM with better context]
        → Correct Answer ✅
```

---

## 🔥 Demo Do's and Don'ts

### ✅ DO
- Start with the problem (traditional search fails)
- Use small numbers (3-5 questions max)
- Show live execution
- Highlight when agentic gets it right and vanilla doesn't
- Acknowledge the speed trade-off
- Make it interactive (take audience questions)

### ❌ DON'T
- Don't show too many questions (boring)
- Don't skip the vanilla example (need contrast)
- Don't ignore the cost (address it directly)
- Don't just show slides (run live code)
- Don't use jargon without explaining

---

## 💡 Audience-Specific Messages

### For Developers
"It's CrewAI agents with custom Qdrant search tools. Each agent can search multiple times."

### For Product/Business
"Traditional search: 70% accurate. Our approach: 90% accurate. For legal research, that matters."

### For Researchers
"Multi-agent retrieval with iterative refinement. Tested on HousingQA benchmark."

---

## 🐛 Troubleshooting Live

### If demo gets stuck on "Processing"
**This is NORMAL!** Agentic RAG takes 20-30 seconds per question.
- 1 question = ~30 seconds
- 3 questions = ~1-2 minutes total
- 5 questions = ~3-4 minutes total
- Be patient! It's working, just slow.

**Quick test:**
```bash
# Test with just 1 question to verify it works
python3 compare_vanilla_vs_agentic.py --state wyoming --limit 1
# Wait ~30 seconds. If it completes, everything is working!
```

**See what's happening:**
See `TROUBLESHOOTING.md` for how to enable verbose mode.

### If demo crashes
```bash
# Check .env file exists (must be in repo root!)
cat ../../.env

# Verify collections exist
python3 ../../examples/1_data_exploration/inspect_collections.py

# Check dependencies installed
pip3 list | grep crewai
```

### If results look wrong
- Check you're using the right state (wyoming, idaho, or iowa)
- Verify collections are populated
- Check API keys are valid

### If it's too slow
- Use --limit 3 (total ~1-2 min instead of 3-4 min)
- Explain: "This is expected - agentic is thorough not fast"
- Alternative: Show vanilla only (much faster)

---

## 📱 Backup Plan

If live demo fails, have screenshots ready:
1. Vanilla RAG result (wrong answer)
2. Agentic RAG result (correct answer)
3. Comparison table showing accuracy

---

## 🎤 Q&A Prep

**Q: How much slower is it?**
A: "About 10x slower - 2 seconds vs 25 seconds per question. But for accuracy-critical tasks, it's worth it."

**Q: Does it always work better?**
A: "Not always. Sometimes vanilla gets lucky. But across many questions, agentic is consistently 10-20 points more accurate."

**Q: What about cost?**
A: "More LLM calls means higher cost - about 5x. For legal research that's worth it. For casual search, maybe not."

**Q: Can I use this with my data?**
A: "Absolutely! Load your documents into Qdrant, adjust the agent prompts for your domain, and you're good to go."

**Q: What about hallucinations?**
A: "Agents are grounded in search results. They can't make up documents. But they can still misinterpret - that's why we show sources."

---

## 🚀 Quick Start from Scratch

```bash
# 1. Setup
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your keys

# 2. Verify
python examples/1_data_exploration/inspect_collections.py

# 3. Demo
./run_demo.sh wyoming 5
```

---

## 📞 Emergency Contact

- Check `docs/QUICK_START.md` for setup help
- Check `docs/DEMO_STRATEGY.md` for presentation tips
- Check `docs/REPOSITORY_GUIDE.md` for code structure

---

**You got this! 🎉**

Remember: The goal is to show WHY agentic search helps, not just that it exists.

Focus on the **problem → solution → results** story.

🎥 Break a leg!

