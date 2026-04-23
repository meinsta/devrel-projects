# Page 23: Pattern 2 (Multi-MCP Coordination) + Pattern 3 (Iterative Refinement)

## Rules for qdrant-os

### R-65: Pattern 2 - Multi-MCP coordination
Use when: workflows span multiple services.

For qdrant-os internal skills, this is common:
```markdown
### Phase 1: Identify Issue (Qdrant MCP)
1. Query collection metrics
2. Check error logs
3. Identify bottleneck

### Phase 2: Document Finding (Notion/Docs MCP)
1. Create incident report
2. Link to relevant collection
3. Tag relevant team members

### Phase 3: Notify Team (Slack MCP)
1. Post summary to #engineering
2. Include metrics and links
```

Key techniques:
- Clear phase separation
- Data passing between MCPs (output of phase 1 feeds into phase 2)
- Validation before moving to next phase
- Centralized error handling

### R-66: Pattern 3 - Iterative refinement
Use when: output quality improves with iteration.

For qdrant-os, this applies to accuracy tuning:
```markdown
## Iterative Accuracy Improvement

### Initial Assessment
1. Run test queries against collection
2. Measure precision@10 and recall@10
3. Record baseline metrics

### Tuning Loop
1. Adjust HNSW ef parameter
2. Re-run test queries
3. Compare with baseline
4. If improved: keep change, try next parameter
5. If worse: revert, try different approach
6. Repeat until target accuracy reached or diminishing returns

### Finalization
1. Document final parameters
2. Record before/after metrics
3. Update collection configuration
```

Key techniques:
- Explicit quality criteria (what "good enough" means)
- Iterative improvement with measurable progress
- Know when to stop (diminishing returns threshold)
- Validation scripts where possible

## How we hit this
- [ ] Multi-MCP skills have clear phase boundaries with data handoff points
- [ ] Iterative skills define explicit "done" criteria (when to stop iterating)
- [ ] Each phase validates output before proceeding
- [ ] Error handling is centralized, not scattered per-phase
