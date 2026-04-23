"""Delete skill - Remove memories.

Handles memory deletion:
1. Validate ID format
2. Check memory exists
3. Delete from Qdrant
4. Return success/failure
"""

from typing import Any, Dict

from ..base import SkillContext


class DeleteSkill:
    """Skill for deleting memories."""

    name = "delete"

    def apply(self, ctx: SkillContext, args: Dict[str, Any]) -> Dict[str, Any]:
        """Delete a memory by ID.

        Args:
            ctx: Skill context with store, policy, etc.
            args: {
                memory_id: str (UUID of memory to delete)
            }

        Returns:
            {success: bool, deleted_id: str} or {success: false, error: str}
        """
        memory_id = args.get("memory_id", "")

        # Validate ID
        if not memory_id or len(memory_id) < 10:
            return {
                "success": False,
                "error": "Invalid memory ID",
            }

        try:
            # Check if memory exists and belongs to this repo
            existing = ctx.store.get(memory_id)
            if not existing:
                return {
                    "success": False,
                    "error": f"Memory not found: {memory_id}",
                }

            # Verify repo ownership (tenant isolation)
            if existing.get("repo_id") != ctx.repo_id:
                return {
                    "success": False,
                    "error": "Memory not found",  # Don't reveal existence
                }

            # Delete from store
            deleted = ctx.store.delete(memory_id)

            if deleted:
                # Telemetry
                if ctx.telemetry:
                    ctx.telemetry.count("memory.delete", 1)

                return {
                    "success": True,
                    "deleted_id": memory_id,
                }
            else:
                return {
                    "success": False,
                    "error": f"Failed to delete memory: {memory_id}",
                }

        except Exception as e:
            return {
                "success": False,
                "error": f"Delete failed: {e}",
            }
