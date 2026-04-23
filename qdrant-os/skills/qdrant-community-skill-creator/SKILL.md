---
name: qdrant-community-skill-creator
description: Guides developers through building community Qdrant skills
  that embed domain knowledge into Claude. Use when someone wants to
  "create a community qdrant skill", "build an external skill for qdrant",
  "make a qdrant skill for the community", "build a public qdrant skill",
  or asks how to "create a skill for qdrant memory issues for developers".
  Also trigger when someone says "I want to build an open source qdrant
  skill" or "help me create a qdrant skill for public use". Do NOT use for
  internal SA skills, general non-Qdrant skill creation, or Python project
  skills unrelated to Qdrant.
license: Apache-2.0
metadata:
  author: thierry
  version: 2.0.0
  category: engineering
  tags: [skill-creator, community, external, templates]
---

# Community Qdrant Skill Creator

A skill for creating public/community Qdrant skills and iteratively improving them.

At a high level, the process goes like this:

- Check whether the skill needs to exist (R-16 check)
- Identify what Claude gets wrong about Qdrant, write a draft using the external template
- Create test prompts and run Claude with and without the skill
- Evaluate results: qualitative review in the branded viewer, quantitative benchmarks
- Improve the skill based on feedback
- Repeat until satisfied
- Optimize the description for better triggering accuracy

Your job is to figure out where the user is in this process and help them progress. Maybe they want to create a new skill from scratch. Maybe they already have a draft and want to run evals. Be flexible.

## The R-16 check: does this skill need to exist?

Before building any skill, answer this question:

**"What does this teach Claude that it currently gets wrong about Qdrant?"**

If Claude already gives correct answers on this topic, you do not need a skill. You need a prompt.

Good answers:
- "Claude says Qdrant only supports float32 and binary quantization"
- "Claude recommends full disk storage for real-time workloads"
- "Claude does not know about 2-bit and 4-bit quantization options"
- "Claude gives wrong units for memmap_threshold"

Bad answers:
- "How to use the Qdrant Python client" (Claude already knows this)
- "What is cosine similarity" (general knowledge)
- "Qdrant collection creation API" (Claude knows the API)

## Creating a Qdrant community skill

### Step 1: Identify what Claude gets wrong

This is the value source for community skills. Test Claude without any skill active:
1. Ask about the topic you want to cover
2. Note every incorrect or incomplete answer
3. Note every missing option or outdated information
4. These corrections become your skill's core content

Example findings:
```
- Claude says Qdrant only supports scalar and binary quantization
  CORRECTION: Qdrant supports 1-bit, 2-bit, 4-bit, and 8-bit
- Claude says memmap_threshold is in kilobytes
  CORRECTION: It is measured in number of vectors (KB of segment size)
```

### Step 2: Choose the skill pattern

Community skills follow the router pattern with conditional reference loading. Load `references/external-skill-template.md` for the skeleton.

Key sections:
1. **Things Claude gets wrong** (corrections from Step 1)
2. **Symptom routing table** (symptom -> reference file)
3. **Decision tree** with concrete thresholds
4. **Do NOT recommend** (anti-patterns)
5. **Troubleshooting** (minimum 2 error cases)

### Step 3: Write with public references only

Community skills must reference only public Qdrant documentation. No internal pricing data, customer names, or SA conversations.

Use these doc base URLs:
- Concepts: `https://qdrant.tech/documentation/concepts/`
- Guides: `https://qdrant.tech/documentation/guides/`
- Tutorials: `https://qdrant.tech/documentation/tutorials/`

Every solution should link to a specific doc page.

### Step 4: Write the SKILL.md

Based on the template and corrections, fill in these components:

- **name**: Skill identifier (kebab-case, matches folder name)
- **description**: When to trigger, what it does. Make descriptions a bit "pushy" to combat undertriggering. Example: instead of "Helps with Qdrant memory issues", write "Use when a user reports OOM crashes, high memory usage, needs to fit more vectors in RAM, asks about quantization options, or wants to reduce Qdrant memory footprint. Do NOT use for general Qdrant API questions or search accuracy tuning."
- **the rest of the skill body**

#### Skill structure

```
skill-name/
├── SKILL.md (required)
│   ├── YAML frontmatter (name, description required)
│   └── Markdown instructions
└── Bundled Resources (optional)
    ├── scripts/    - Executable code
    ├── references/ - Docs loaded into context as needed
    └── assets/     - Files used in output
```

#### Progressive disclosure

Skills use a three-level loading system:
1. **Metadata** (name + description): Always in context (~100 words)
2. **SKILL.md body**: In context whenever skill triggers (<500 lines ideal)
3. **Bundled resources**: As needed (unlimited, scripts can execute without loading)

Keep SKILL.md under 500 lines. Move "how" content to references/. For large reference files (>300 lines), include a table of contents.

### Step 5: Validate and build eval set

