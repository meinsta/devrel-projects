# Page 29: Resources and References

## Rules for qdrant-os

### R-80: Use official resources as the foundation
Build skills referencing these official sources:

**Anthropic Resources:**
- Best Practices Guide
- Skills Documentation
- API Reference
- MCP Documentation

**Reference implementations:**
- GitHub: anthropics/skills (Anthropic-created skills to study and customize)
- Partner Skills Directory (Asana, Atlassian, Canva, Figma, Sentry, Zapier patterns)

### R-81: Use skill-creator for creation and validation
Two uses:
1. **Creating**: "Help me build a skill using skill-creator" - generates from natural language
2. **Validating**: "Review this skill and suggest improvements" - flags issues and recommends fixes

Use skill-creator for EVERY first draft. Then refine manually.

### R-82: Study partner skills for patterns
Before building qdrant-os skills, study how Sentry, Figma, Asana, and others built their skills. These are the patterns that work in production at scale. Clone them, modify for Qdrant use cases.

The Sentry code-review skill is particularly relevant: it coordinates MCP calls, embeds domain expertise, and handles errors. This is the closest pattern to what qdrant-os external skills should look like.

### R-83: Community support channels
- Technical questions: Claude Developers Discord
- Bug reports: GitHub Issues at anthropics/skills/issues
- Include: skill name, error message, steps to reproduce

## How we hit this
- [ ] Every contributor reviews at least 2 partner skills before writing their first skill
- [ ] skill-creator used for every first draft
- [ ] skill-creator validation run before every PR
- [ ] Sentry skill pattern studied as primary reference for external qdrant-os skills
