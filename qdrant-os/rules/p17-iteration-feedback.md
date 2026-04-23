# Page 17: Iteration Based on Feedback

## Rules for qdrant-os

### R-49: Skills are living documents, plan to iterate
No skill ships as a final version. Every skill will need iteration based on real-world feedback.

### R-50: Recognize undertriggering signals
Your skill is undertriggering if:
- Skill doesn't load when it should
- Users are manually enabling it
- Support questions about when to use it keep coming

**Fix:** Add more detail and nuance to the description. Include keywords, especially for technical terms. If users say "OOM" but your description only says "memory usage", add "OOM".

### R-51: Recognize overtriggering signals
Your skill is overtriggering if:
- Skill loads for irrelevant queries
- Users are disabling it
- Confusion about what the skill is for

**Fix:** Add negative triggers. Be more specific about scope:
```yaml
description: ... Do NOT use for general Qdrant setup,
  installation questions, or embedding model selection.
```

### R-52: Recognize execution issues
Your skill has execution issues if:
- Inconsistent results across runs
- API/MCP call failures
- Users need to correct Claude's behavior

**Fix:** Improve instructions, add error handling, make instructions more specific and actionable.

### R-53: Feedback loop for qdrant-os
Every skill must have a feedback mechanism:
1. Track which support questions still come in after skill deployment
2. If a question should have been handled by a skill but wasn't: undertriggering
3. If users complain a skill activated when it shouldn't have: overtriggering
4. If users say the skill gave wrong advice: execution issue

Update the skill within 1 week of receiving actionable feedback.

## How we hit this
- [ ] Monthly review of support tickets vs deployed skills
- [ ] Description updated within 1 week of confirmed undertriggering
- [ ] Negative triggers added within 1 week of confirmed overtriggering
- [ ] Execution issues trigger a new functional test case before the fix
