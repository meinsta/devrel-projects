"""Recent skill - List recent memories.

Retrieves memories ordered by creation time:
1. Query Qdrant with optional kind filter
2. Order by created_at descending
3. Return top N results
"""

from typing import Any, Dict, List, Optional

from ..base import SkillContext


class RecentSkill:
    """Skill for listing recent memories."""

    name = "list_recent"

    def apply(self, ctx: SkillContext, args: Dict[str, Any]) -> Dict[str, Any]:
        """List recent memories.

        Args:
            ctx: Skill context with store, policy, etc.
            args: {
                kind: str (optional, filter by kind),
                limit: int (optional, default 20)
            }

        Returns:
            {success: bool, memories: list[dict], count: int}
        """
        kind = args.get("kind")
        limit = args.get("limit", 20)

        # Validate kind if provided
        from ..store.schema import VALID_KINDS

        if kind and kind not in VALID_KINDS:
            return {
                "success": False,
                "error": f"Invalid kind '{kind}'. Must be one of: {', '.join(VALID_KINDS)}",
                "memories": [],
                "count": 0,
            }

        # Clamp limit
        limit = max(1, min(100, limit))

        try:
            # Get recent from store
            memories = ctx.store.list_recent(
                repo_id=ctx.repo_id,
                kind=kind,
                limit=limit,
            )

            # Telemetry
            if ctx.telemetry:
                ctx.telemetry.count("memory.list_recent", 1)

            return {
                "success": True,
                "memories": memories,
                "count": len(memories),
            }

        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to list recent memories: {e}",
                "memories": [],
                "count": 0,
            }
