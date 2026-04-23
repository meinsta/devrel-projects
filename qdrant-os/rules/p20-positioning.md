# Page 20: Positioning Your Skill

## Rules for qdrant-os

### R-59: GitHub repo structure for distribution
Start by hosting on GitHub with:
1. Public repo for open-source skills
2. Clear README with installation instructions (repo-level, NOT inside skill folders)
3. Example usage and screenshots
4. Link from MCP documentation to skills
5. Quick-start guide explaining why using MCP + skills together is valuable

### R-60: Installation guide template
Every repo must have a clear installation guide:
```markdown
## Installing qdrant-os skills

1. Download the skill:
   - Clone repo: `git clone https://github.com/qdrant/qdrant-os`
   - Or download ZIP from Releases

2. Install in Claude:
   - Open Claude.ai > Settings > Skills
   - Click "Upload skill"
   - Select the skill folder (zipped)

3. Enable the skill:
   - Toggle on the desired skill
   - Ensure Qdrant MCP server is connected (if applicable)

4. Test:
   - Ask Claude: "My qdrant instance is using too much memory"
```

### R-61: Focus on outcomes, not features
GOOD:
```
"The qdrant-memory-usage skill helps you diagnose and fix memory
issues in minutes, instead of spending hours reading docs and
guessing at configuration changes."
```

BAD:
```
"The qdrant-memory-usage skill is a folder containing YAML
frontmatter and Markdown instructions that reference Qdrant
documentation."
```

### R-62: Highlight the MCP + skills story
```
"The Qdrant MCP server gives Claude access to your collections
and cluster. Our skills teach Claude how to diagnose problems
and recommend the right configuration. Together, they enable
AI-powered database operations."
```

## How we hit this
- [ ] Repo README describes outcomes, not technical implementation
- [ ] Installation guide is copy-paste ready (tested by someone who didn't write it)
- [ ] MCP + skills value proposition stated clearly in README
- [ ] Screenshots or examples of skills in action included in README
