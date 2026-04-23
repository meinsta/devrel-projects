# Page 16: Functional Tests + Performance Comparison

## Rules for qdrant-os

### R-45: Functional tests verify correct outputs
Every external skill must have functional test cases covering:
- Valid outputs generated
- API/MCP calls succeed
- Error handling works
- Edge cases covered

Format:
```
Test: Diagnose memory issue with 1M vectors using 32GB RAM
Given: Collection with 1M 768-dim vectors, no quantization
When: Skill executes decision tree
Then:
  - Identifies vectors as primary memory consumer
  - Recommends scalar quantization
  - Links to correct quantization reference doc
  - No broken links
```

### R-46: Performance comparison is required for external skills
Every external skill must document a before/after comparison:

```
Without skill:
- User provides context each time
- 8+ back-and-forth messages
- Links to wrong docs twice
- 12,000 tokens consumed

With skill:
- Skill activates on problem description
- 2 clarifying questions only
- Points to correct doc on first try
- 6,000 tokens consumed
```

The skill must REDUCE: message count, token usage, and incorrect recommendations.

### R-47: Use skill-creator for first drafts
Use the skill-creator skill in Claude.ai to generate initial skill drafts:
"Use the skill-creator skill to help me build a skill for [use case]"

skill-creator can:
- Generate skills from natural language descriptions
- Produce properly formatted SKILL.md with frontmatter
- Suggest trigger phrases and structure
- Flag common issues (vague descriptions, missing triggers)
- Suggest test cases based on the skill's purpose

Note: skill-creator helps you design and refine, but does NOT run automated test suites.

### R-48: Iterative improvement with skill-creator
After using a skill and hitting edge cases or failures, bring those examples back:
"Use the issues and solutions identified in this chat to improve how the skill handles [specific edge case]"

## How we hit this
- [ ] Every external skill has at least 3 functional test cases documented
- [ ] Every external skill has a before/after performance comparison
- [ ] First drafts use skill-creator, then refined manually
- [ ] Edge cases discovered in production fed back to skill-creator for refinement
