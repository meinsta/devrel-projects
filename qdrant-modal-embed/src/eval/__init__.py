"""Evaluation metrics and reporting"""

from src.eval.retrieval_metrics import ndcg_at_k, mrr_at_k, recall_at_k, evaluate_retrieval
from src.eval.baselines import (
    run_baseline_evaluation,
    evaluate_baseline,
    BM25_MODEL,
    SPLADE_MODEL,
)

__all__ = [
    "ndcg_at_k",
    "mrr_at_k",
    "recall_at_k",
    "evaluate_retrieval",
    "run_baseline_evaluation",
    "evaluate_baseline",
    "BM25_MODEL",
    "SPLADE_MODEL",
]
