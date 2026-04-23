# qdrant-os Rules Index

95 rules extracted from "The Complete Guide to Building Skills for Claude" (33 pages).
Each rule is tagged with how qdrant-os must hit it.

## Files by Chapter

### Introduction (p3)
- [p03-introduction.md](p03-introduction.md) - R-01 to R-05
  Skills are folders. Teach once. 15-30 min build time.

### Chapter 1: Fundamentals (p5-6)
- [p05-fundamentals.md](p05-fundamentals.md) - R-06 to R-10
  Folder structure. Progressive disclosure (3 levels). Composability. Portability.
- [p06-mcp-integration.md](p06-mcp-integration.md) - R-11 to R-13
  MCP = connectivity, Skills = knowledge. Skills solve the "now what?" problem.

### Chapter 2: Planning and Design (p8-13)
- [p08-planning-use-cases.md](p08-planning-use-cases.md) - R-14 to R-17
  Start with use cases. Four questions. qdrant-os is Category 3 (MCP Enhancement).
- [p09-success-criteria.md](p09-success-criteria.md) - R-18 to R-20
  Quantitative metrics (90% trigger, tool call reduction, 0 failures). Qualitative metrics.
- [p10-technical-requirements.md](p10-technical-requirements.md) - R-21 to R-26
  File structure. SKILL.md naming. Folder naming. No README. YAML frontmatter.
- [p11-writing-descriptions.md](p11-writing-descriptions.md) - R-27 to R-31
  Description formula. Good/bad examples. Security restrictions.
- [p12-writing-instructions.md](p12-writing-instructions.md) - R-32 to R-35
  SKILL.md body template. Decision tree format. Realistic examples. Troubleshooting required.
- [p13-best-practices-instructions.md](p13-best-practices-instructions.md) - R-36 to R-40
  Be specific. Error handling. Reference linking. Progressive disclosure. How lives in references.

### Chapter 3: Testing and Iteration (p15-17)
- [p15-testing-triggering.md](p15-testing-triggering.md) - R-41 to R-44
  Three testing levels. Iterate single task first. Triggering test format.
- [p16-functional-performance-tests.md](p16-functional-performance-tests.md) - R-45 to R-48
  Functional tests. Performance comparison. skill-creator usage.
- [p17-iteration-feedback.md](p17-iteration-feedback.md) - R-49 to R-53
  Living documents. Undertriggering. Overtriggering. Execution issues. Feedback loop.

### Chapter 4: Distribution and Sharing (p19-20)
- [p19-distribution.md](p19-distribution.md) - R-54 to R-58
  Distribution channels. Open standard. API vs Claude.ai. Code Execution beta.
- [p20-positioning.md](p20-positioning.md) - R-59 to R-62
  GitHub structure. Installation guide. Outcomes not features. MCP + skills story.

### Chapter 5: Patterns and Troubleshooting (p22-27)
- [p22-patterns-problem-first.md](p22-patterns-problem-first.md) - R-63 to R-64
  Problem-first vs tool-first. Sequential workflow pattern.
- [p23-patterns-multi-mcp-iterative.md](p23-patterns-multi-mcp-iterative.md) - R-65 to R-66
  Multi-MCP coordination. Iterative refinement.
- [p24-patterns-context-aware-domain.md](p24-patterns-context-aware-domain.md) - R-67 to R-68
  Context-aware tool selection. Domain-specific intelligence (our PRIMARY pattern).
- [p25-troubleshooting-upload-trigger.md](p25-troubleshooting-upload-trigger.md) - R-69 to R-72
  Upload errors. Trigger debugging. Pre-merge validation.
- [p26-troubleshooting-mcp-instructions.md](p26-troubleshooting-mcp-instructions.md) - R-73 to R-75
  MCP connection issues. Instructions not followed. Scripts for validation.
- [p27-large-context.md](p27-large-context.md) - R-76 to R-79
  Size limits. 5,000 word max. Simultaneous skill limits. Progressive disclosure prevents bloat.

### Chapter 6: Resources and References (p29-32)
- [p29-resources.md](p29-resources.md) - R-80 to R-83
  Official resources. skill-creator. Partner skills. Community support.
- [p30-quick-checklist.md](p30-quick-checklist.md) - R-84 to R-88
  Pre-build, during-build, pre-upload, post-upload checklists.
- [p31-yaml-reference.md](p31-yaml-reference.md) - R-89 to R-92
  Required fields. Full template. Field-by-field rules. Security.
- [p32-complete-examples.md](p32-complete-examples.md) - R-93 to R-95
  Reference implementations. Clone-modify workflow. Sentry as primary reference.

## Top 10 Rules for qdrant-os (the ones that matter most)

1. **R-07**: Progressive disclosure maps to our when/why/how principle
2. **R-16**: If no domain knowledge to embed, it is NOT a skill
3. **R-25**: YAML frontmatter is the most important part (triggers)
4. **R-28**: Good descriptions include trigger phrases in quotes
5. **R-40**: The "how" lives in references, not the body
6. **R-44**: Every skill has triggers.json with positive AND negative cases
7. **R-51**: Add negative triggers to prevent overtriggering
8. **R-63**: qdrant-os external skills are problem-first
9. **R-68**: Domain-specific intelligence is our primary pattern
10. **R-77**: SKILL.md under 5,000 words (hard limit)
