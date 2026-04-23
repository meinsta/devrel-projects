# Rules checklist for Qdrant skills

Distilled from the 95 rules in `rules/`. These are the checks that matter
most when building Qdrant-specific skills.

## Structure rules

- **R-06:** Skill folder must contain SKILL.md. Optional: scripts/, references/, assets/
- **R-07:** Three-level progressive disclosure:
  - Level 1: Frontmatter (when to trigger). Always loaded.
  - Level 2: SKILL.md body (why and what). Loaded on activation.
  - Level 3: references/ files (how). Loaded on demand.
- **R-08:** No skill assumes it is alone. Multiple skills can be active.
- **R-10:** MCP provides connectivity. Skills provide knowledge.

## Naming rules

- **R-22:** File MUST be named `SKILL.md` (exact case, not skill.md or Skill.md)
- **R-23:** Folder name in kebab-case (e.g., `qdrant-memory-optimization`)
- **R-26:** `name` field in frontmatter must match folder name exactly

## Description rules

- **R-25:** YAML frontmatter with `---` delimiters required
- **R-28:** Description must include trigger phrases. Use "Use when" pattern.
- **R-31:** No XML angle brackets in frontmatter (no `<` or `>`)
- **R-51:** Description must include "Do NOT" negative triggers
- **R-91:** Description must be under 1024 characters

## Content rules

- **R-35:** Troubleshooting section mandatory (minimum 2 error cases)
- **R-39:** Progressive disclosure prevents bloat. Do not front-load everything.
- **R-40:** "How" lives in references/, not in SKILL.md body
- **R-77:** SKILL.md body must be under 5,000 words

## Testing rules

- **R-44:** triggers.json required with 4+ positive and 4+ negative test cases
- **R-45:** Functional tests required (does the skill produce correct output?)
- **R-46:** Before/after performance comparison (token count, accuracy, steps)
- **R-50:** Watch for undertriggering (skill not activating when it should)
- **R-51:** Watch for overtriggering (skill activating when it should not)

## Qdrant-specific rules

- **R-67:** Decision trees with concrete thresholds, not vague guidance
  - BAD: "for large datasets, consider quantization"
  - GOOD: "if dataset exceeds 10M vectors, apply scalar quantization"
- **R-68:** Domain-specific intelligence is the primary pattern
  - Embed SA knowledge, not just tool access
  - Every recommendation explains WHY (transparency)
  - Trade-offs always documented
- **R-84:** Pre-build: identify 2-3 concrete use cases first
- **R-88:** Qdrant-specific checks:
  - Skill starts with a situation/problem, NOT a feature name
  - Decision tree uses concrete thresholds
  - All doc links resolve to real Qdrant documentation
  - triggers.json included
  - Before/after performance comparison documented

## Quick validation commands

```bash
# Run the linter
python3 scripts/lint-skills.py

# Check word count
wc -w skills/YOUR-SKILL/SKILL.md

# Check description length
python3 -c "
import re
content = open('skills/YOUR-SKILL/SKILL.md').read()
fm_end = content.find('---', 3)
fm = content[3:fm_end]
for line in fm.split('\n'):
    if line.startswith('description:'):
        desc = line[12:].strip()
        break
print(f'Description: {len(desc)} chars (max 1024)')
"
```
