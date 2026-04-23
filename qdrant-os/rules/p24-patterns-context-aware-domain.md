# Page 24: Pattern 4 (Context-Aware Tool Selection) + Pattern 5 (Domain-Specific Intelligence)

## Rules for qdrant-os

### R-67: Pattern 4 - Context-aware tool selection
Use when: same outcome, different approach depending on context.

For qdrant-os, this is the core pattern for decision trees:
```markdown
## Smart Storage Configuration

### Decision Tree
1. Check dataset size and query pattern
2. Determine best storage configuration:
   - Small dataset (<100K vectors): keep in-memory, no quantization
   - Medium dataset (100K-10M): scalar quantization + in-memory
   - Large dataset (10M-100M): scalar quantization + mmap
   - Very large (>100M): product quantization + on-disk + sharding

### Execute Configuration
Based on decision:
- Apply the recommended quantization method
- Configure storage backend
- Set appropriate HNSW parameters for the tier

### Explain to User
Tell the user WHY this configuration was chosen for their specific case.
```

Key techniques:
- Clear decision criteria (not fuzzy)
- Fallback options if primary choice fails
- Transparency about why a choice was made

### R-68: Pattern 5 - Domain-specific intelligence
Use when: your skill adds specialized knowledge beyond tool access.

This is the PRIMARY pattern for qdrant-os. Our skills embed solution architect knowledge that goes beyond what the tools can tell you:

```markdown
## Before Recommending Configuration

### Assessment
1. Check current collection parameters via MCP
2. Apply domain knowledge:
   - cosine distance + normalized vectors = can use binary quantization
   - dot product + non-normalized = scalar quantization only
   - multi-tenancy = check payload index + tenant isolation
3. Document reasoning for recommendation

### Recommendation
IF binary quantization is safe:
  - Recommend it (32x memory reduction)
  - Link to binary quantization guide
ELSE:
  - Recommend scalar quantization (4x reduction)
  - Link to scalar quantization guide

### Explain Trade-offs
- Always explain what accuracy loss to expect
- Always explain what performance change to expect
- Link to benchmarks in references/
```

Key techniques:
- Domain expertise embedded in logic (not just tool calls)
- Expert knowledge that users would need a solutions architect to get
- Comprehensive documentation of reasoning
- Clear governance (why this recommendation was made)

## How we hit this
- [ ] Decision trees have concrete thresholds, not vague guidance
- [ ] Every recommendation explains WHY (transparency about choices)
- [ ] Domain expertise is the value-add, not tool orchestration alone
- [ ] Trade-offs are always documented (no recommendation without caveats)
