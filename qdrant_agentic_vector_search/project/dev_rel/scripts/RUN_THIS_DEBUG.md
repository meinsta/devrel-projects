# 🔍 Debug Instructions

## Run the debug script to see what CrewAI is doing

```bash
cd dev_rel/scripts

# Test with just 2 questions (keeps output manageable)
python3 debug_agents.py --state wyoming --limit 2
```

## What You'll See

The debug script shows:
1. ✅ What vanilla RAG does (step by step)
2. 🤖 What each agent thinks and does (verbose output)
3. 🔍 Tool calls to Qdrant
4. ❌ Exactly where it fails (if it does)

## Watch For

### If Question 1 works but Question 2 fails:
- Look for agent state issues
- Check if agents are reusing context
- See if task completion criteria are clear

### If you see "Maximum iterations reached":
- Agent is looping (not finding termination condition)
- Look at the agent's "Thought" and "Action" logs
- See what it's stuck on

## Common Issues

### Issue: "Thought: I need to search..."
Agent keeps trying to search even after finding results.

**Solution**: Task needs clearer termination (already fixed in `compare_vanilla_vs_agentic_fixed.py`)

### Issue: "Action: Delegate work to..."
Agent is trying to delegate when it shouldn't.

**Solution**: Set `allow_delegation=False` (already done in fixed version)

### Issue: Agent loops between same actions
Agent oscillating between search and analysis.

**Solution**: Simplify tasks, limit max_iter (already done in fixed version)

## What We're Looking For

Run this and look for patterns:

```bash
python3 debug_agents.py --state wyoming --limit 2 2>&1 | tee debug_output.log
```

Then check `debug_output.log` for:
- Where does Question 1 succeed?
- Where does Question 2 start to fail?
- What's different between them?

## Expected Behavior

**Question 1** should show:
```
→ Starting crew execution...
[Research Agent]
  Thought: I need to search for...
  Action: QdrantVectorSearch
  Observation: Found 5 statutes...
  Thought: I have enough information
  Final Answer: [list of statutes]

[Analyst Agent]
  Thought: Based on the statutes...
  Final Answer: Yes

→ Crew completed!
```

**Question 2** should do the same (but might not due to state issues)

## After Running

Share the output and we can see:
1. Is it a CrewAI state issue?
2. Is it a task definition issue?
3. Is it a tool issue?

Then we can fix accordingly!