1. Run `python scripts/validate.py` to check all rules
2. Load `references/rules-checklist.md` and verify every item passes
3. Open the eval review page at `assets/eval_review.html`
4. Add 4+ positive trigger queries using real developer language
5. Add 4+ negative trigger queries covering adjacent topics
6. Export the JSON and save as `triggers.json`

Positive triggers should sound like real developers:
- "qdrant keeps getting OOM killed on our k8s cluster"
- "switched to disk but latency went from 15ms to 3 seconds"

Negative triggers should cover adjacent territory:
- "how do I install qdrant on kubernetes"
- "what embedding model should I use"

Save test cases to `evals/evals.json`. Don't write assertions yet, just the prompts.

```json
{
  "skill_name": "example-skill",
  "evals": [
    {
      "id": 1,
      "prompt": "User's task prompt",
      "expected_output": "Description of expected result",
      "files": []
    }
  ]
}
```

See `references/schemas.md` for the full schema.

## Running and evaluating test cases

This section is one continuous sequence. Put results in `<skill-name>-workspace/` as a sibling to the skill directory. Organize results by iteration (`iteration-1/`, `iteration-2/`, etc.) and within that, each test case gets a directory (`eval-0/`, `eval-1/`, etc.).

### Step 1: Spawn all runs (with-skill AND baseline) in the same turn

For each test case, spawn two subagents in the same turn. Don't spawn with-skill first and baselines later. Launch everything at once.

**With-skill run:**

```
Execute this task:
- Skill path: <path-to-skill>
- Task: <eval prompt>
- Input files: <eval files if any, or "none">
- Save outputs to: <workspace>/iteration-<N>/eval-<ID>/with_skill/outputs/
- Outputs to save: <what the user cares about>
```

**Baseline run** (same prompt, no skill):
- **Creating a new skill**: no skill at all. Save to `without_skill/outputs/`.
- **Improving an existing skill**: snapshot the old version, point baseline at it. Save to `old_skill/outputs/`.

Write an `eval_metadata.json` for each test case with a descriptive name. If this iteration uses new or modified eval prompts, create these files fresh.

```json
{
  "eval_id": 0,
  "eval_name": "descriptive-name-here",
  "prompt": "The user's task prompt",
  "assertions": []
}
```

### Step 2: While runs are in progress, draft assertions

Don't wait for runs to finish. Draft quantitative assertions and explain them to the user. Good assertions are objectively verifiable and have descriptive names.

Update the `eval_metadata.json` files and `evals/evals.json` with assertions once drafted.

### Step 3: As runs complete, capture timing data

When each subagent task completes, the notification contains `total_tokens` and `duration_ms`. Save immediately to `timing.json` in the run directory:

```json
{
  "total_tokens": 84852,
  "duration_ms": 23332,
  "total_duration_seconds": 23.3
}
```

### Step 4: Grade, aggregate, and launch the viewer

Once all runs are done:

1. **Grade each run** using the Qdrant grader. Read `agents/qdrant-grader.md` and evaluate each assertion against the outputs. The grader runs standard assertion checks AND Qdrant domain checks (D-1 through D-8: corrections section, symptom routing, decision tree thresholds, anti-patterns, doc links, progressive disclosure, no internal data, public doc links). Save results to `grading.json` in each run directory. The grading.json expectations array must use fields `text`, `passed`, and `evidence`.

   For assertions that can be checked programmatically, write and run a script rather than eyeballing it.

2. **Aggregate into benchmark**:
   ```bash
   python -m scripts.aggregate_benchmark <workspace>/iteration-N --skill-name <name>
   ```
   This produces `benchmark.json` and `benchmark.md` with pass_rate, time, and tokens for each configuration.

3. **Do an analyst pass** using `agents/analyzer.md`. Surface patterns the aggregate stats might hide: non-discriminating assertions, high-variance evals, time/token tradeoffs.

4. **Launch the viewer** with both qualitative outputs and quantitative data:
   ```bash
   nohup python eval-viewer/generate_review.py \
     <workspace>/iteration-N \
     --skill-name "my-skill" \
     --benchmark <workspace>/iteration-N/benchmark.json \
     > /dev/null 2>&1 &
   VIEWER_PID=$!
   ```
   For iteration 2+, also pass `--previous-workspace <workspace>/iteration-<N-1>`.

   **Headless environments:** Use `--static <output_path>` to write standalone HTML instead of starting a server.

5. **Tell the user** something like: "I've opened the results in your browser. There are two tabs: 'Outputs' lets you click through each test case and leave feedback, 'Benchmark' shows the quantitative comparison. When you're done, come back here and let me know."

### What the user sees in the viewer

The "Outputs" tab shows one test case at a time:
- **Prompt**: the task that was given
- **Output**: the files the skill produced, rendered inline
- **Previous Output** (iteration 2+): collapsed section showing last iteration
- **Formal Grades**: collapsed section with assertion pass/fail AND Qdrant domain checks
- **Feedback**: textbox that auto-saves
- **Previous Feedback** (iteration 2+): comments from last time

The "Benchmark" tab shows summary stats and per-eval breakdowns.

