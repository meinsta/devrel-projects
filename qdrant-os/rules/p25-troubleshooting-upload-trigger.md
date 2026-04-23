# Page 25: Troubleshooting - Upload Issues + Trigger Issues

## Rules for qdrant-os

### R-69: Common upload errors and fixes

**"Could not find SKILL.md in uploaded folder"**
- Cause: File not named exactly SKILL.md
- Fix: Rename to SKILL.md (case-sensitive). Verify with `ls -la`.

**"Invalid frontmatter"**
- Cause: YAML formatting issue
- Common mistakes:
  - Missing `---` delimiters
  - Unclosed quotes in description
- Always use the correct format:
```yaml
---
name: my-skill
description: Does things
---
```

**"Invalid skill name"**
- Cause: Name has spaces or capitals
- Fix: Use kebab-case only. `my-cool-skill` not `My Cool Skill`.

### R-70: Debugging skills that don't trigger
Symptom: Skill never loads automatically.

Checklist:
- Is the description too generic? ("Helps with Qdrant" will not work)
- Does it include trigger phrases users would actually say?
- Does it mention relevant technical terms?

**Debugging approach:** Ask Claude directly: "When would you use the [skill name] skill?" Claude will quote the description back. Adjust based on what's missing.

### R-71: Debugging skills that trigger too often
Symptom: Skill loads for unrelated queries.

Solutions:
1. **Add negative triggers**: "Do NOT use for general Qdrant setup or installation"
2. **Be more specific**: "Processes Qdrant memory diagnostics" not "Processes Qdrant issues"
3. **Clarify scope**: "Use specifically for memory and RAM issues, not for query performance"

### R-72: Pre-merge trigger validation
Before merging any skill:
1. Test that it triggers on all should-trigger cases
2. Test that it does NOT trigger on should-not-trigger cases
3. Ask Claude "when would you use this skill?" and verify the answer matches intent

## How we hit this
- [ ] CI validates SKILL.md file naming and YAML format
- [ ] Every PR includes "asked Claude when it would use this skill" screenshot or log
- [ ] Every skill has negative triggers in the description
- [ ] Trigger tests run before merge
