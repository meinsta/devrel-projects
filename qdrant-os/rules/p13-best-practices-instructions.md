# Page 13: Best Practices for Instructions

## Rules for qdrant-os

### R-36: Be specific and actionable
GOOD:
```
Run `python scripts/validate.py --input {filename}` to check data format.
If validation fails, common issues include:
- Missing required fields (add them to the CSV)
- Invalid date formats (use YYYY-MM-DD)
```

BAD:
```
Validate the data before proceeding.
```

Every instruction must be specific enough that Claude can execute it without guessing. If an instruction says "validate" or "check" without saying HOW, it is too vague.

### R-37: Include error handling in instructions
Every skill must have a Common Issues section with actionable fixes:
```markdown
## Common Issues

### Connection Refused
If you see "Connection refused":
1. Verify Qdrant is running: check the health endpoint
2. Confirm the URL and port are correct
3. Check if the collection exists
```

### R-38: Reference bundled resources clearly
When linking to references, be explicit about what they contain:
```markdown
Before tuning HNSW parameters, consult `references/hnsw-guide.md` for:
- ef_construct vs ef tradeoffs
- Recommended values by dataset size
- Benchmarks comparing configurations
```

Do NOT just say "see references/hnsw-guide.md" without context.

### R-39: Use progressive disclosure in practice
Keep SKILL.md focused on core decision tree and instructions. Move detailed documentation to `references/` and link to it. The SKILL.md body should be under 5,000 words. If it is longer, split content into references.

### R-40: For qdrant-os, the "how" lives in references, not the body
The SKILL.md body contains the decision tree (when/why). The references/ folder contains the detailed documentation (how). This enforces our core principle:
- Body: "Apply quantization" (the decision)
- Reference: "Here's how to configure scalar quantization step by step" (the documentation)

## How we hit this
- [ ] No instruction uses vague words like "validate", "check", "ensure" without specifics
- [ ] Every reference link includes a description of what the reference contains
- [ ] SKILL.md body is under 5,000 words (CI check)
- [ ] Detailed how-to content lives in references/, not in the SKILL.md body
