# Page 26: Troubleshooting - MCP Connection + Instructions Not Followed

## Rules for qdrant-os

### R-73: Debugging MCP connection issues
Symptom: Skill loads but MCP calls fail.

Checklist:
1. **Verify MCP server is connected**
   - Claude.ai: Settings > Extensions > Qdrant
   - Should show "Connected" status

2. **Check authentication**
   - API keys valid and not expired
   - Proper permissions/scopes granted

3. **Test MCP independently**
   - Ask Claude to call MCP directly without skill: "Use Qdrant MCP to list my collections"
   - If this fails, the issue is MCP, not the skill

4. **Verify tool names**
   - Skill references correct MCP tool names
   - Tool names are case-sensitive
   - Check against MCP server documentation

### R-74: Instructions not followed - common causes and fixes

**1. Instructions too verbose**
- Keep instructions concise
- Use bullet points and numbered lists
- Move detailed reference to separate files in references/

**2. Instructions buried**
- Put critical instructions at the TOP of the SKILL.md body
- Use `## Important` or `## Critical` headers
- Repeat key points if needed

**3. Ambiguous language**
BAD: "Make sure to validate things properly"
GOOD: "CRITICAL: Before recommending quantization, verify:
- Vector dimensions are known
- Current memory usage is measured
- Dataset size is confirmed"

**4. Model laziness**
Add explicit encouragement:
```markdown
## Performance Notes
- Take your time to do this thoroughly
- Quality is more important than speed
- Do not skip validation steps
```
Note: Adding this to USER prompts is more effective than in SKILL.md.

### R-75: Use scripts for critical validations
For critical checks, bundle a script that performs the validation programmatically rather than relying on language instructions. Code is deterministic; language interpretation is not.

Example: instead of "check if the collection has quantization enabled", write a script:
```python
# scripts/check_quantization.py
# Returns clear yes/no instead of relying on Claude to interpret
```

## How we hit this
- [ ] MCP connection issues documented in each external skill's Troubleshooting section
- [ ] Critical instructions appear at the TOP of SKILL.md body
- [ ] No ambiguous language in instructions (CI lint for vague words)
- [ ] Validation scripts used for deterministic checks where possible
