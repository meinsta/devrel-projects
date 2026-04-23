# Page 10: Technical Requirements

## Rules for qdrant-os

### R-21: Exact file structure
Every skill folder follows this layout:
```
your-skill-name/
  SKILL.md                # Required
  scripts/                # Optional - executable code
    process_data.py
    validate.sh
  references/             # Optional - documentation
    api-guide.md
    examples/
  assets/                 # Optional - templates, etc.
    report-template.md
```

### R-22: SKILL.md naming is exact (case-sensitive)
- File MUST be named exactly `SKILL.md`
- No variations: `SKILL.MD`, `skill.md`, `Skill.md` are all WRONG
- Verify with `ls -la` before committing

### R-23: Skill folder naming rules
- Use kebab-case: `qdrant-memory-usage` CORRECT
- No spaces: `Qdrant Memory Usage` WRONG
- No underscores: `qdrant_memory_usage` WRONG
- No capitals: `QdrantMemoryUsage` WRONG

### R-24: No README.md inside skill folders
- Do NOT include README.md inside the skill folder
- All documentation goes in SKILL.md or references/
- The repo-level README is for human visitors (separate from skill folders)

### R-25: YAML frontmatter is the most important part
The frontmatter is how Claude decides whether to load your skill. Get this right or the skill is useless.

Minimal required format:
```yaml
---
name: your-skill-name
description: What it does. Use when user asks to [specific phrases].
---
```

### R-26: Field requirements
**name** (required):
- kebab-case only
- No spaces or capitals
- Must match folder name

**description** (required):
- MUST include BOTH: what the skill does AND when to use it (trigger conditions)
- Under 1024 characters
- No XML tags (< or >)
- Include specific phrases users would actually say
- Mention file types if relevant

## How we hit this
- [ ] CI lint check validates: SKILL.md exists, name is kebab-case, folder matches name
- [ ] CI lint check validates: description contains both WHAT and WHEN
- [ ] CI lint check validates: no README.md inside skill folders
- [ ] CI lint check validates: no XML tags in frontmatter
- [ ] PR template includes checklist for all technical requirements
