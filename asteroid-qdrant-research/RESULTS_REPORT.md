# Asteroid Results Report

Date: April 2, 2026

## Executive Summary

Asteroid already has one strong, defensible result: on the internal `asteroid-search`
wiki retrieval task, a trained Qwen3-30B adapter outperforms `gpt-oss-20b` on the
same harness and evaluation setup. FRAMES shows encouraging transfer signal, but the
stored checkpoints are still unstable and small-sample. BrowseComp remains weak.

The retrieval-subagent contract, retrieval metrics, and Qdrant ablation plumbing are
implemented, but the current stored retrieval-mode runs are not publication-ready.
Some runs are missing gold-document wiring, and at least one stored run failed due to
endpoint routing errors rather than model behavior.

## Artifact-Backed Results

### 1. Wiki retrieval (`asteroid-search`)

These are the cleanest results in the repo today.

| Model | n | Metric | Result | Notes | Artifact |
|---|---:|---|---:|---|---|
| `Qwen3-30B` trained adapter `f3lt79e1...` | 50 | `avg_reward` | **0.788** | Zero eval errors | `artifacts/results/wiki/qwen30b_trained_8bc1995a_metadata.json` |
| `Qwen3-30B` trained adapter `f3lt79e1...` | 50 | `avg_reward` | 0.780 | Zero eval errors | `artifacts/results/wiki/qwen30b_trained_c62e58a1_metadata.json` |
| `Qwen3-30B` trained adapter `f3lt79e1...` | 50 | `avg_reward` | 0.764 | Zero eval errors | `artifacts/results/wiki/qwen30b_trained_ebeb797a_metadata.json` |
| `Qwen3-30B` trained adapter `f3lt79e1...` | 50 | `avg_reward` | 0.752 | Zero eval errors | `artifacts/results/wiki/qwen30b_trained_c026c033_metadata.json` |
| `gpt-oss-20b` base | 50 | `avg_reward` | 0.636 | `avg_error=0.04` | `artifacts/results/wiki/gpt_oss_20b_e6bb44cc_metadata.json` |
| `Qwen3-30B` base | 50 | `avg_reward` | 0.516 | High eval error rate (`avg_error=0.52`), not a clean floor | `artifacts/results/wiki/qwen30b_base_3770875c_metadata.json` |

What this supports:

- The trained 30B adapter is consistently better than `gpt-oss-20b` on the stored
  50-question wiki evals.
- The strongest directly defensible comparison in-repo today is `0.788` vs `0.636`,
  a `+0.152` absolute gain.
- The trained runs are also operationally cleaner than the stored base Qwen runs.

What this does not yet support:

- A clean "base Qwen3-30B to trained Qwen3-30B" headline. The stored base Qwen runs
  have too many eval errors to use as a reliable floor.

### 2. FRAMES holdout (`answer` scoring mode)

These runs are useful as early signal, not as final benchmark claims.

| Model | n | Metric | Result | Artifact |
|---|---:|---|---:|---|
| `Qwen3-4B` base | 20 | `score_avg` | 0.19 | `artifacts/results/frames/frames_holdout_base.json` |
| `Qwen3-4B` trained adapter `l49czs4k...` | 20 | `score_avg` | 0.35 | `artifacts/results/frames/frames_holdout_l49czs4k.json` |
| `Qwen3-4B` trained adapter `dkh5h5as...` | 20 | `score_avg` | **0.56** | `artifacts/results/frames/frames_holdout_dkh5h5as.json` |
| `Qwen3-30B` trained adapter `ew3idqqu...` | 20 | `score_avg` | 0.45 | `artifacts/results/frames/frames_holdout_ew3idqqu.json` |
| `Qwen3-30B` trained adapter `g68hwgee...` | 5 | `score_avg` | 0.00 | `artifacts/results/frames/frames_holdout_g68hwgee.json` |

Takeaways:

- FRAMES transfer is real. Multiple trained checkpoints beat the stored 4B base
  score of `0.19`.
- The best stored holdout score is `0.56` on a 20-question slice.
- Results are still unstable across checkpoints and sample sizes, so this is not yet
  the place to make parity claims against Context-1.

### 3. BrowseComp holdout (`answer_found`)

BrowseComp is the weakest area in the current artifact set.

| Model | n | Metric | Result | Artifact |
|---|---:|---|---:|---|
| `Qwen3-4B` trained adapter `dkh5h5as...` | 20 | `answer_found_avg` | 0.17 | `artifacts/results/browsecomp/browsecomp_qwen3_dkh5h5as.json` |
| `Qwen3-4B` trained adapter `l49czs4k...` | 20 | `answer_found_avg` | 0.17 | `artifacts/results/browsecomp/browsecomp_holdout_l49czs4k.json` |
| `Qwen3-30B` trained adapter `ew3idqqu...` | 20 | `answer_found_avg` | 0.14 | `artifacts/results/browsecomp/browsecomp_holdout_ew3idqqu.json` |
| `Qwen3-4B` trained adapter `dkh5h5as...` | 10 | `answer_found_avg` | 0.20 | `artifacts/results/browsecomp/browsecomp_holdout_dkh5h5as.json` |
| `Qwen3-30B` trained adapter `g68hwgee...` | 10 | `answer_found_avg` | 0.10 | `artifacts/results/browsecomp/browsecomp_holdout_g68hwgee.json` |

Takeaway:

- BrowseComp is not working well enough yet to anchor the story. It should be treated
  as an open research problem, not a headline benchmark.

## What Is Working

- The core agent + tool stack is good enough to produce repeatable gains on the wiki
  retrieval task.
- Training signal exists on FRAMES. Even the small stored holdout runs show lift over
  the base 4B result.
- The repository already contains the ingredients for a real research story:
  harness, tool layer, holdout scripts, ablations, tests, and draft writeups.

## What Is Not Ready To Claim Publicly

- Any final retrieval-subagent F1 / precision / recall numbers for FRAMES.
- Any final Qdrant ablation lift table.
- Any "we matched or beat Context-1" claim on FRAMES or BrowseComp.
- Any clean untrained-vs-trained Qwen3-30B delta on the wiki task unless the base
  eval is rerun without the routing failures visible in the stored artifacts.

## Why The Retrieval Metrics Are Not Yet Publishable

Two concrete issues show up in the stored retrieval-mode artifacts:

1. `artifacts/results/frames/frames_holdout_base_retrieval.json` contains endpoint
   failures with empty model output and zero tool calls. That file is measuring
   infrastructure failure as much as model behavior.
2. Several retrieval-mode and ablation runs report patterns like
   `output_recall=1.0`, `output_precision=0.0`, and `f1=0.0`. That strongly suggests
   the gold-document mapping is not fully wired for those runs, so the metrics are not
   yet trustworthy as benchmark evidence.

The retrieval pipeline is promising as engineering work, but it still needs a hardening
pass before it should appear in an external report.

## Recommended Story Right Now

If this needs to be summarized externally today, the strongest honest framing is:

- Asteroid already demonstrates a real training win on a controlled wiki retrieval
  task: best stored run `0.788` vs `0.636` for `gpt-oss-20b` on the same eval setup.
- FRAMES shows encouraging early transfer, with a best stored holdout of `0.56` on a
  20-question slice, but the benchmark is not stable enough yet for parity claims.
- BrowseComp is currently the clearest gap and should be framed as next work.
- The most important next milestone is not "more hype"; it is turning the retrieval
  evaluation and ablation path into a publishable, reproducible benchmark.
