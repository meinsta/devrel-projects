"""Ablation framework for Qdrant-native feature evaluation.

Each ablation adds one Qdrant capability on top of the 4-tool baseline.
Ablations are applied in order:
1. + weighted RRF
2. + late-interaction rerank
3. + payload-filtered search
4. + grouped retrieval
5. + relevance feedback

The baseline uses: dense + BM25 + unweighted RRF, no payload filtering,
no grouped retrieval, no relevance feedback, no weighted RRF,
no late-interaction rerank.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from qdrant_client import models


class AblationType(str, Enum):
    BASELINE = "baseline"
    WEIGHTED_RRF = "weighted_rrf"
    LATE_INTERACTION_RERANK = "late_interaction_rerank"
    PAYLOAD_FILTERED = "payload_filtered"
    GROUPED_RETRIEVAL = "grouped_retrieval"
    RELEVANCE_FEEDBACK = "relevance_feedback"


# Ordered list matching the plan's evaluation sequence
ABLATION_ORDER = [
    AblationType.BASELINE,
    AblationType.WEIGHTED_RRF,
    AblationType.LATE_INTERACTION_RERANK,
    AblationType.PAYLOAD_FILTERED,
    AblationType.GROUPED_RETRIEVAL,
    AblationType.RELEVANCE_FEEDBACK,
]


@dataclass
class AblationConfig:
    """Configuration for a single ablation run."""
    ablation_type: AblationType = AblationType.BASELINE
    label: str = ""

    # Weighted RRF
    dense_weight: float = 1.0
    bm25_weight: float = 1.0

    # Late-interaction rerank
    rerank_model: str = ""
    rerank_top_k: int = 20

    # Payload filtering
    payload_filters: list[dict[str, Any]] = field(default_factory=list)

    # Grouped retrieval
    group_by_field: str = ""
    group_size: int = 1
    groups_limit: int = 5

    # Relevance feedback
    relevance_feedback_rounds: int = 0
    feedback_expansion_terms: int = 5

    def __post_init__(self):
        if not self.label:
            self.label = self.ablation_type.value


def baseline_config() -> AblationConfig:
    """4-tool baseline: dense + BM25 + unweighted RRF."""
    return AblationConfig(
        ablation_type=AblationType.BASELINE,
        label="baseline (dense + BM25 + unweighted RRF)",
    )


def weighted_rrf_config(dense_weight: float = 1.0, bm25_weight: float = 0.7) -> AblationConfig:
    """Baseline + weighted RRF fusion."""
    return AblationConfig(
        ablation_type=AblationType.WEIGHTED_RRF,
        label=f"+ weighted RRF (dense={dense_weight}, bm25={bm25_weight})",
        dense_weight=dense_weight,
        bm25_weight=bm25_weight,
    )


def late_interaction_rerank_config(
    rerank_model: str = "colbert-ir/colbertv2.0",
    rerank_top_k: int = 20,
) -> AblationConfig:
    """Baseline + late-interaction reranking (ColBERT)."""
    return AblationConfig(
        ablation_type=AblationType.LATE_INTERACTION_RERANK,
        label=f"+ late-interaction rerank ({rerank_model})",
        rerank_model=rerank_model,
        rerank_top_k=rerank_top_k,
    )


def payload_filtered_config(
    payload_filters: list[dict[str, Any]] | None = None,
) -> AblationConfig:
    """Baseline + payload-filtered search."""
    return AblationConfig(
        ablation_type=AblationType.PAYLOAD_FILTERED,
        label="+ payload-filtered search",
        payload_filters=payload_filters or [],
    )


def grouped_retrieval_config(
    group_by_field: str = "title",
    group_size: int = 2,
    groups_limit: int = 5,
) -> AblationConfig:
    """Baseline + grouped retrieval (deduplicate by field)."""
    return AblationConfig(
        ablation_type=AblationType.GROUPED_RETRIEVAL,
        label=f"+ grouped retrieval (by {group_by_field})",
        group_by_field=group_by_field,
        group_size=group_size,
        groups_limit=groups_limit,
    )


def relevance_feedback_config(
    rounds: int = 1,
    expansion_terms: int = 5,
) -> AblationConfig:
    """Baseline + pseudo-relevance feedback (query expansion)."""
    return AblationConfig(
        ablation_type=AblationType.RELEVANCE_FEEDBACK,
        label=f"+ relevance feedback ({rounds} round(s))",
        relevance_feedback_rounds=rounds,
        feedback_expansion_terms=expansion_terms,
    )


def build_all_ablations() -> list[AblationConfig]:
    """Build the full ablation sequence per the plan."""
    return [
        baseline_config(),
        weighted_rrf_config(),
        late_interaction_rerank_config(),
        payload_filtered_config(),
        grouped_retrieval_config(),
        relevance_feedback_config(),
    ]


def apply_ablation_to_prefetch(
    config: AblationConfig,
    query_vector: list[float],
    query_text: str,
    *,
    base_limit: int = 10,
) -> dict[str, Any]:
    """Build Qdrant query_points kwargs modified by the ablation config.

    Returns a dict of kwargs suitable for qdrant.query_points().
    The caller must add collection_name and with_payload.

    Ablation patterns from qdrant-search-quality skill:
    - Baseline: dense + BM25 + unweighted RRF
    - Weighted RRF: RrfQuery with per-prefetch weights (v1.17+)
    - Late-interaction rerank: prefetch dense+BM25, rescore with ColBERT multivectors
    - DBSF: Distribution-based score fusion (can outperform RRF for technical docs)
    - Grouped retrieval: deduplicate by doc_id field
    - Relevance feedback: RelevanceFeedbackQuery with naive strategy
    """
    bm25_prefetch = models.Prefetch(
        query=models.Document(text=query_text, model="Qdrant/bm25"),
        using="bm25",
        limit=base_limit,
    )
    dense_prefetch = models.Prefetch(
        query=query_vector, using="dense", limit=base_limit,
    )

    kwargs: dict[str, Any] = {"limit": 6}

    if config.ablation_type == AblationType.BASELINE:
        # Dense + BM25 + unweighted RRF (the fair baseline)
        kwargs["prefetch"] = [bm25_prefetch, dense_prefetch]
        kwargs["query"] = models.FusionQuery(fusion=models.Fusion.RRF)

    elif config.ablation_type == AblationType.WEIGHTED_RRF:
        # RrfQuery with weights: weight dense higher than BM25
        # Weights correspond to prefetch order: [bm25_weight, dense_weight]
        kwargs["prefetch"] = [bm25_prefetch, dense_prefetch]
        kwargs["query"] = models.RrfQuery(
            rrf=models.Rrf(weights=[config.bm25_weight, config.dense_weight])
        )

    elif config.ablation_type == AblationType.LATE_INTERACTION_RERANK:
        # Multi-stage: prefetch with dense+BM25 fused, then rescore with ColBERT
        # ColBERT multivectors stored without HNSW (rescore-only, per skill guidance)
        # NOTE: caller must provide colbert_query_vector (multivector embedding of query)
        first_stage = models.Prefetch(
            prefetch=[bm25_prefetch, dense_prefetch],
            query=models.FusionQuery(fusion=models.Fusion.RRF),
            limit=config.rerank_top_k,
        )
        kwargs["prefetch"] = [first_stage]
        # Placeholder: caller replaces with ColBERT multivector of the query
        kwargs["_colbert_rescore"] = True
        kwargs["using"] = "colbert"
        kwargs["limit"] = 6

    elif config.ablation_type == AblationType.PAYLOAD_FILTERED:
        # Same as baseline but with payload filter applied
        kwargs["prefetch"] = [bm25_prefetch, dense_prefetch]
        kwargs["query"] = models.FusionQuery(fusion=models.Fusion.RRF)
        if config.payload_filters:
            must_conditions = []
            for pf in config.payload_filters:
                for key, value in pf.items():
                    must_conditions.append(
                        models.FieldCondition(
                            key=key, match=models.MatchValue(value=value)
                        )
                    )
            if must_conditions:
                kwargs["query_filter"] = models.Filter(must=must_conditions)

    elif config.ablation_type == AblationType.GROUPED_RETRIEVAL:
        # Deduplicate by doc_id: one result per document
        # NOTE: grouped retrieval uses query_batch_groups or search_groups API,
        # not query_points. Caller must use the appropriate method.
        kwargs["prefetch"] = [bm25_prefetch, dense_prefetch]
        kwargs["query"] = models.FusionQuery(fusion=models.Fusion.RRF)
        kwargs["_group_by"] = config.group_by_field
        kwargs["_group_size"] = config.group_size
        kwargs["limit"] = config.groups_limit

    elif config.ablation_type == AblationType.RELEVANCE_FEEDBACK:
        # RF Query: use initial retrieval results as feedback signal
        # First do a standard search, then use top results as positive feedback
        # This is a two-phase process handled by the caller
        kwargs["prefetch"] = [bm25_prefetch, dense_prefetch]
        kwargs["query"] = models.FusionQuery(fusion=models.Fusion.RRF)
        kwargs["_rf_rounds"] = config.relevance_feedback_rounds

    # Keys prefixed with _ are metadata for the caller, not Qdrant API kwargs.
    # The caller must pop them before passing to qdrant.query_points().
    return kwargs


@dataclass
class AblationResult:
    """Result from a single ablation run on a query set."""
    config: AblationConfig
    metrics: dict[str, float] = field(default_factory=dict)
    per_query: list[dict[str, Any]] = field(default_factory=list)

    @property
    def label(self) -> str:
        return self.config.label

    def summary_row(self) -> str:
        """One-line summary for reporting."""
        parts = [f"{self.label}:"]
        for key in ["output_recall", "output_precision", "f1", "trajectory_recall"]:
            if key in self.metrics:
                parts.append(f"{key}={self.metrics[key]:.3f}")
        return " ".join(parts)
