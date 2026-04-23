# Troubleshooting Guide

## 🛑 Issue: CrewAI "Maximum iterations reached"

**This is the ACTUAL issue!** The agents are looping infinitely and can't complete.

### Symptoms
- Script gets stuck during "Processing"
- Terminal shows: `Maximum iterations reached. Requesting final answer.`
- Terminal shows: `WARNING: ...status 401...`

### SOLUTION: Use the Fixed Script

```bash
cd dev_rel/scripts

# Use the FIXED version (prevents infinite loops)
python3 compare_vanilla_vs_agentic_fixed.py --state wyoming --limit 1
```

**This should complete in ~30 seconds!**

### What Was Fixed
1. ✅ Disabled CrewAI telemetry (no more 401 warnings)
2. ✅ Simplified agent tasks to prevent loops
3. ✅ Added `allow_delegation=False` to prevent delegation loops
4. ✅ Limited `max_iter` to 3-5 iterations
5. ✅ Clearer task termination conditions

---

## 🚀 Alternative: Vanilla-Only Mode

If agentic still has issues, use vanilla-only (always works):

```bash
cd dev_rel/scripts
python3 vanilla_only.py --state wyoming --limit 10
```

Fast, reliable, no agents needed! Good for quick demos.

---

## Issue: Comparison Script Gets Stuck on "Processing" (Original Issue)

### Common Causes

#### 1. **Agentic RAG Agents Taking Time**
The agentic RAG part can take 20-30 seconds per question. It's not stuck, just slow!

**Solution**: Be patient or add verbose output to see progress.

#### 2. **Verbose Mode Disabled**
By default, agent output is hidden (`verbose=False`), so it looks stuck.

**Solution**: Enable verbose mode to see what's happening.

#### 3. **API Rate Limits**
OpenAI API calls might be rate-limited or slow.

**Solution**: Check your API keys and quotas.

#### 4. **Large Question Limit**
Testing too many questions at once.

**Solution**: Start with `--limit 1` to test.

---

## Quick Fixes

### Fix 1: Run with Verbose Mode

Edit `dev_rel/scripts/compare_vanilla_vs_agentic.py`:

Find lines ~92 and ~119 (in `agentic_rag_answer` function):

```python
research_agent = Agent(
    role="Research Specialist",
    goal=f"Find relevant {state_name.title()} statutes through strategic search",
    backstory=f"""...""",
    tools=[qdrant_tool],
    verbose=False,  # ← Change this to True
    llm=LLM(model="gpt-4o-mini", temperature=0)
)

analyst_agent = Agent(
    role="Legal Analyst",
    goal="Provide accurate Yes/No answer",
    backstory=f"""...""",
    tools=[qdrant_tool],
    verbose=False,  # ← Change this to True
    llm=LLM(model="gpt-4o-mini", temperature=0)
)
```

Change both `verbose=False` to `verbose=True`.

Also find line ~171 (in `agentic_rag_answer`):

```python
crew = Crew(
    agents=[research_agent, analyst_agent],
    tasks=[research_task, analysis_task],
    process=Process.sequential,
    verbose=False  # ← Change this to True
)
```

Change to `verbose=True`.

### Fix 2: Test with Single Question

```bash
cd dev_rel/scripts
python3 compare_vanilla_vs_agentic.py --state wyoming --limit 1
```

This tests with just ONE question to see if it completes.

### Fix 3: Check Dependencies

```bash
cd ../..  # Back to repo root
pip3 install -r requirements.txt
```

### Fix 4: Check .env File

Make sure you have:
```bash
# In repo root: .env
OPENAI_API_KEY=sk-...
QDRANT_CLOUD_URL=https://...
QDRANT_API_KEY=...
```

### Fix 5: Test Vanilla Only First

```bash
cd ../../examples/2_vanilla_rag
python3 simple_rag.py --state wyoming --limit 1
```

If this works quickly, the issue is with agentic RAG.

---

## Debug Script

Run this to diagnose the issue:

```bash
cd dev_rel/scripts
python3 test_quick.py
```

This will tell you:
- ✓ Are dependencies installed?
- ✓ Are API keys set?
- ✓ Can it connect to Qdrant?
- ✓ Can it load the dataset?

---

## Expected Timing

### Vanilla RAG
- Per question: ~2 seconds
- 5 questions: ~10 seconds

### Agentic RAG  
- Per question: ~20-30 seconds ⚠️ **This is normal!**
- 5 questions: ~2-3 minutes

**So if you run with `--limit 5`, expect 3-4 minutes total!**

---

## What "Processing" Means

When you see "Processing" with a progress bar:

```
Processing: 20%|████      | 1/5 [00:25<01:40, 25.0s/it]
```

This means:
- It's on question 1 of 5
- Took 25 seconds (normal for agentic!)
- Estimated 1:40 remaining

**It's not stuck, it's just slow!**

---

## Quick Workaround: Vanilla Only

If agentic RAG is too slow, test vanilla RAG only:

```bash
cd ../../examples/2_vanilla_rag
python3 simple_rag.py --state wyoming --limit 10
```

This is much faster (~20 seconds for 10 questions).

---

## If Still Stuck

### Enable Full Debug Output

1. Edit `compare_vanilla_vs_agentic.py`
2. Change all `verbose=False` to `verbose=True`
3. Run again:

```bash
python3 compare_vanilla_vs_agentic.py --state wyoming --limit 1
```

You'll see exactly what the agents are doing:
- "Thought: ..."
- "Action: ..."
- "Observation: ..."

### Check for Errors

Run with error output:

```bash
python3 compare_vanilla_vs_agentic.py --state wyoming --limit 1 2>&1 | tee debug.log
```

Check `debug.log` for errors.

---

## Common Issues

### Issue: "No module named 'crewai'"
**Fix**: `pip3 install -r ../../requirements.txt`

### Issue: "OPENAI_API_KEY not set"
**Fix**: Create `.env` file in repo root

### Issue: "No such collection"
**Fix**: Verify collections exist:
```bash
python3 ../../examples/1_data_exploration/inspect_collections.py
```

### Issue: Takes forever on first run
**Cause**: FastEmbed downloading model (~90MB)  
**Fix**: Wait for first download, then it's cached

---

## Recommended: Start Small

**Best practice for first run:**

```bash
# Test with just 1 question
cd dev_rel/scripts
python3 compare_vanilla_vs_agentic.py --state wyoming --limit 1
```

**Expected output:**
- Vanilla RAG: ~2 seconds
- Agentic RAG: ~25 seconds
- Total: ~30 seconds

If this works, you know everything is set up correctly!

Then try 3-5 questions for actual demos.

---

## Performance Tips

### For Faster Testing
```bash
# Skip agentic, just test vanilla
cd ../../examples/2_vanilla_rag
python3 simple_rag.py --state wyoming --limit 10
```

### For Demos
```bash
# Use 3-5 questions max
cd dev_rel/scripts
./run_demo.sh wyoming 3  # ~1-2 minutes
```

### For Full Evaluation
```bash
# Use 10+ questions (but be patient!)
./run_demo.sh wyoming 10  # ~5-6 minutes
```

---

## TL;DR

**If stuck on "Processing":**

1. **Be patient** - Agentic RAG takes 20-30 seconds per question
2. **Start small** - Test with `--limit 1` first
3. **Enable verbose** - Change `verbose=False` to `verbose=True` in script
4. **Check timing** - 5 questions = 3-4 minutes total (normal!)

**Quick test:**
```bash
cd dev_rel/scripts
python3 compare_vanilla_vs_agentic.py --state wyoming --limit 1
```

Wait 30 seconds. If it completes, it's working fine!

