# Page 31: YAML Frontmatter Reference (Reference B)

## Rules for qdrant-os

### R-89: Required fields (every skill must have these)
```yaml
---
name: skill-name-in-kebab-case
description: What it does and when to use it. Include specific trigger phrases.
---
```

### R-90: Full field template for qdrant-os skills
```yaml
---
name: qdrant-memory-usage
description: Diagnoses and resolves high memory usage in Qdrant
  deployments. Use when user reports OOM kills, high RAM usage,
  or asks about "reducing memory", "quantization", or "collection
  too large". Do NOT use for installation or setup questions.
license: Apache-2.0
metadata:
  author: brian
  version: 1.0.0
  mcp-server: qdrant
  category: operations
  tags: [memory, quantization, performance, mmap]
---
```

### R-91: Field-by-field rules

**name**:
- kebab-case only
- Must match folder name
- No "claude" or "anthropic" prefix

**description**:
- Must include WHAT + WHEN + negative triggers
- Under 1024 characters
- No XML angle brackets
- Include quoted trigger phrases users would say

**license**:
- Apache-2.0 for qdrant-os (public)
- Omit for qdrant-os-internal (private)

**metadata.author**:
- First name, lowercase (e.g., "brian", "daniel")
- For internal skills, this is the domain expert who wrote it

**metadata.version**:
- Semver (1.0.0, 1.1.0, etc.)
- Bump minor version on description/trigger changes
- Bump patch version on content fixes

**metadata.mcp-server**:
- "qdrant" for external skills that use the Qdrant MCP server
- Omit for standalone skills

**metadata.category**:
- External: operations, development, migration, monitoring
- Internal: marketing, engineering, support, product

**metadata.tags**:
- Array of lowercase keywords for searchability

### R-92: Security hard rules
**Allowed**: strings, numbers, booleans, lists, objects, custom metadata, long descriptions (up to 1024 chars)

**Forbidden**:
- XML angle brackets (< >) anywhere in frontmatter
- Code execution in YAML
- "claude" or "anthropic" in skill name

## How we hit this
- [ ] CI validates all required fields present
- [ ] CI validates name matches folder name
- [ ] CI validates description under 1024 chars
- [ ] CI validates no forbidden characters
- [ ] Every skill uses the full field template (not just minimal)
