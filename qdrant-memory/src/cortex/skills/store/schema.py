"""Memory record schema and validation.

Defines the MemoryRecord dataclass and payload conversion.
This is the single source of truth for memory structure.
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from typing import Optional, List
import uuid


VALID_KINDS = {"episode", "fact", "recipe"}
SCHEMA_VERSION = 1


@dataclass
class MemoryRecord:
    """A single memory record stored in Qdrant.

    Attributes:
        id: Unique identifier (UUID)
        repo_id: Tenant boundary (hash of git remote + repo name)
        kind: Memory type (episode|fact|recipe)
        text: Memory content
        tags: Categorization tags
        topic: Canonical topic for facts (for upsert/conflict detection)
        created_at: ISO timestamp
        verified_at: ISO timestamp when memory was verified (boosts ranking)
        expires_at: ISO timestamp for TTL
        git_commit: Commit hash when memory was created
        git_branch: Branch name when memory was created
        source: Where memory came from (claude-code, manual, etc.)
        version: Schema version for migrations
    """

    # Required fields
    repo_id: str
    kind: str
    text: str

    # Optional fields with defaults
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    tags: List[str] = field(default_factory=list)
    topic: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    verified_at: Optional[str] = None
    expires_at: Optional[str] = None
    git_commit: Optional[str] = None
    git_branch: Optional[str] = None
    source: str = "claude-code"
    version: int = SCHEMA_VERSION

    def __post_init__(self):
        """Validate fields after initialization."""
        if self.kind not in VALID_KINDS:
            raise ValueError(f"Invalid kind '{self.kind}'. Must be one of: {VALID_KINDS}")
        if not self.text or len(self.text.strip()) < 10:
            raise ValueError("Memory text must be at least 10 characters")
        if not self.repo_id:
            raise ValueError("repo_id is required")

    def to_payload(self) -> dict:
        """Convert to Qdrant payload format."""
        return {
            "repo_id": self.repo_id,
            "kind": self.kind,
            "text": self.text,
            "tags": self.tags,
            "topic": self.topic,
            "created_at": self.created_at,
            "verified_at": self.verified_at,
            "expires_at": self.expires_at,
            "git_commit": self.git_commit,
            "git_branch": self.git_branch,
            "source": self.source,
            "version": self.version,
        }

    def to_dict(self) -> dict:
        """Convert to dict for API response."""
        return {
            "id": self.id,
            "kind": self.kind,
            "text": self.text,
            "tags": self.tags,
            "topic": self.topic,
            "created_at": self.created_at,
            "verified_at": self.verified_at,
            "expires_at": self.expires_at,
            "git_commit": self.git_commit,
            "git_branch": self.git_branch,
            "source": self.source,
        }

    @classmethod
    def from_payload(cls, point_id: str, payload: dict) -> "MemoryRecord":
        """Construct from Qdrant search result.

        Args:
            point_id: Qdrant point ID
            payload: Qdrant payload dict

        Returns:
            MemoryRecord instance
        """
        return cls(
            id=str(point_id),
            repo_id=payload.get("repo_id", ""),
            kind=payload.get("kind", "episode"),
            text=payload.get("text", ""),
            tags=payload.get("tags", []),
            topic=payload.get("topic"),
            created_at=payload.get("created_at", ""),
            verified_at=payload.get("verified_at"),
            expires_at=payload.get("expires_at"),
            git_commit=payload.get("git_commit"),
            git_branch=payload.get("git_branch"),
            source=payload.get("source", "unknown"),
            version=payload.get("version", 1),
        )

    def is_expired(self) -> bool:
        """Check if memory has expired based on expires_at."""
        if not self.expires_at:
            return False
        try:
            expires = datetime.fromisoformat(self.expires_at.replace("Z", "+00:00"))
            return datetime.now(timezone.utc) > expires
        except (ValueError, AttributeError):
            return False

    def set_ttl(self, days: int) -> None:
        """Set expiration to N days from now."""
        if days <= 0:
            self.expires_at = None
        else:
            expires = datetime.now(timezone.utc) + timedelta(days=days)
            self.expires_at = expires.isoformat()


def default_ttl_for_kind(kind: str, config: dict = None) -> Optional[int]:
    """Get default TTL in days for a memory kind.

    Args:
        kind: Memory kind (episode|fact|recipe)
        config: Optional config dict with TTL overrides

    Returns:
        TTL in days, or None for no expiration
    """
    config = config or {}
    defaults = {
        "episode": config.get("default_episode_ttl_days", 90),
        "fact": config.get("default_fact_ttl_days", 365),
        "recipe": config.get("default_recipe_ttl_days", 180),
    }
    return defaults.get(kind)
