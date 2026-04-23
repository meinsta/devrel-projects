# Page 22: Patterns - Problem-First vs Tool-First + Sequential Workflows

## Rules for qdrant-os

### R-63: Choose problem-first or tool-first framing
Two approaches:
- **Problem-first**: "I need to reduce memory usage" -> Skill orchestrates the right steps. Users describe outcomes; the skill handles the tools.
- **Tool-first**: "I have Qdrant MCP connected" -> Skill teaches Claude optimal workflows. Users have access; the skill provides expertise.

**qdrant-os external skills are problem-first.** Users come with problems ("too much RAM", "bad search results"), not tool requests.

**qdrant-os internal skills can be either.** Marketing skills might be tool-first ("I have LinkedIn connected, how do I run a campaign"). Engineering skills might be problem-first ("deferred indexing is slow").

### R-64: Pattern 1 - Sequential workflow orchestration
Use when: users need multi-step processes in a specific order.

For qdrant-os, this looks like:
```markdown
## Workflow: Diagnose Memory Issue

### Step 1: Check Collection Info
Call: get_collection to retrieve current parameters
Look for: vector dimension, quantization config, storage type

### Step 2: Calculate Expected Memory
Formula: vectors * dimensions * 4 bytes (float32)
Compare with: actual reported usage

### Step 3: Recommend Fix
Based on gap between expected and actual:
- If vectors dominate: recommend quantization
- If HNSW dominates: recommend mmap storage
- If payload dominates: check payload index configuration
```

Key techniques:
- Explicit step ordering
- Dependencies between steps
- Validation at each stage
- Rollback instructions for failures

## How we hit this
- [ ] Every external skill is framed as problem-first (starts with user situation)
- [ ] Sequential workflows have numbered steps with clear dependencies
- [ ] Each step has a validation check before moving to the next
- [ ] Failure cases documented at each step