Navigation is via prev/next buttons or arrow keys. "Submit All Reviews" saves everything to `feedback.json`.

### Step 5: Read the feedback

When the user is done, read `feedback.json`. Empty feedback means fine. Focus improvements on test cases with specific complaints.

Kill the viewer when done: `kill $VIEWER_PID 2>/dev/null`

## Improving the skill

### How to think about improvements

1. **Generalize from the feedback.** Don't put in fiddly overfitty changes. The skill will be used across many different prompts, not just the test examples.

2. **Keep the prompt lean.** Remove things that aren't pulling their weight. Read the transcripts, not just the final outputs.

3. **Explain the why.** Explain the reasoning behind instructions. If you find yourself writing ALWAYS or NEVER in all caps, reframe and explain why.

4. **Look for repeated work across test cases.** If all test runs independently wrote similar helper scripts, the skill should bundle that script. Write it once, put it in `scripts/`.

### The iteration loop

After improving the skill:

1. Apply improvements to the skill
2. Rerun all test cases into a new `iteration-<N+1>/` directory, including baselines
3. Launch the reviewer with `--previous-workspace` pointing at the previous iteration
4. Wait for user review
5. Read new feedback, improve again, repeat

Keep going until the user is happy, feedback is all empty, or you're not making meaningful progress.

## Advanced: Blind comparison

For rigorous comparison between two skill versions, read `agents/comparator.md` and `agents/analyzer.md`. The comparator judges quality blindly (with Qdrant domain rubric). The analyzer explains why the winner won (with Qdrant-specific improvement categories: decision_tree, doc_links, corrections, symptom_routing).

This is optional and most users won't need it.

## Description optimization

After the skill is solid, optimize the description for triggering accuracy.

### Step 1: Generate trigger eval queries

Create 20 eval queries (10 should-trigger, 10 should-not-trigger). Save as JSON:

```json
[
  {"query": "the user prompt", "should_trigger": true},
  {"query": "another prompt", "should_trigger": false}
]
```

Queries must be realistic with concrete detail: file paths, customer context, specific numbers, company names. Not abstract requests.

For **should-trigger** queries (8-10): different phrasings of the same intent, some formal, some casual. Include cases where the user doesn't name the skill but clearly needs it.

For **should-not-trigger** queries (8-10): near-misses that share keywords but need something different. Not obviously irrelevant queries.

### Step 2: Review with user

Present via the HTML template at `assets/eval_review.html`. Replace placeholders, write to a temp file, and open it. The user edits queries, toggles should-trigger, then clicks "Export Eval Set".

### Step 3: Run the optimization loop

```bash
python -m scripts.run_loop \
  --eval-set <path-to-trigger-eval.json> \
  --skill-path <path-to-skill> \
  --model <model-id-powering-this-session> \
  --max-iterations 5 \
  --verbose
```

This splits 60/40 train/test, evaluates the description (3 runs per query), calls Claude with extended thinking to improve, and iterates up to 5 times. It opens an HTML report and returns JSON with `best_description`.

### Step 4: Apply the result

Take `best_description` from the output and update the skill's SKILL.md frontmatter. Show before/after and report scores.

## Do NOT recommend

- Do NOT include internal customer data, SA conversations, or pricing formulas
- Do NOT create skills for knowledge Claude already has
- Do NOT use vague descriptions. Include specific trigger phrases.
- Do NOT put implementation details in SKILL.md body. Use references/.
- Do NOT skip the R-16 check.

## Troubleshooting

### "Skill triggers on general Qdrant questions, not just my topic"
**Cause:** Description is too broad. It matches on "qdrant" instead
of the specific symptom category.
**Fix:** Narrow the description to specific symptoms. Add "Do NOT
use for" phrases covering adjacent Qdrant topics. Example: a memory
skill should exclude "search accuracy tuning" and "API scripting".

### "Skill output is no better than vanilla Claude"
**Cause:** The corrections section is empty or trivial. The skill
does not add domain knowledge Claude lacks.
**Fix:** Go back to Step 1. Test Claude without the skill and
document specific mistakes. Those corrections are your value.

### "References are too long, skill hits context limits"
**Cause:** Reference files contain full documentation instead of
curated decision guidance.
**Fix:** References should contain "when and why", not full API docs.
Link to qdrant.tech for the "how". Keep each reference under 1,000 words.

## Reference files

The agents/ directory contains instructions for specialized subagents:

- `agents/qdrant-grader.md`: Evaluate assertions + Qdrant domain checks (D-1 through D-8)
- `agents/comparator.md`: Blind A/B comparison with Qdrant domain rubric
- `agents/analyzer.md`: Post-hoc analysis with Qdrant improvement categories

The references/ directory has additional documentation:
- `references/schemas.md`: JSON structures for evals.json, grading.json, benchmark.json, etc.
- `references/external-skill-template.md`: Full skeleton for community skills
- `references/rules-checklist.md`: Validation checklist
- `references/examples.md`: Example skill patterns
