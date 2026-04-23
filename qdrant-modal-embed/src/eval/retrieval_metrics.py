"""Retrieval Evaluation Metrics for E-Commerce Search"""

import logging
from typing import Dict, List, Optional, Set

import numpy as np
from qdrant_client import QdrantClient
from sentence_transformers import SparseEncoder

from src.config import ESCI_SCORES, RELEVANT_LABELS, WANDS_SCORES, WANDS_RELEVANT_LABELS
from src.qdrant.index import sparse_embedding_to_qdrant

logger = logging.getLogger(__name__)


def dcg_at_k(relevances: List[float], k: int) -> float:
    """
    Discounted Cumulative Gain at k.

    DCG = sum(rel_i / log2(i + 2)) for i in 0..k-1
    """
    relevances = relevances[:k]
    if not relevances:
        return 0.0

    gains = [rel / np.log2(i + 2) for i, rel in enumerate(relevances)]
    return sum(gains)


def ndcg_at_k(relevances: List[float], k: int = 10) -> float:
    """
    Normalized Discounted Cumulative Gain at k.

    nDCG = DCG / IDCG where IDCG is the ideal DCG with sorted relevances.

    Args:
        relevances: List of relevance scores in retrieved order
        k: Cutoff rank

    Returns:
        nDCG@k score in [0, 1]
    """
    dcg = dcg_at_k(relevances, k)
    ideal_relevances = sorted(relevances, reverse=True)
    idcg = dcg_at_k(ideal_relevances, k)

    if idcg == 0:
        return 0.0
    return dcg / idcg


def mrr_at_k(relevant_ids: Set[str], retrieved_ids: List[str], k: int = 10) -> float:
    """
    Mean Reciprocal Rank at k.

    MRR = 1/rank of first relevant result (0 if none in top k)

    Args:
        relevant_ids: Set of relevant item IDs
        retrieved_ids: List of retrieved item IDs in rank order
        k: Cutoff rank

    Returns:
        RR score in [0, 1]
    """
    for rank, item_id in enumerate(retrieved_ids[:k], start=1):
        if item_id in relevant_ids:
            return 1.0 / rank
    return 0.0


def recall_at_k(relevant_ids: Set[str], retrieved_ids: List[str], k: int) -> float:
    """
    Recall at k.

    Recall@k = |retrieved ∩ relevant| / |relevant|

    Args:
        relevant_ids: Set of all relevant item IDs
        retrieved_ids: List of retrieved item IDs
        k: Cutoff rank

    Returns:
        Recall@k score in [0, 1]
    """
    if not relevant_ids:
        return 0.0

    retrieved_set = set(retrieved_ids[:k])
    hits = len(relevant_ids & retrieved_set)
    return hits / len(relevant_ids)


def precision_at_k(relevant_ids: Set[str], retrieved_ids: List[str], k: int) -> float:
    """
    Precision at k.

    Precision@k = |retrieved ∩ relevant| / k

    Args:
        relevant_ids: Set of all relevant item IDs
        retrieved_ids: List of retrieved item IDs
        k: Cutoff rank

    Returns:
        Precision@k score in [0, 1]
    """
    if k == 0:
        return 0.0

    retrieved_set = set(retrieved_ids[:k])
    hits = len(relevant_ids & retrieved_set)
    return hits / k


def _detect_label_format(ground_truth: List[Dict]) -> str:
    """
    Detect whether labels are ESCI (string) or WANDS (numeric) format.

    Returns:
        "esci" for string labels, "wands" for numeric labels
    """
    for q in ground_truth:
        relevance = q.get("relevance", {})
        for label in relevance.values():
            if isinstance(label, int):
                return "wands"
            elif isinstance(label, str):
                return "esci"
    return "esci"  # Default to ESCI


def _get_relevance_score(label, label_format: str) -> float:
    """Get relevance score for a label based on format."""
    if label_format == "wands":
        return WANDS_SCORES.get(label, 0.0)
    else:
        return ESCI_SCORES.get(label, 0.0)


def _get_default_label(label_format: str):
    """Get default irrelevant label for format."""
    return 0 if label_format == "wands" else "I"


def _is_relevant(label, label_format: str) -> bool:
    """Check if a label is considered relevant."""
    if label_format == "wands":
        return label in WANDS_RELEVANT_LABELS
    else:
        return label in RELEVANT_LABELS


