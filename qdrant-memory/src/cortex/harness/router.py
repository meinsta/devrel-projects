"""Router - Routes MCP tool calls to skills.

The thin orchestration layer that:
- Maps tool names to skills
- Builds SkillContext per request
- Handles doctor diagnostics
"""

import os
from typing import Any, Dict, Optional

from .context import build_skill_context
from ..skills.remember import RememberSkill
from ..skills.recall import RecallSkill
from ..skills.recent import RecentSkill
from ..skills.delete import DeleteSkill


class Router:
    """
    Routes MCP tool calls to the appropriate skill.

    Exposes only the memory-focused golden path:
    - remember: Store a memory
    - recall: Search memories
    - list_recent: Get recent memories
    - delete: Remove a memory
    - doctor: Diagnostics
    """

    def __init__(self):
        # Initialize skills
        self._skills = {
            "remember": RememberSkill(),
            "recall": RecallSkill(),
            "list_recent": RecentSkill(),
            "delete": DeleteSkill(),
        }

    def handle(self, tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """
        Route a tool call to the appropriate skill.

        Args:
            tool_name: Name of the tool (remember, recall, list_recent, delete)
            args: Tool arguments

        Returns:
            Skill result dict
        """
        # Special case: doctor
        if tool_name == "doctor":
            return self.doctor()

        # Get skill
        skill = self._skills.get(tool_name)
        if not skill:
            return {
                "success": False,
                "error": f"Unknown tool: {tool_name}",
            }

        # Build context
        ctx = build_skill_context()

        # Execute skill
        return skill.apply(ctx, args)

    def doctor(self) -> Dict[str, Any]:
        """
        Comprehensive system diagnostic.

        Checks:
        - Environment (QDRANT_URL)
        - Store connectivity
        - Embedder health
        - Memory stats
        """
        report = {
            "checks": [],
            "summary": {"passed": 0, "failed": 0, "warnings": 0},
        }

        def add_check(name: str, status: str, message: str, details: Optional[dict] = None):
            report["checks"].append({
                "name": name,
                "status": status,
                "message": message,
                "details": details or {},
            })
            if status == "pass":
                report["summary"]["passed"] += 1
            elif status == "fail":
                report["summary"]["failed"] += 1
            else:
                report["summary"]["warnings"] += 1

        # Check QDRANT_URL
        qdrant_url = os.environ.get("QDRANT_URL")
        if qdrant_url:
            add_check("env_qdrant_url", "pass", f"QDRANT_URL: {qdrant_url[:50]}...")
        else:
            add_check("env_qdrant_url", "fail", "QDRANT_URL not set")

        # Check store
        try:
            ctx = build_skill_context()
            store_health = ctx.store.health()
            add_check(
                "store",
                "pass",
                f"Store: {store_health.get('collection', 'unknown')}",
                store_health,
            )
        except Exception as e:
            add_check("store", "fail", f"Store error: {e}")

        # Check embedder
        try:
            ctx = build_skill_context()
            embedder_health = ctx.embedder.health()
            add_check(
                "embedder",
                "pass",
                f"Embedder: {embedder_health.get('model', 'unknown')}",
                embedder_health,
            )
        except Exception as e:
            add_check("embedder", "fail", f"Embedder error: {e}")

        # Check repo detection
        try:
            ctx = build_skill_context()
            add_check("repo", "pass", f"Repo: {ctx.repo_id}")
            if ctx.git_commit:
                add_check("git", "pass", f"Git: {ctx.git_branch} @ {ctx.git_commit}")
            else:
                add_check("git", "warn", "Not in a git repo")
        except Exception as e:
            add_check("repo", "fail", f"Repo detection error: {e}")

        # Overall status
        report["status"] = "healthy" if report["summary"]["failed"] == 0 else "unhealthy"
        return report


# Global router instance
_router: Optional[Router] = None


def get_router() -> Router:
    """Get the global router instance."""
    global _router
    if _router is None:
        _router = Router()
    return _router
