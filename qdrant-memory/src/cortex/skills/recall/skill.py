"""Recall skill - Semantic search across memories.

Orchestrates memory retrieval:
1. Embed query
2. Search Qdrant with filters (repo_id, kinds, tags, since_days)
3. Re-rank by freshness + verified boost + kind preference
4. Return top N results
"""

from typing import Any, Dict, List, Optional

from ..base import SkillContext
from .ranker import rerank_results, boost_for_query_type


class RecallSkill:
    """Skill for searching memories."""

    name = "recall"

    def apply(self, ctx: SkillContext, args: Dict[str, Any]) -> Dict[str, Any]:
        """Search for relevant memories.

        Args:
            ctx: Skill context with store, policy, etc.
            args: {
                query: str (search query),
                kinds: list[str] (optional, filter by kinds),
                tags: list[str] (optional, filter by tags),
                since_days: int (optional, only memories from last N days),
                limit: int (optional, default 8)
            }

        Returns:
            {success: bool, memories: list[dict], count: int}
        """
        query = args.get("query", "")
        kinds = args.get("kinds")
        tags = args.get("tags")
        since_days = args.get("since_days")
        limit = args.get("limit", 8)

        # Validate query
        if not query or len(query.strip()) < 2:
            return {
                "success": False,
                "error": "Query must be at least 2 characters",
                "memories": [],
                "count": 0,
            }

        try:
            # Search Qdrant
            results = ctx.store.search(
                query=query,
                repo_id=ctx.repo_id,
                kinds=kinds,
                tags=tags,
                since_days=since_days,
                limit=limit * 2,  # Fetch extra for re-ranking
            )

            # Apply query-type boost to kind weights
            ranking_config = ctx.policy.get("ranking", {})
            for result in results:
                kind = result.get("kind", "episode")
                query_boost = boost_for_query_type(query, kind)
                result["_query_boost"] = query_boost

            # Re-rank with freshness, verified, etc.
            ranked = rerank_results(results, ranking_config, query)

            # Take top N
            memories = ranked[:limit]

            # Clean up internal ranking data for response
            for mem in memories:
                mem.pop("_ranking", None)
                mem.pop("_query_boost", None)

            # Telemetry
            if ctx.telemetry:
                ctx.telemetry.count("memory.recall", 1)
                ctx.telemetry.count("memory.recall.results", len(memories))

            return {
                "success": True,
                "memories": memories,
                "count": len(memories),
                "query": query,
            }

        except Exception as e:
            return {
                "success": False,
                "error": f"Search failed: {e}",
                "memories": [],
                "count": 0,
            }
