# Page 32: Complete Skill Examples (Reference C)

## Rules for qdrant-os

### R-93: Study reference implementations before building
Before building qdrant-os skills, every contributor must review:
- Document Skills (PDF, DOCX, PPTX, XLSX creation) - for structure patterns
- Example Skills (various workflow patterns) - for decision tree patterns
- Partner Skills Directory (Asana, Atlassian, Canva, Figma, Sentry, Zapier) - for MCP enhancement patterns

### R-94: Clone, modify, don't start from scratch
These repositories include production-ready skills. Clone them, modify for Qdrant use cases, use them as templates. Do NOT start from a blank file.

The workflow for building a new qdrant-os skill:
1. Find the closest matching pattern from the reference implementations
2. Clone it as a starting point
3. Use skill-creator to adapt it for the Qdrant use case
4. Refine manually to enforce the when/why structure
5. Run through the full checklist (p30)

### R-95: Sentry skill is our primary external reference
The sentry-code-review skill pattern is closest to what qdrant-os external skills should look like:
- Coordinates multiple MCP calls in sequence
- Embeds domain expertise
- Provides context users would otherwise need to specify
- Handles errors for common MCP issues

Study this skill first. Then adapt the pattern for Qdrant problem-solving workflows.

## How we hit this
- [ ] Every contributor reviews 3+ reference skills before writing their first skill
- [ ] New skills start from a cloned template, never a blank file
- [ ] CONTRIBUTING.md links to all reference implementations
- [ ] Sentry skill pattern explicitly called out as the model for external skills
