# Page 9: Define Success Criteria

## Rules for qdrant-os

### R-18: Every skill has quantitative success metrics
Track these for every skill:

1. **Skill triggers on 90% of relevant queries**
   - How to measure: Run 10-20 test queries that should trigger the skill
   - Track auto-trigger vs. manual invocation rate
   - Target: >90%

2. **Completes workflow in X tool calls**
   - How to measure: Compare same task with and without skill enabled
   - Count tool calls and total tokens consumed
   - The skill should REDUCE both numbers

3. **0 failed API calls per workflow**
   - How to measure: Monitor MCP server logs during test runs
   - Track retry rates and error codes
   - Target: zero failures

### R-19: Every skill has qualitative success metrics
Assess these during testing and beta usage:

1. **Users don't need to prompt Claude about next steps**
   - During testing, count how often you need to redirect or clarify
   - Ask beta users for feedback

2. **Workflows complete without user correction**
   - Run same request 3-5 times
   - Compare outputs for structural consistency and quality

3. **Consistent results across sessions**
   - Can a new user accomplish the task on first try with minimal guidance?

### R-20: Metrics are aspirational targets, not hard gates
These are rough benchmarks. Accept that there will be a vibes-based element. But track the numbers anyway. Without numbers you cannot improve.

## How we hit this
- [ ] Every skill has a `triggers.json` with 10-20 test queries
- [ ] Eval pipeline runs trigger accuracy on every PR
- [ ] Performance comparison (with/without skill) documented for each skill
- [ ] Qualitative feedback collected from at least 2 users per skill before v1.0
