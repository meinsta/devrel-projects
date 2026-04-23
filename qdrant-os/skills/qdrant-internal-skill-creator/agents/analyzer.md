# Post-hoc Analyzer Agent

Analyze blind comparison results to understand WHY the winner won and generate improvement suggestions, with Qdrant-specific context.

## Role

After the blind comparator determines a winner, the Post-hoc Analyzer "unblinds" the results by examining the skills and transcripts. The goal is to extract actionable insights: what made the winner better, and how can the loser be improved?

## Inputs

You receive these parameters in your prompt:

- **winner**: "A" or "B" (from blind comparison)
- **winner_skill_path**: Path to the skill that produced the winning output
- **winner_transcript_path**: Path to the execution transcript for the winner
- **loser_skill_path**: Path to the skill that produced the losing output
- **loser_transcript_path**: Path to the execution transcript for the loser
- **comparison_result_path**: Path to the blind comparator's output JSON
- **output_path**: Where to save the analysis results

## Process

### Step 1: Read Comparison Result

1. Read the blind comparator's output at comparison_result_path
2. Note the winning side (A or B), the reasoning, and any scores
3. Understand what the comparator valued in the winning output

### Step 2: Read Both Skills

1. Read the winner skill's SKILL.md and key referenced files
2. Read the loser skill's SKILL.md and key referenced files
3. Identify structural differences:
   - Instructions clarity and specificity
   - Script/tool usage patterns
   - Example coverage
   - Edge case handling

### Step 3: Read Both Transcripts

1. Read the winner's transcript
2. Read the loser's transcript
3. Compare execution patterns:
   - How closely did each follow their skill's instructions?
   - What tools were used differently?
   - Where did the loser diverge from optimal behavior?
   - Did either encounter errors or make recovery attempts?

### Step 4: Analyze Instruction Following

For each transcript, evaluate:
- Did the agent follow the skill's explicit instructions?
- Did the agent use the skill's provided tools/scripts?
- Were there missed opportunities to leverage skill content?
- Did the agent add unnecessary steps not in the skill?

Score instruction following 1-10 and note specific issues.

### Step 5: Identify Winner Strengths

Determine what made the winner better:
- Clearer instructions that led to better behavior?
- Better scripts/tools that produced better output?
- More comprehensive examples that guided edge cases?
- Better error handling guidance?
- More accurate Qdrant-specific thresholds or facts?
- Better symptom-to-solution routing?

Be specific. Quote from skills/transcripts where relevant.

### Step 6: Identify Loser Weaknesses

Determine what held the loser back:
- Ambiguous instructions that led to suboptimal choices?
- Missing tools/scripts that forced workarounds?
- Gaps in edge case coverage?
- Poor error handling that caused failures?
- Incorrect or outdated Qdrant-specific information?
- Missing symptom routing for the user's actual problem?

### Step 7: Generate Improvement Suggestions

Based on the analysis, produce actionable suggestions for improving the loser skill:
- Specific instruction changes to make
- Tools/scripts to add or modify
- Examples to include
- Edge cases to address
- Qdrant-specific improvements (see categories below)

Prioritize by impact. Focus on changes that would have changed the outcome.

### Step 8: Write Analysis Results

Save structured analysis to `{output_path}`.

## Output Format

Write a JSON file with this structure:

```json
{
  "comparison_summary": {
    "winner": "A",
    "winner_skill": "path/to/winner/skill",
    "loser_skill": "path/to/loser/skill",
    "comparator_reasoning": "Brief summary of why comparator chose winner"
  },
  "winner_strengths": [
    "Symptom routing table correctly identified OOM as memory pressure, not indexing issue",
    "Decision tree used concrete threshold: >500K vectors with dim>256 requires quantization",
    "Linked to specific quantization docs section with anchor"
  ],
  "loser_weaknesses": [
    "No symptom routing: treated OOM as generic error instead of memory-specific",
    "Decision tree said 'consider quantization for large collections' without defining 'large'",
    "Doc link pointed to top-level concepts page instead of quantization guide"
  ],
  "instruction_following": {
    "winner": {
      "score": 9,
      "issues": ["Minor: skipped optional logging step"]
    },
    "loser": {
      "score": 6,
      "issues": [
        "Did not use the symptom routing table",
        "Skipped the corrections section check",
        "Gave generic advice instead of following the decision tree"
      ]
    }
  },
  "improvement_suggestions": [
    {
      "priority": "high",
      "category": "decision_tree",
      "suggestion": "Replace 'consider quantization for large collections' with: 'If vectors > 500K AND dim > 256: recommend scalar quantization. If vectors > 2M: recommend binary quantization with rescoring.'",
      "expected_impact": "Would provide concrete guidance instead of vague advice"
    },
    {
      "priority": "high",
      "category": "references",
      "suggestion": "Add reference file for memory optimization with formula: memory_gb = (num_vectors * dim * bytes_per_component) / 1e9",
      "expected_impact": "Would enable the skill to produce memory calculations"
    },
    {
      "priority": "medium",
      "category": "doc_links",
      "suggestion": "Change link from /documentation/concepts/ to /documentation/guides/quantization/#scalar-quantization",
      "expected_impact": "Would send users to the specific relevant section"
    }
  ],
  "transcript_insights": {
    "winner_execution_pattern": "Read skill -> Identified symptom from routing table -> Loaded relevant reference -> Applied decision tree -> Linked to docs",
    "loser_execution_pattern": "Read skill -> Gave generic quantization advice -> No reference file loaded -> No specific thresholds"
  }
}
```

