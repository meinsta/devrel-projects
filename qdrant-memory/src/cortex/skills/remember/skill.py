"""Remember skill - Store memories.

Orchestrates memory storage:
1. Validate kind
2. Run policy checks (secrets, size)
3. Build MemoryRecord
4. Apply TTL defaults
5. Upsert to Qdrant
6. Return success + ID
"""

from typing import Any, Dict, List, Optional

from ..base import SkillContext
from ..store.schema import MemoryRecord, VALID_KINDS, default_ttl_for_kind


class RememberSkill:
    """Skill for storing memories."""

    name = "remember"

    def apply(self, ctx: SkillContext, args: Dict[str, Any]) -> Dict[str, Any]:
        """Store a memory.

        Args:
            ctx: Skill context with store, policy, etc.
            args: {
                kind: str (episode|fact|recipe),
                text: str (memory content),
                tags: list[str] (optional),
                ttl_days: int (optional)
            }

        Returns:
            {success: bool, id: str} or {success: false, error: str}
        """
        kind = args.get("kind", "")
        text = args.get("text", "")
        tags = args.get("tags", []) or []
        ttl_days = args.get("ttl_days")

        # Validate kind
        if kind not in VALID_KINDS:
            return {
                "success": False,
                "error": f"Invalid kind '{kind}'. Must be one of: {', '.join(VALID_KINDS)}",
            }

        # Validate text length
        if not text or len(text.strip()) < 10:
            return {
                "success": False,
                "error": "Memory text must be at least 10 characters",
            }

        # Policy check: secrets and size
        from ...harness.policy import enforce_remember_policy, PolicyViolation

        try:
            enforce_remember_policy(text, kind, ctx.policy)
        except PolicyViolation as e:
            return {
                "success": False,
                "error": str(e),
            }

        # Build memory record
        record = MemoryRecord(
            repo_id=ctx.repo_id,
            kind=kind,
            text=text.strip(),
            tags=tags,
            git_commit=ctx.git_commit,
            git_branch=ctx.git_branch,
            source=ctx.source,
        )

        # Apply TTL
        if ttl_days is not None:
            record.set_ttl(ttl_days)
        else:
            # Use default TTL for kind
            default_ttl = default_ttl_for_kind(kind, ctx.policy.get("memory", {}))
            if default_ttl:
                record.set_ttl(default_ttl)

        # Store in Qdrant
        try:
            memory_id = ctx.store.upsert(record)

            # Telemetry
            if ctx.telemetry:
                ctx.telemetry.count("memory.remember", 1, {"kind": kind})

            return {
                "success": True,
                "id": memory_id,
                "kind": kind,
                "expires_at": record.expires_at,
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to store memory: {e}",
            }
