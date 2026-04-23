"""Tests for retrieval metrics and reward computation."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "frames_search"))

from metrics import (
    compute_f1,
    compute_f_beta,
    compute_precision,
    compute_recall,
    compute_reward,
    compute_trajectory_recall,
    evaluate_retrieval,
)


def test_perfect_recall():
    assert compute_recall({"d001", "d002"}, {"d001", "d002"}) == 1.0


def test_partial_recall():
    assert compute_recall({"d001"}, {"d001", "d002"}) == 0.5


def test_zero_recall():
    assert compute_recall({"d003"}, {"d001", "d002"}) == 0.0


def test_empty_gold_recall():
    assert compute_recall({"d001"}, set()) == 1.0


def test_perfect_precision():
    assert compute_precision({"d001", "d002"}, {"d001", "d002"}) == 1.0


def test_partial_precision():
    assert compute_precision({"d001", "d003"}, {"d001", "d002"}) == 0.5


def test_zero_precision():
    assert compute_precision({"d003"}, {"d001", "d002"}) == 0.0


def test_empty_output_precision():
    assert compute_precision(set(), {"d001"}) == 0.0


def test_f1_perfect():
    assert compute_f1(1.0, 1.0) == 1.0


def test_f1_zero():
    assert compute_f1(0.0, 0.0) == 0.0


def test_f1_partial():
    f1 = compute_f1(0.5, 1.0)
    assert abs(f1 - 2 / 3) < 1e-6


def test_f_beta_recall_weighted():
    # beta=4 should weight recall much more than precision
    f4 = compute_f_beta(0.1, 1.0, beta=4.0)
    f1 = compute_f1(0.1, 1.0)
    assert f4 > f1  # beta=4 forgives low precision if recall is high


def test_trajectory_recall():
    assert compute_trajectory_recall({"d001", "d002", "d003"}, {"d001", "d002"}) == 1.0
    assert compute_trajectory_recall({"d001"}, {"d001", "d002"}) == 0.5
    assert compute_trajectory_recall(set(), {"d001"}) == 0.0


def test_evaluate_retrieval_full():
    metrics = evaluate_retrieval(
        output_doc_ids=["d001", "d002"],
        gold_doc_ids=["d001", "d002", "d003"],
        seen_doc_ids=["d001", "d002", "d003"],
        final_answer_found=True,
        tool_calls=5,
        turns=3,
        token_usage=10000,
    )
    assert abs(metrics.output_recall - 2 / 3) < 1e-6
    assert metrics.output_precision == 1.0
    assert metrics.trajectory_recall == 1.0
    assert metrics.final_answer_found is True
    assert metrics.tool_calls == 5
    assert metrics.turns == 3


def test_reward_basic():
    metrics = evaluate_retrieval(
        output_doc_ids=["d001", "d002"],
        gold_doc_ids=["d001", "d002"],
        seen_doc_ids=["d001", "d002"],
        final_answer_found=True,
    )
    reward = compute_reward(metrics)
    # Perfect retrieval + answer found bonus = 0.7*1.0 + 0.3*1.0 + 1.0 = 2.0
    assert abs(reward - 2.0) < 1e-6


def test_reward_prune_penalty():
    metrics = evaluate_retrieval(
        output_doc_ids=["d001"],
        gold_doc_ids=["d001"],
        seen_doc_ids=["d001"],
        final_answer_found=True,
    )
    reward = compute_reward(metrics, consecutive_prunes=5, prune_threshold=3)
    # 2 excess prunes * 0.1 = 0.2 penalty
    expected = 2.0 - 0.2
    assert abs(reward - expected) < 1e-6


def test_reward_turn_penalty():
    metrics = evaluate_retrieval(
        output_doc_ids=["d001"],
        gold_doc_ids=["d001"],
        seen_doc_ids=["d001"],
        final_answer_found=True,
        turns=128,
    )
    reward = compute_reward(metrics)
    # At max turns, turn penalty = 0.5
    expected = 2.0 - 0.5
    assert abs(reward - expected) < 1e-6


def test_reward_no_answer_no_bonus():
    metrics = evaluate_retrieval(
        output_doc_ids=[],
        gold_doc_ids=["d001"],
        seen_doc_ids=[],
        final_answer_found=False,
    )
    reward = compute_reward(metrics)
    assert reward == 0.0
