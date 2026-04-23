# Page 30: Quick Checklist (Reference A)

## Rules for qdrant-os

### R-84: Pre-build checklist
Before writing any skill, confirm:
- [ ] Identified 2-3 concrete use cases
- [ ] Tools identified (built-in or MCP)
- [ ] Reviewed this guide and example skills
- [ ] Planned folder structure

### R-85: During-development checklist
While building the skill, verify:
- [ ] Folder named in kebab-case
- [ ] SKILL.md file exists (exact spelling)
- [ ] YAML frontmatter has `---` delimiters
- [ ] `name` field: kebab-case, no spaces, no capitals
- [ ] `description` includes WHAT and WHEN
- [ ] No XML tags (< >) anywhere
- [ ] Instructions are clear and actionable
- [ ] Error handling included
- [ ] Examples provided
- [ ] References clearly linked

### R-86: Pre-upload checklist
Before merging or uploading:
- [ ] Tested triggering on obvious tasks
- [ ] Tested triggering on paraphrased requests
- [ ] Verified doesn't trigger on unrelated topics
- [ ] Functional tests pass
- [ ] Tool integration works (if applicable)
- [ ] Compressed as .zip file (for Claude.ai upload)

### R-87: Post-upload checklist
After deployment:
- [ ] Test in real conversations
- [ ] Monitor for under/over-triggering
- [ ] Collect user feedback
- [ ] Iterate on description and instructions
- [ ] Update version in metadata

### R-88: qdrant-os additional checks
On top of the standard checklist:
- [ ] Skill starts with a situation/problem, NOT a feature name
- [ ] Decision tree uses concrete thresholds, not vague guidance
- [ ] All doc links in references/ resolve to real Qdrant documentation
- [ ] triggers.json included with 4+ positive and 4+ negative cases
- [ ] Before/after performance comparison documented

## How we hit this
- [ ] PR template includes this full checklist
- [ ] CI automates the checks that can be automated (naming, format, word count)
- [ ] Manual review covers the checks that cannot be automated (quality, clarity)
- [ ] No PR merges without all checkboxes checked
