# Asteroid Research Proposal

Date: April 2, 2026

## Title

Asteroid: A model-agnostic retrieval layer for agentic search built on Qdrant

## Proposal In One Paragraph

Asteroid treats retrieval infrastructure as the main variable in search-agent
performance, not just the base model. The project combines a model-agnostic agent
harness with Qdrant-native retrieval tools, then measures what comes from the tool
layer, what comes from training, and which database primitives produce measurable
lift. The immediate goal is to turn the current prototype into a publishable evaluation
stack: a clean 4-tool baseline, a validated retrieval-subagent metric pipeline, and a
Qdrant-native ablation suite on top of that baseline. The longer-term goal is to show
that open models trained on richer retrieval tools can close meaningful ground on
retrieval-heavy benchmarks and outperform generic search stacks in structured
enterprise settings.

## Current Starting Point

The repository already supports the proposal:

- Best stored wiki retrieval result: `0.788 avg_reward` on 50 questions for a trained
  Qwen3-30B adapter.
- Stored `gpt-oss-20b` comparison on the same task: `0.636 avg_reward` on 50
  questions.
- Best stored FRAMES holdout result: `0.56` on a 20-question slice.
- BrowseComp is currently weak (`0.10-0.20` answer-found on stored holdout runs).
- Retrieval-subagent metrics, parser, and ablation harness exist, but need validation
  before they can support external claims.

See `RESULTS_REPORT.md` and the copied artifacts in `artifacts/results/` for the
current evidence base.

This means the project already has signal. What it lacks is not ambition; it lacks one
clean, defensible evaluation story.

## Core Research Questions

1. How much of search-agent performance comes from the retrieval layer itself, before
   any model fine-tuning?
2. Which Qdrant-native capabilities produce measurable lift beyond a fair 4-tool
   baseline?
3. Can smaller or mid-sized open models approach stronger retrieval performance when
   trained specifically to use better tools?
4. Do the gains transfer from general wiki-style retrieval to metadata-heavy enterprise
   corpora where payload filtering, grouping, and exact text search matter more?

## Hypotheses

1. A strong retrieval layer plus tool-aware prompting should produce meaningful gains
   even before RL.
2. Training will improve performance most when the evaluation contract is retrieval-
   first and the tasks reward tool selection rather than generic free-form answering.
3. Qdrant-native capabilities such as payload filtering and grouped retrieval will show
   larger gains on structured corpora than on Wikipedia-style benchmarks.
4. Retrieval-subagent evaluation will be more reproducible than answer-only judging,
   provided gold-document wiring is complete and stable.

## Research Plan

### Work Package 1: Evaluation Hardening

Goal: make the benchmark trustworthy before expanding the headline claims.

Tasks:

- Complete gold-document mapping for FRAMES and BrowseComp retrieval-mode evals.
- Make the ranked-document output contract the canonical scoring path.
- Fix or quarantine endpoint-routing failures so benchmark runs are not polluted by
  serving instability.
- Standardize one schema for per-example metrics and one schema for top-level summary
  metrics.
- Add explicit error-rate reporting to every result table.

Exit criteria:

- Retrieval-mode runs have valid gold-document coverage.
- Eval error rate is below 5 percent on headline runs.
- A malformed final output scores as empty output, not as a silent success case.

### Work Package 2: Fair Baseline Benchmark

Goal: define the clean comparison row.

Baseline tool set:

- `search_corpus`
- `text_search`
- `read_document`
- `prune_chunks`

Benchmarks:

- BrowseComp as the primary parity benchmark.
- FRAMES as the secondary evidence benchmark.

Method:

- Run the same benchmark slice with untrained and trained models.
- Keep the baseline retrieval stack fixed: dense + BM25 + unweighted RRF.
- Store both 1x rollout and 4x rollout variants where helpful, but do not mix them in
  the same headline row.

### Work Package 3: Qdrant-Native Ablations

Goal: measure lift from retrieval infrastructure rather than from vague system changes.

Ablation order:

1. Baseline: dense + BM25 + unweighted RRF
2. `+ weighted RRF`
3. `+ payload-filtered search`
4. `+ grouped retrieval`
5. `+ relevance feedback`
6. `+ late-interaction rerank` when the collection and index support it cleanly

Principle:

- Same questions
- Same output contract
- Same model
- One added capability at a time

The deliverable here is the actual differentiator for Asteroid. This is the part of
the work that can become a product story, a paper figure, and a partnership artifact at
the same time.

### Work Package 4: Training Study

Goal: measure what RL buys once the evaluation stack is stable.

Plan:

- Start with the cheaper 4B line for quick iterations and failure analysis.
- Use the 30B line for the best-quality headline runs once the task and metric path are
  stable.
- Track not just accuracy, but tool-use diversity, turns, and error rate.
- Gate further training on evidence that the model is improving actual retrieval
  behavior rather than merely exploiting answer-format quirks.

Open question to resolve empirically:

- Does RL improve ranking quality, search coverage, tool choice, or all three?

### Work Package 5: Domain-Specific Evaluation

Goal: test the features that make Qdrant materially different from generic search.

Priority domains:

- SEC filings
- patents
- legal code / legislative text

Why these matter:

- They reward metadata-aware retrieval.
- They naturally expose payload filtering.
- They make exact text search and grouping useful in a way wiki benchmarks do not.

## Metrics

### Headline Metrics

- `final_answer_found` for continuity with older answer-mode runs
- `output_recall`
- `output_precision`
- `f1`
- `trajectory_recall`

### Operational Metrics

- eval error rate
- tool calls
- turns
- token usage
- tool mix by benchmark and by checkpoint

### Gating Rule

No new headline claim should be made unless:

- gold-doc coverage is validated for that run
- eval error rate is reported
- the exact artifact path is recorded

## Deliverables

1. A clean, reproducible benchmark harness with retrieval-subagent scoring.
2. A baseline comparison table for untrained vs trained models on the same tasks.
3. A Qdrant-native ablation table showing lift per capability.
4. At least one domain-specific eval where structured retrieval features matter.
5. A short technical report grounded in artifact-backed results, not aspirational
   numbers.

## Success Criteria

The project counts as a strong next-phase success if it delivers all of the following:

1. One publishable baseline benchmark with validated retrieval metrics.
2. One publishable ablation result showing measurable lift from a Qdrant-native
   capability.
3. One clean trained-vs-untrained comparison without major serving or scoring
   confounds.
4. One domain-specific result that demonstrates why Qdrant features matter beyond
   generic Wikipedia benchmarks.

## Suggested Timeline

### Week 1

- Harden retrieval metrics
- finish gold-doc wiring
- clean up result schemas

### Week 2

- Run stable FRAMES and BrowseComp baselines
- validate 1x vs 4x rollout story

### Week 3

- Run ablations on the same fixed benchmark slice
- identify which feature lifts are real and reproducible

### Week 4

- Retrain selected 4B and 30B checkpoints against the stabilized benchmark
- measure tool behavior, not just headline score

### Week 5

- Build and run one domain-specific eval
- prepare the external writeup

## Bottom Line

Asteroid does not need a bigger narrative right now. It needs a cleaner experiment.
The work already in the repo is enough to justify that experiment: there is real
evidence that the retrieval layer matters, early evidence that training helps, and a
clear path to a differentiated result if the evaluation story is tightened first.
