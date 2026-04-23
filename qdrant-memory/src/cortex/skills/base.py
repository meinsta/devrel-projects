"""Skills base - SkillContext and Skill protocol.

Following Anthropic's Agent Skills pattern:
- Skills are self-contained units with clear interfaces
- SkillContext provides shared state (repo, git, store, embedder)
- Harness orchestrates but skills do the work
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Protocol


@dataclass
class SkillContext:
    """Shared context for all skills.

    Built once per request by the harness, passed to skill.apply().
    Provides repo identity, git provenance, policy config, and shared services.
    """

    # Repo identity
    repo_id: str
    repo_name: str
    cwd: str

    # Git provenance (auto-captured)
    git_commit: Optional[str] = None
    git_branch: Optional[str] = None

    # Timestamp
    now_iso: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    # Policy config (loaded from cortex.toml + env vars)
    policy: Dict[str, Any] = field(default_factory=dict)

    # Shared services (injected by harness)
    store: Any = None  # QdrantMemoryStore
    embedder: Any = None  # Embedder
    telemetry: Any = None  # Telemetry (no-op by default)

    # Source identifier
    source: str = "claude-code"


class Skill(Protocol):
    """Protocol for all skills.

    Skills are pure functions with a name and apply method.
    They receive SkillContext and args, return a dict.
    No side effects outside the store.
    """

    name: str

    def apply(self, ctx: SkillContext, args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the skill with given context and arguments.

        Args:
            ctx: Shared context (repo, git, store, embedder, policy)
            args: Tool arguments from MCP

        Returns:
            Dict with result (success/error + data)
        """
        ...


class NoOpTelemetry:
    """Default telemetry that does nothing."""

    def count(self, metric: str, value: int = 1, tags: Dict[str, str] = None) -> None:
        pass

    def timing(self, metric: str, value_ms: float, tags: Dict[str, str] = None) -> None:
        pass

    def log(self, level: str, message: str, **kwargs) -> None:
        pass
