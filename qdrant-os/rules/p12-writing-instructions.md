# Page 12: Writing Main Instructions + Examples + Troubleshooting

## Rules for qdrant-os

### R-32: SKILL.md body structure template
After the frontmatter, every SKILL.md follows this structure:

```markdown
---
name: your-skill
description: [...]
---

# Your Skill Name

## Instructions

### Step 1: [First Major Step]
Clear explanation of what happens.

### Step 2: [Second Major Step]
...

## Examples

### Example 1: [common scenario]
User says: "[realistic user query]"
Actions:
1. [what the skill does]
2. [next action]
Result: [what success looks like]

## Troubleshooting

### Error: [Common error message]
**Cause:** [Why it happens]
**Solution:** [How to fix]
```

### R-33: For qdrant-os, adapt the template to decision trees
Our skills are problem-first, so the "Instructions" section is a decision tree:

```markdown
## Decision Tree

### Step 1: Identify the source
Check which component is consuming memory.
See `references/collection-params.md` for details.
- Vectors too large? -> Step 2
- HNSW index too large? -> Step 3
- Payload index bloated? -> Step 4

### Step 2: Apply quantization
...
```

### R-34: Examples use realistic user language
The "Examples" section must use actual phrases users would say, not formal technical descriptions:
- GOOD: "my qdrant is eating 32GB of RAM with 1M vectors"
- BAD: "Optimize memory utilization in production vector database deployment"

### R-35: Troubleshooting section is mandatory
Every skill must include at least 2 common error cases with:
- The actual error message or symptom
- Why it happens (root cause)
- How to fix it (specific steps, not vague advice)

## How we hit this
- [ ] Every SKILL.md has: Instructions, Examples, Troubleshooting sections
- [ ] Examples use real user language (sourced from Discord/support)
- [ ] Troubleshooting has at least 2 error cases
- [ ] Decision trees use arrow notation for branching
