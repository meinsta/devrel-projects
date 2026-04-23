"""Retrieval metrics for the retrieval-subagent evaluation contract.

All metrics operate on sets of doc_ids. Gold doc_ids come from the benchmark
ground truth (e.g. FRAMES positive article URLs mapped to stable doc_ids).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class RetrievalMetrics:
    """Complete metric record for a single retrieval evaluation."""
    output_doc_ids: list[str] = field(default_factory=list)
    gold_doc_ids: list[str] = field(default_factory=list)
    seen_doc_ids: list[str] = field(default_factory=list)
    final_answer_found: bool = False
    output_recall: float = 0.0
    output_precision: float = 0.0
    f1: float = 0.0
    trajectory_recall: float = 0.0
    tool_calls: int = 0
    turns: int = 0
    token_usage: int = 0


def compute_recall(output_ids: set[str], gold_ids: set[str]) -> float:
    if not gold_ids:
        return 1.0
    return len(output_ids & gold_ids) / len(gold_ids)


def compute_precision(output_ids: set[str], gold_ids: set[str]) -> float:
    if not output_ids:
        return 0.0
    return len(output_ids & gold_ids) / len(output_ids)


def compute_f1(precision: float, recall: float) -> float:
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def compute_f_beta(precision: float, recall: float, beta: float = 4.0) -> float:
    """F-beta score. beta > 1 weights recall higher than precision."""
    if precision + recall == 0:
        return 0.0
    beta_sq = beta ** 2
    return (1 + beta_sq) * precision * recall / (beta_sq * precision + recall)


def compute_trajectory_recall(seen_ids: set[str], gold_ids: set[str]) -> float:
    """Fraction of gold docs that appeared anywhere in the agent trajectory."""
    if not gold_ids:
        return 1.0
    return len(seen_ids & gold_ids) / len(gold_ids)


def evaluate_retrieval(
    output_doc_ids: list[str],
    gold_doc_ids: list[str],
    seen_doc_ids: list[str],
    final_answer_found: bool = False,
    tool_calls: int = 0,
    turns: int = 0,
    token_usage: int = 0,
) -> RetrievalMetrics:
    """Compute all retrieval metrics for a single question."""
    out_set = set(output_doc_ids)
    gold_set = set(gold_doc_ids)
    seen_set = set(seen_doc_ids)

    recall = compute_recall(out_set, gold_set)
    precision = compute_precision(out_set, gold_set)

    return RetrievalMetrics(
        output_doc_ids=output_doc_ids,
        gold_doc_ids=gold_doc_ids,
        seen_doc_ids=seen_doc_ids,
        final_answer_found=final_answer_found,
        output_recall=recall,
        output_precision=precision,
        f1=compute_f1(precision, recall),
        trajectory_recall=compute_trajectory_recall(seen_set, gold_set),
        tool_calls=tool_calls,
        turns=turns,
        token_usage=token_usage,
    )


# ---------------------------------------------------------------------------
# Reward function (Context-1 style)
# ---------------------------------------------------------------------------

def compute_reward(
    metrics: RetrievalMetrics,
    beta: float = 4.0,
    final_answer_bonus: float = 1.0,
    max_prune_penalty: float = 0.5,
    consecutive_prunes: int = 0,
    prune_threshold: int = 3,
    max_turns: int = 128,
    turn_penalty_start: int = 64,
) -> float:
    """Context-1-style reward.

    reward = 0.7 * F_beta + 0.3 * trajectory_recall
             + final_answer_found_bonus
             - prune_penalty
             - turn_penalty

    Prune penalty: 0.1 per consecutive prune beyond threshold, capped.
    Turn penalty: ramps from 0 at turn_penalty_start to 0.5 at max_turns.
    """
    f_beta = compute_f_beta(
        metrics.output_precision, metrics.output_recall, beta=beta
    )
    base = 0.7 * f_beta + 0.3 * metrics.trajectory_recall

    bonus = final_answer_bonus if metrics.final_answer_found else 0.0

    prune_excess = max(0, consecutive_prunes - prune_threshold)
    prune_pen = min(prune_excess * 0.1, max_prune_penalty)

    if metrics.turns <= turn_penalty_start:
        turn_pen = 0.0
    elif metrics.turns >= max_turns:
        turn_pen = 0.5
    else:
        progress = (metrics.turns - turn_penalty_start) / (max_turns - turn_penalty_start)
        turn_pen = 0.5 * progress

    return base + bonus - prune_pen - turn_pen
