# Page 11: Writing Effective Descriptions + Optional Fields

## Rules for qdrant-os

### R-27: Description structure formula
Every description follows this formula:
```
[What it does] + [When to use it] + [Key capabilities]
```

### R-28: Good description examples (study these)
```yaml
# Good - specific and actionable
description: Diagnoses and resolves high memory usage in Qdrant
  deployments. Use when user reports OOM kills, high RAM usage,
  or asks about "reducing memory", "quantization", or "collection
  too large".

# Good - includes trigger phrases
description: Guides accuracy tuning for Qdrant search results.
  Use when user says "search results are wrong", "low recall",
  "precision too low", or "HNSW tuning".

# Good - clear value proposition with negative trigger
description: Ensures zero-downtime Qdrant deployments during
  updates and migrations. Use when user asks about "rolling
  updates", "blue-green deployment", or "migration without
  downtime". Do NOT use for initial setup or installation.
```

### R-29: Bad description patterns (reject these in PR review)
```yaml
# Too vague - REJECT
description: Helps with Qdrant.

# Missing triggers - REJECT
description: Manages sophisticated vector database optimization.

# Too technical, no user triggers - REJECT
description: Implements the HNSW graph configuration model
  with hierarchical parameter relationships.
```

### R-30: Optional fields we use
```yaml
metadata:
  author: brian          # who wrote it
  version: 1.0.0        # semver
  category: operations   # or: development, marketing, etc.
  tags: [memory, quantization, performance]
```

### R-31: Security restrictions (hard rules)
Forbidden in frontmatter:
- XML angle brackets (< >) - because frontmatter appears in Claude's system prompt
- Skills with "claude" or "anthropic" in name (reserved by Anthropic)

## How we hit this
- [ ] CI lint: description matches formula [what] + [when] + [capabilities]
- [ ] CI lint: description contains at least 2 trigger phrases in quotes
- [ ] CI lint: no XML angle brackets anywhere in frontmatter
- [ ] CI lint: name does not contain "claude" or "anthropic"
- [ ] PR review: reject descriptions that match the "bad" patterns above
