# Page 27: Large Context Issues

## Rules for qdrant-os

### R-76: Keep skill content lean
Symptom: Skill seems slow or responses degraded.

Causes:
- Skill content too large
- Too many skills enabled simultaneously
- All content loaded instead of using progressive disclosure

### R-77: SKILL.md size limit
Keep SKILL.md under 5,000 words. This is a hard rule for qdrant-os.

If your skill exceeds 5,000 words:
1. Move detailed documentation to `references/`
2. Link to references instead of inlining content
3. Keep only the decision tree and core instructions in SKILL.md

### R-78: Limit simultaneous skills
If users have more than 20-50 skills enabled simultaneously, performance degrades.

For qdrant-os:
- External skills: recommend users enable only the skills relevant to their current task
- Consider "skill packs" for related capabilities (e.g., "qdrant-operations" pack includes memory, accuracy, and downtime skills)
- Internal skills: deploy only to relevant teams, not the entire org

### R-79: Progressive disclosure prevents context bloat
This is WHY progressive disclosure exists:
- Level 1 (frontmatter): always loaded, must be tiny (under 1024 chars)
- Level 2 (SKILL.md body): loaded only when triggered, must be under 5,000 words
- Level 3 (references/): loaded only when Claude navigates to them, can be as large as needed

If you put everything in the SKILL.md body, it all loads when triggered, wasting context. Move the "how" to references/ and let Claude pull it only when needed.

## How we hit this
- [ ] CI check: SKILL.md body under 5,000 words
- [ ] CI check: frontmatter description under 1024 characters
- [ ] Detailed how-to content lives in references/, not SKILL.md body
- [ ] README recommends enabling only relevant skills at a time
- [ ] Consider skill packs for related capabilities
