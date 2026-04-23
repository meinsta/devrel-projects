# Page 8: Planning and Design - Use Cases

## Rules for qdrant-os

### R-14: Start with 2-3 concrete use cases before writing anything
Before writing any skill, identify 2-3 concrete use cases the skill should enable. Define each with:
- **Use Case**: name
- **Trigger**: what the user says or what situation they're in
- **Steps**: the multi-step workflow
- **Result**: what "done" looks like

### R-15: Use case definition format
Every qdrant-os skill must have its use cases documented before writing begins:
```
Use Case: Diagnose high memory usage
Trigger: User says "qdrant using too much RAM" or "OOM killed"
Steps:
1. Check collection parameters
2. Identify memory source (vectors, HNSW, payload index)
3. Recommend quantization or mmap
4. Link to relevant docs
Result: User knows which component to tune and has a link to the guide
```

### R-16: Ask four questions before building
For every proposed skill:
1. What does the user want to accomplish?
2. What multi-step workflow does this require?
3. Which tools are needed (built-in or MCP)?
4. What domain knowledge or best practices should be embedded?

If question 4 has no answer (no domain knowledge to embed), it is NOT a skill. It is documentation.

### R-17: qdrant-os is Category 3 (MCP Enhancement)
Our external skills are primarily MCP Enhancement: workflow guidance that enhances the tool access the Qdrant MCP server provides. Key techniques:
- Coordinate multiple MCP calls in sequence
- Embed domain expertise (solution architect knowledge)
- Provide context users would otherwise need to specify
- Error handling for common MCP/Qdrant issues

Our internal skills are Category 2 (Workflow Automation): multi-step processes that benefit from consistent methodology.

## How we hit this
- [ ] Every skill PR includes a use-case definition block in the PR description
- [ ] No skill is written without answering all four questions first
- [ ] External skills are tagged as "mcp-enhancement" category
- [ ] Internal skills are tagged as "workflow-automation" category
