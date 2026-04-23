# Asteroid Qdrant Research

Asteroid is a curated research snapshot of a Qdrant-native search-agent stack.
It packages the core agent code, evaluation harness, tests, and a small set of
result artifacts into a cleaner repo for research discussion and follow-on work.

## What This Repo Contains

- A model-agnostic agent toolkit in `src/asteroid`
- FRAMES and BrowseComp evaluation code in `frames_search` and `scripts`
- Unit tests for retrieval parsing, metrics, novelty pressure, and token budgets
- Copied result artifacts in `artifacts/results`
- Two top-level docs for discussion:
  - `RESULTS_REPORT.md`
  - `RESEARCH_PROPOSAL.md`

## Current Evidence

The strongest artifact-backed result in this repo today is on the internal wiki
retrieval task:

| Comparison | Metric | Result |
|---|---|---:|
| Trained Qwen3-30B adapter | `avg_reward` | **0.788** |
| `gpt-oss-20b` | `avg_reward` | 0.636 |

There is also direct evidence that training changes behavior on FRAMES:

| Model | Metric | Result |
|---|---|---:|
| Qwen3-4B base | `score_avg` | 0.19 |
| Qwen3-4B trained checkpoint | `score_avg` | 0.35 |
| Best stored Qwen3-4B trained checkpoint | `score_avg` | **0.56** |

The detailed writeup lives in `RESULTS_REPORT.md`.

## Repo Layout

```text
asteroid-qdrant-research/
  artifacts/results/   # copied eval artifacts used in the report
  frames_search/       # FRAMES / BrowseComp environments and metric code
  scripts/             # indexing, eval, and ablation scripts
  src/asteroid/        # core agent and tool code
  tests/               # unit tests
  RESULTS_REPORT.md
  RESEARCH_PROPOSAL.md
```

## Quickstart

```bash
uv sync
uv run pytest
```

If you are using plain `pip`:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[eval,dev]'
pytest
```

Some scripts require API keys and local indexing setup. The unit tests do not.

## Suggested Reading Order

1. `RESULTS_REPORT.md`
2. `RESEARCH_PROPOSAL.md`
3. `scripts/eval_frames_holdout.py`
4. `scripts/run_ablations.py`

## Why This Repo Exists

The original workspace contains a lot of exploratory runs, drafts, and dead ends.
This repo is the trimmed version: enough code and evidence to discuss the research
direction clearly, without dragging along the entire scratch tree.
