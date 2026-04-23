"""Recall ranker - Re-rank search results for better relevance.

Takes raw Qdrant results and re-ranks by:
- vector_score (base)
- freshness (decay by age)
- verified_boost (if verified_at present)
- kind_preference (configurable)
"""

from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
import math


# Default ranking config
DEFAULT_FRESHNESS_DECAY_DAYS = 30
DEFAULT_VERIFIED_BOOST = 1.5
DEFAULT_KIND_WEIGHTS = {
    "episode": 1.2,  # Episodes slightly preferred for "fix this" queries
    "recipe": 1.1,
    "fact": 1.0,
}


def rerank_results(
    results: List[Dict[str, Any]],
    config: Optional[Dict[str, Any]] = None,
    query_context: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Re-rank Qdrant search results with freshness and verified boost.

    Args:
        results: Raw results from Qdrant search (must have 'score', 'created_at', etc.)
        config: Optional ranking config overrides
        query_context: Optional query text for context-aware ranking

    Returns:
        Re-ranked list of results with 'final_score' added
    """
    if not results:
        return []

    config = config or {}
    freshness_decay_days = config.get("freshness_decay_days", DEFAULT_FRESHNESS_DECAY_DAYS)
    verified_boost = config.get("verified_boost", DEFAULT_VERIFIED_BOOST)
    kind_weights = config.get("kind_weights", DEFAULT_KIND_WEIGHTS)

    now = datetime.now(timezone.utc)

    for result in results:
        # Start with vector score
        base_score = result.get("score", 0.0)

        # Freshness decay: exponential decay based on age
        created_at = result.get("created_at", "")
        freshness_factor = 1.0
        if created_at:
            try:
                created = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                age_days = (now - created).days
                # Exponential decay: 0.5 at decay_days, approaching 0 at 3x
                freshness_factor = math.exp(-age_days / freshness_decay_days)
                # Clamp to reasonable range
                freshness_factor = max(0.3, min(1.0, freshness_factor))
            except (ValueError, AttributeError):
                pass

        # Verified boost
        verified_factor = 1.0
        if result.get("verified_at"):
            verified_factor = verified_boost

        # Kind weight
        kind = result.get("kind", "episode")
        kind_factor = kind_weights.get(kind, 1.0)

        # Combine scores (multiplicative)
        final_score = base_score * freshness_factor * verified_factor * kind_factor

        result["final_score"] = round(final_score, 4)
        result["_ranking"] = {
            "base": round(base_score, 4),
            "freshness": round(freshness_factor, 4),
            "verified": round(verified_factor, 4),
            "kind": round(kind_factor, 4),
        }

    # Sort by final_score descending
    results.sort(key=lambda x: x.get("final_score", 0), reverse=True)

    return results


def boost_for_query_type(query: str, kind: str) -> float:
    """Detect query intent and boost appropriate kinds.

    Simple heuristic - could be enhanced with ML.

    Args:
        query: Search query
        kind: Memory kind

    Returns:
        Boost factor (1.0 = no change)
    """
    query_lower = query.lower()

    # Bug/fix queries prefer episodes
    fix_keywords = {"fix", "bug", "error", "issue", "problem", "broke", "broken", "fail"}
    if any(kw in query_lower for kw in fix_keywords):
        if kind == "episode":
            return 1.3
        elif kind == "fact":
            return 0.9

    # How-to queries prefer recipes
    howto_keywords = {"how", "run", "test", "deploy", "build", "setup", "install", "start"}
    if any(kw in query_lower for kw in howto_keywords):
        if kind == "recipe":
            return 1.3
        elif kind == "fact":
            return 1.1

    # What/convention queries prefer facts
    what_keywords = {"what", "convention", "rule", "standard", "use", "using"}
    if any(kw in query_lower for kw in what_keywords):
        if kind == "fact":
            return 1.2

    return 1.0
