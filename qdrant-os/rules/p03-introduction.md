# Page 3: Introduction

## Rules for qdrant-os

### R-01: Skills are folders, not files
A skill is a set of instructions packaged as a simple folder. Every qdrant-os skill must be a folder containing at minimum a SKILL.md file.

### R-02: Teach once, benefit every time
Skills eliminate re-explaining. If a solution architect has answered the same question three times, it becomes a skill. No one should have to re-explain preferences, processes, or domain expertise in every conversation.

### R-03: Skills work with built-in capabilities
Skills work well with Claude's built-in capabilities like code execution and document creation. For MCP integrations, skills turn raw tool access into reliable, optimized workflows.

### R-04: Two paths, same spec
Whether building standalone skills (qdrant-os external) or MCP-enhanced skills (qdrant-os with Qdrant MCP server), both share the same technical requirements. The skill format is the same.

### R-05: 15-30 minute build time
A functional skill should be buildable in a single sitting, 15-30 minutes using the skill-creator. If a skill takes longer than that to write, it is too complex and should be split.

## How we hit this
- [ ] Every skill is a folder, not a loose markdown file
- [ ] Before writing a new skill, check: has this been explained 3+ times?
- [ ] Use skill-creator for first drafts to stay within 15-30 min target
- [ ] Both external and internal skills follow identical folder structure
