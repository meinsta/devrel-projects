"""Skills - self-contained capability modules.

Each skill:
- Implements the Skill protocol (apply method)
- Receives SkillContext with store, embedder, policy
- Returns structured result dict
"""

from .base import SkillContext, Skill
from .remember import RememberSkill
from .recall import RecallSkill
from .recent import RecentSkill
from .delete import DeleteSkill
from .store import QdrantMemoryStore, Embedder, MemoryRecord

__all__ = [
    # Base
    "SkillContext",
    "Skill",
    # Skills
    "RememberSkill",
    "RecallSkill",
    "RecentSkill",
    "DeleteSkill",
    # Store
    "QdrantMemoryStore",
    "Embedder",
    "MemoryRecord",
]
