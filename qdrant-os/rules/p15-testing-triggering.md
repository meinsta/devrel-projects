# Page 15: Testing and Iteration - Triggering Tests

## Rules for qdrant-os

### R-41: Three levels of testing rigor
Choose based on skill visibility:
1. **Manual testing in Claude.ai** - run queries, observe behavior (minimum for all skills)
2. **Scripted testing in Claude Code** - automate test cases for repeatable validation (required for external skills)
3. **Programmatic testing via skills API** - evaluation suites against defined test sets (required before v1.0)

Internal skills used by a small team: level 1 is sufficient.
External skills deployed to Qdrant users: levels 1-3 are required.

### R-42: Iterate on a single task before expanding
The most effective approach: iterate on a single challenging task until Claude succeeds, then extract the winning approach into the skill. This provides faster signal than broad testing. Once you have a working foundation, expand to multiple test cases.

### R-43: Every skill has triggering tests
Every skill must include test cases covering three areas:

1. **Should trigger on obvious tasks**
2. **Should trigger on paraphrased requests**
3. **Should NOT trigger on unrelated topics**

### R-44: Triggering test format for qdrant-os
Every skill must include a `triggers.json` file:
```json
{
  "skill": "qdrant-memory-usage",
  "should_trigger": [
    "my qdrant instance is eating 32GB of RAM",
    "how to reduce memory in qdrant",
    "qdrant OOM killed after bulk upload",
    "collection using way too much memory"
  ],
  "should_not_trigger": [
    "how to install qdrant",
    "what embedding model should I use",
    "qdrant vs pinecone comparison",
    "help me write python code"
  ]
}
```

Minimum: 4 positive cases, 4 negative cases per skill.

## How we hit this
- [ ] Every skill folder contains a `triggers.json`
- [ ] Minimum 4 should-trigger and 4 should-not-trigger cases
- [ ] External skills tested at all 3 levels before merge
- [ ] New skills start with 1 hard task, iterate until it works, then expand
