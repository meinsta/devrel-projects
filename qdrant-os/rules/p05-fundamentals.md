# Page 5: Fundamentals - Structure and Design Principles

## Rules for qdrant-os

### R-06: Required folder contents
Every skill folder must contain:
- `SKILL.md` (required): Instructions in Markdown with YAML frontmatter
- `scripts/` (optional): Executable code (Python, Bash, etc.)
- `references/` (optional): Documentation loaded as needed
- `assets/` (optional): Templates, fonts, icons used in output

### R-07: Progressive disclosure is mandatory (three levels)
Skills MUST use the three-level progressive disclosure system:
1. **First level (YAML frontmatter)**: Always loaded in Claude's system prompt. Just enough info for Claude to know WHEN the skill should activate. This is the "when" layer.
2. **Second level (SKILL.md body)**: Loaded when Claude thinks the skill is relevant. Contains the full decision tree and guidance. This is the "why" layer.
3. **Third level (references/)**: Additional files Claude navigates only as needed. This is the "how" layer that links back to Qdrant docs.

This maps directly to our core principle: frontmatter = when, body = why, references = how.

### R-08: Composability
Skills must work well alongside other skills. Never assume your skill is the only one loaded. Do not use generic trigger phrases that would conflict with other skills.

### R-09: Portability
Skills must work identically across Claude.ai, Claude Code, and the API without modification. Do not rely on environment-specific features unless noted in the `compatibility` field.

### R-10: MCP = kitchen, Skills = recipes
For qdrant-os: The Qdrant MCP server provides connectivity (tools, data access). Skills provide the knowledge (when to use which tool, best practices, decision trees). Skills are NOT a replacement for the MCP server. They are the knowledge layer on top.

## How we hit this
- [ ] Every skill has exactly these levels: frontmatter (when), body (why), references/ (how)
- [ ] PR review checks: does the frontmatter only contain trigger info, NOT full instructions?
- [ ] No skill assumes it is the only one active
- [ ] Every skill tested on Claude.ai AND Claude Code before merge