def evaluate_retrieval(
    retrieved_results: List[Dict],
    ground_truth: List[Dict],
    k_values: List[int] = [10, 50, 100],
) -> Dict[str, float]:
    """
    Evaluate retrieval results against ground truth.

    Automatically detects label format:
    - ESCI: String labels ("E", "S", "C", "I")
    - WANDS: Numeric labels (2=Exact, 1=Partial, 0=Irrelevant)

    Args:
        retrieved_results: List of dicts with:
            - "query_id": str
            - "retrieved_ids": List[str] of product IDs in rank order
        ground_truth: List of dicts with:
            - "query_id": str
            - "relevance": Dict[product_id, label] mapping

    Returns:
        Dict of metrics:
            - ndcg@k for each k
            - mrr@k for k=10
            - recall@k for each k
            - precision@k for each k
    """
    # Detect label format (ESCI string vs WANDS numeric)
    label_format = _detect_label_format(ground_truth)
    logger.info(f"Detected label format: {label_format}")

    # Build ground truth lookup
    gt_lookup = {q["query_id"]: q["relevance"] for q in ground_truth}

    # Collect per-query metrics
    all_ndcg = {k: [] for k in k_values}
    all_mrr = []
    all_recall = {k: [] for k in k_values}
    all_precision = {k: [] for k in k_values}

    default_label = _get_default_label(label_format)

    for result in retrieved_results:
        query_id = result["query_id"]
        retrieved_ids = result["retrieved_ids"]

        if query_id not in gt_lookup:
            continue

        relevance_map = gt_lookup[query_id]

        # Get relevance scores in retrieved order
        relevances = [
            _get_relevance_score(relevance_map.get(pid, default_label), label_format)
            for pid in retrieved_ids
        ]

        # Get set of relevant IDs
        relevant_ids = {
            pid
            for pid, label in relevance_map.items()
            if _is_relevant(label, label_format)
        }

        # Compute metrics
        for k in k_values:
            all_ndcg[k].append(ndcg_at_k(relevances, k))
            all_recall[k].append(recall_at_k(relevant_ids, retrieved_ids, k))
            all_precision[k].append(precision_at_k(relevant_ids, retrieved_ids, k))

        all_mrr.append(mrr_at_k(relevant_ids, retrieved_ids, k=10))

    # Aggregate
    metrics = {
        "mrr@10": np.mean(all_mrr) if all_mrr else 0.0,
    }

    for k in k_values:
        metrics[f"ndcg@{k}"] = np.mean(all_ndcg[k]) if all_ndcg[k] else 0.0
        metrics[f"recall@{k}"] = np.mean(all_recall[k]) if all_recall[k] else 0.0
        metrics[f"precision@{k}"] = np.mean(all_precision[k]) if all_precision[k] else 0.0

    return metrics


class QdrantEvaluator:
    """
    Evaluate sparse encoder using Qdrant for retrieval.

    This enables evaluation against a live Qdrant index,
    useful for continuous evaluation during training.
    """

    def __init__(
        self,
        client: QdrantClient,
        model: SparseEncoder,
        collection_name: str,
        vector_name: str = "text",
    ):
        """
        Initialize evaluator.

        Args:
            client: Qdrant client
            model: SparseEncoder for query encoding
            collection_name: Collection to evaluate against
            vector_name: Sparse vector field name
        """
        self.client = client
        self.model = model
        self.collection_name = collection_name
        self.vector_name = vector_name

    def evaluate(
        self,
        queries: List[Dict],
        k_values: List[int] = [10, 50, 100],
        show_progress: bool = True,
    ) -> Dict[str, float]:
        """
        Run retrieval evaluation.

        Args:
            queries: List of dicts with:
                - "query_id": str
                - "query": str (query text)
                - "relevance": Dict[product_id, label]
            k_values: Cutoff ranks to evaluate
            show_progress: Show progress bar

        Returns:
            Dict of aggregated metrics
        """
        from tqdm import tqdm

        retrieved_results = []
        iterator = queries
        if show_progress:
            iterator = tqdm(queries, desc="Evaluating")

        for q in iterator:
            query_text = q["query"]

            # Encode query
            emb = self.model.encode([query_text])[0]
            sparse_vector = sparse_embedding_to_qdrant(emb)

            # Search
            max_k = max(k_values)
            results = self.client.query_points(
                collection_name=self.collection_name,
                query=sparse_vector,
                using=self.vector_name,
                limit=max_k,
                with_payload=True,
            )

            # Extract product IDs
            retrieved_ids = [
                p.payload.get("product_id", "") for p in results.points
            ]

            retrieved_results.append(
                {
                    "query_id": q["query_id"],
                    "retrieved_ids": retrieved_ids,
                }
            )

        # Compute metrics
        return evaluate_retrieval(
            retrieved_results=retrieved_results,
            ground_truth=queries,
            k_values=k_values,
        )


def print_metrics(metrics: Dict[str, float], title: str = "Evaluation Results"):
    """Pretty print evaluation metrics."""
    print(f"\n{'='*50}")
    print(title)
    print("=" * 50)

    # Group by metric type
    ndcg_metrics = {k: v for k, v in metrics.items() if k.startswith("ndcg")}
    mrr_metrics = {k: v for k, v in metrics.items() if k.startswith("mrr")}
    recall_metrics = {k: v for k, v in metrics.items() if k.startswith("recall")}
    precision_metrics = {k: v for k, v in metrics.items() if k.startswith("precision")}

    if mrr_metrics:
        print("\nMRR:")
        for k, v in sorted(mrr_metrics.items()):
            print(f"  {k}: {v:.4f}")

    if ndcg_metrics:
        print("\nnDCG:")
        for k, v in sorted(ndcg_metrics.items()):
            print(f"  {k}: {v:.4f}")

    if recall_metrics:
        print("\nRecall:")
        for k, v in sorted(recall_metrics.items()):
            print(f"  {k}: {v:.4f}")

    if precision_metrics:
        print("\nPrecision:")
        for k, v in sorted(precision_metrics.items()):
            print(f"  {k}: {v:.4f}")

    print("=" * 50)
