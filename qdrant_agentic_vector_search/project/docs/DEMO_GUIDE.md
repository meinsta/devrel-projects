# Demo Presentation Guide

> **How to present the Agentic Vector Search demo in videos and presentations**

## 🎯 Demo Objective

Show that **agentic vector search powered by Qdrant** provides materially better results than traditional single-shot RAG through intelligent multi-step reasoning.

**Target audience**: Developers, AI engineers, technical decision-makers

**Key message**: Vector search + AI agents = Better information retrieval

---

## 🎬 5-Minute Demo Script

### 0:00-0:30 - Setup & Context (30 sec)

**What to say:**
> "Today I'm showing you the difference between traditional RAG and agentic RAG for legal research. We have three Qdrant collections with housing law statutes from Iowa, Idaho, and Wyoming. We'll ask the same question to both systems and compare the results."

**What to show:**
- Open terminal in the repo
- Quick ls to show clean structure
- Run `python setup/02_verify_collections.py` to show collections exist

**Key point**: Establish that the data is real legal statutes from the HousingQA dataset

---

### 0:30-2:00 - Vanilla RAG (1.5 min)

**What to say:**
> "First, let's see how traditional RAG handles this question. Traditional RAG searches the vector database once, retrieves the top results, and generates an answer. That's it - no reasoning, no refinement."

**Commands:**
```bash
python examples/01_vanilla_rag.py --state wyoming \
  --question "Is there a state/territory law regulating residential evictions?"
```