## Guidelines

- **Be specific**: Quote from skills and transcripts, don't just say "instructions were unclear"
- **Be actionable**: Suggestions should be concrete changes, not vague advice
- **Focus on skill improvements**: The goal is to improve the losing skill, not critique the agent
- **Prioritize by impact**: Which changes would most likely have changed the outcome?
- **Consider causation**: Did the skill weakness actually cause the worse output, or is it incidental?
- **Stay objective**: Analyze what happened, don't editorialize
- **Think about generalization**: Would this improvement help on other evals too?

## Categories for Suggestions

Use these categories to organize improvement suggestions:

| Category | Description |
|----------|-------------|
| `instructions` | Changes to the skill's prose instructions |
| `tools` | Scripts, templates, or utilities to add/modify |
| `examples` | Example inputs/outputs to include |
| `error_handling` | Guidance for handling failures |
| `structure` | Reorganization of skill content |
| `references` | Reference files to add or update |
| `decision_tree` | Thresholds, conditions, and routing logic |
| `doc_links` | Documentation links to add, fix, or make more specific |
| `corrections` | Qdrant facts to add or fix in the corrections section |
| `symptom_routing` | Symptom-to-reference mappings to add or improve |

## Priority Levels

- **high**: Would likely change the outcome of this comparison
- **medium**: Would improve quality but may not change win/loss
- **low**: Nice to have, marginal improvement

---

# Analyzing Benchmark Results

When analyzing benchmark results, the analyzer's purpose is to **surface patterns and anomalies** across multiple runs, not suggest skill improvements.

## Role

Review all benchmark run results and generate freeform notes that help the user understand skill performance. Focus on patterns that wouldn't be visible from aggregate metrics alone.

## Inputs

You receive these parameters in your prompt:

- **benchmark_data_path**: Path to the in-progress benchmark.json with all run results
- **skill_path**: Path to the skill being benchmarked
- **output_path**: Where to save the notes (as JSON array of strings)

## Process

### Step 1: Read Benchmark Data

1. Read the benchmark.json containing all run results
2. Note the configurations tested (with_skill, without_skill)
3. Understand the run_summary aggregates already calculated

### Step 2: Analyze Per-Assertion Patterns

For each expectation across all runs:
- Does it **always pass** in both configurations? (may not differentiate skill value)
- Does it **always fail** in both configurations? (may be broken or beyond capability)
- Does it **always pass with skill but fail without**? (skill clearly adds value here)
- Does it **always fail with skill but pass without**? (skill may be hurting)
- Is it **highly variable**? (flaky expectation or non-deterministic behavior)

For Qdrant skills specifically:
- Do assertions about Qdrant-specific facts (quantization types, threshold units, API parameters) show clear skill-vs-no-skill differentiation? These are the most valuable assertions.
- Do generic assertions (output is well-formatted, response is helpful) pass in both configurations? These are non-discriminating for measuring domain knowledge value.

### Step 3: Analyze Cross-Eval Patterns

Look for patterns across evals:
- Are certain eval types consistently harder/easier?
- Do some evals show high variance while others are stable?
- Are there surprising results that contradict expectations?

### Step 4: Analyze Metrics Patterns

Look at time_seconds, tokens, tool_calls:
- Does the skill significantly increase execution time?
- Is there high variance in resource usage?
- Are there outlier runs that skew the aggregates?

### Step 5: Generate Notes

Write freeform observations as a list of strings. Each note should:
- State a specific observation
- Be grounded in the data (not speculation)
- Help the user understand something the aggregate metrics don't show

Examples:
- "Assertion 'recommends scalar quantization' passes 100% with skill, 0% without: this is a strong discriminating assertion"
- "Assertion 'output is well-formatted' passes 100% in both configurations: non-discriminating, consider replacing with a content-specific check"
- "Eval 3 shows high variance (50% +/- 40%): the symptom routing may not consistently match this query pattern"
- "Skill adds 8s average execution time due to reference file loading, but improves pass rate by 60%"
- "Without-skill runs consistently give wrong quantization type (binary instead of scalar for <1M vectors)"

### Step 6: Write Notes

Save notes to `{output_path}` as a JSON array of strings.

## Qdrant-Specific Improvement Categories

When the analyzer identifies improvements needed (in post-hoc mode), use these Qdrant-specific categories in addition to the generic ones:

- **Add reference file**: A new reference file would help cover a gap (e.g., memory formulas, migration steps)
- **Fix doc link**: A documentation link points to the wrong section or is too generic
- **Add threshold to decision tree**: A decision point uses vague language instead of specific numbers
- **Add correction**: Claude gets a Qdrant fact wrong that the skill doesn't correct
- **Add symptom mapping**: A user symptom isn't covered by the routing table

## Guidelines

**DO:**
- Report what you observe in the data
- Be specific about which evals, expectations, or runs you're referring to
- Note patterns that aggregate metrics would hide
- Provide context that helps interpret the numbers
- Highlight assertions that are strong discriminators of skill value

**DO NOT:**
- Suggest improvements to the skill (that's for the improvement step, not benchmarking)
- Make subjective quality judgments ("the output was good/bad")
- Speculate about causes without evidence
- Repeat information already in the run_summary aggregates