**What to show:**
- The single search happening (point out: "see - just one search")
- The retrieved documents (highlight they're about duties, not eviction procedures)
- The generated answer (note if it's incomplete/wrong)

**Key point**: "The system only searched once. If that search misses key information, the answer will be incomplete. And look - it did miss the eviction laws."

**Visual tip**: Have the question and "golden answer" visible on screen for comparison

---

### 2:00-4:00 - Agentic RAG (2 min)

**What to say:**
> "Now let's see how an AI agent handles this. The agent has the same search tool, but it can reason about the problem, search multiple times from different angles, and refine its approach based on what it finds."

**Commands:**
```bash
python examples/02_agentic_rag.py --state wyoming \
  --question "Is there a state/territory law regulating residential evictions?"
```

**What to show:**
- Agent reasoning (pause to read key parts of agent's thinking)
- Multiple searches happening
- Different search queries being tried
- Final comprehensive answer

**Key point**: "Notice how the agent searched 3 times with different queries. First for 'evictions', then for 'eviction procedures', then for the legal term 'forcible entry and detainer'. That multi-perspective approach found the eviction laws that the simple search missed."

**Visual tip**: Let the agent output stream naturally - the "thinking" is the demo!

---

### 4:00-4:45 - Side-by-Side Comparison (45 sec)

**What to say:**
> "Let's see both answers side by side."

**Commands:**
```bash
python examples/03_demo_comparison.py --state wyoming
# Select the eviction question
```

**What to show:**
- The comparison table (approach, searches, time)
- Both answers displayed side-by-side
- Key differences highlighted

**Key point**: "The agentic approach took 8x longer, but it found the right information. For legal research where accuracy is critical, that's absolutely worth it."

---

### 4:45-5:00 - Wrap Up (15 sec)

**What to say:**
> "This shows the power of combining vector search with agentic AI. Qdrant provides the fast semantic search foundation, and CrewAI agents add intelligent reasoning on top. The result? Better answers through smarter retrieval."

**Call to action:**
- "Try this yourself - the repo is ready to run"
- "Works with any domain where thorough research matters"
- "Links in the description"

---

## 🎨 Presentation Tips

### Visual Setup

1. **Terminal**: Use a large font (16-18pt)
2. **Color scheme**: High contrast (light background for screen recording)
3. **Split screen**: Terminal on one side, slides/notes on other
4. **Highlight key output**: Draw attention to important lines

### Pacing

- **Speak slowly**: Let viewers absorb what's happening
- **Pause on agent thinking**: Don't rush through the reasoning
- **Read key phrases**: Help viewers understand what the agent is doing
- **Emphasize the contrast**: Make it clear when vanilla fails and agent succeeds

### Technical Tips

- **Pre-run once**: Ensure everything works before recording
- **Have fallback**: If live demo fails, have a recording
- **Test timing**: Practice to hit 5 minutes
- **Prepare for delays**: Agent can take 30-60s (fill this time with explanation)

---

## 📝 Key Talking Points

### What Makes Agentic RAG Different?

1. **Multiple search perspectives**: Not limited to a single query
2. **Iterative refinement**: Can improve based on initial results
3. **Strategic reasoning**: Understands what information is needed
4. **Adaptive behavior**: Complex questions get more thorough treatment

### Why Vector Search Enables This

1. **Fast semantic search**: Agent can search multiple times because each search is fast
2. **Flexible queries**: Can reformulate and search from different angles
3. **Qdrant's performance**: Handles repeated queries efficiently
4. **Named vectors**: Clean integration with agent tools

### When Agentic Approach Wins

- ✅ Complex questions requiring multi-angle research
- ✅ Legal, medical, technical domains where accuracy matters
- ✅ Questions where important info might be scattered
- ✅ Scenarios where missing key information has consequences

### When Vanilla RAG is Fine

- Simple, straightforward questions
- Speed is critical over accuracy
- Information is typically found in one place
- Lower stakes applications

---

## 🎯 Demo Variations

### Quick Version (2 minutes)

Just run the comparison demo:
```bash
python examples/03_demo_comparison.py --state wyoming
```

Show side-by-side results and explain the difference.

### Deep Dive Version (10 minutes)

Add:
- Show the code structure (agent definitions)
- Explain how the Qdrant tool works
- Walk through agent reasoning in detail
- Show evaluation metrics from `evaluation/`

### Interactive Version (Live Q&A)

Take questions from the audience and answer them live:
```bash
python examples/02_agentic_rag.py
# Let audience suggest questions
```

Shows that it works for any question, not just pre-selected ones.

---

## ❓ Anticipated Questions & Answers

### Q: "How much slower is the agentic approach?"

**A**: "Typically 5-10x slower. Vanilla RAG takes 2-5 seconds, agentic takes 15-30 seconds. For legal research where a wrong answer could cost thousands of dollars, that's a worthwhile tradeoff. You can also optimize by running searches in parallel."

### Q: "Does this work with other databases besides Qdrant?"

**A**: "Yes, the agent pattern works with any vector database. Qdrant is great for this because of its speed and named vector support, but you could adapt the tool to use Pinecone, Weaviate, etc."

### Q: "Can I use a different LLM?"

**A**: "Absolutely. The code uses GPT-4o-mini but you can swap in Claude, Llama, or any other model that CrewAI supports. Just change the LLM configuration."

### Q: "What about cost?"

**A**: "Agentic RAG costs more because it makes multiple LLM calls. For this demo, we're talking a few cents per question. For production, you'd optimize by caching, parallel execution, and stopping early when the agent has enough information."

### Q: "Does it always find the right answer?"

**A**: "Not always - we tested on 99 Wyoming questions and got 80% accuracy vs 70% for vanilla. It's a significant improvement but not perfect. The value is in finding more relevant context, which helps the LLM give better answers."

### Q: "Could the agent search forever?"

**A**: "We set max iterations (usually 8-10) so the agent will stop even if not satisfied. In practice, agents typically search 2-4 times before they have enough information."

### Q: "What if my documents are longer than 512 tokens?"

**A**: "This demo uses pre-chunked statutes. For your data, you'd chunk longer documents first. The `src/chunker.py` module has examples of semantic chunking strategies."

---

## 🚀 After the Demo

### Follow-Up Resources

Point viewers to:
1. **This repo**: "Clone it and try yourself"
2. **Qdrant docs**: "Learn more about vector search"
3. **CrewAI docs**: "Explore agent frameworks"
4. **HousingQA paper**: "See the original dataset research"

### Engagement Ideas

- **Challenge**: "Try it with your own documents"
- **Comparison**: "Test different agent configurations"
- **Share results**: "Let us know how it works for your use case"

### Next Steps for Viewers

```bash
# 1. Clone the repo
git clone <your-repo-url>

# 2. Install dependencies
uv pip install -e .

# 3. Setup environment
cp .env.example .env
# Add your API keys

# 4. Ingest data
python setup/01_ingest_data.py

# 5. Run demo
python examples/03_demo_comparison.py
```

---

## 📊 Supporting Metrics (Optional)

If time permits, show evaluation results:

```bash
# Show existing evaluation results
ls evaluation_results/

# Or run quick evaluation
python evaluation/compare_results.py
```

**Talking points**:
- "We tested this on 99 real legal questions"
- "Agentic RAG improved accuracy by 10 percentage points"
- "The difference becomes critical for complex questions"

---

## ✨ Demo Success Checklist

Before presenting, ensure:

- [ ] Collections are loaded and verified
- [ ] .env file has valid API keys
- [ ] All examples run without errors
- [ ] Terminal font is large and readable
- [ ] Example questions are tested
- [ ] Timing is practiced (5 min target)
- [ ] Fallback recording is ready
- [ ] Links are prepared for description

**Good luck with your demo! 🎉**

---

## 💬 Feedback Loop

After demos, note:
- Questions that came up
- What resonated most
- What was confusing
- Timing adjustments needed

Use this to refine future presentations.

