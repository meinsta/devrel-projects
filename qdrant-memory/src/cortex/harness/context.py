"""Context - Builds skill context for request handling.

Provides:
- SkillContext builder with repo detection
- Git provenance capture
- Policy loading from cortex.toml
"""

import hashlib
import os
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

try:
    import tomllib
except ImportError:
    import tomli as tomllib

from ..skills.base import SkillContext
from ..skills.store import QdrantMemoryStore, Embedder


def _get_repo_id(project_path: str) -> str:
    """Get repo_id from git remote or folder name."""
    # Try git remote URL
    try:
        result = subprocess.run(
            ["git", "-C", project_path, "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            remote_url = result.stdout.strip()
            url_hash = hashlib.sha256(remote_url.encode()).hexdigest()[:12]
            repo_name = remote_url.rstrip("/").split("/")[-1].replace(".git", "")
            return f"{repo_name}-{url_hash}"
    except Exception:
        pass

    # Fall back to directory name
    return os.path.basename(os.path.abspath(project_path))


def _get_repo_name(project_path: str) -> str:
    """Get human-readable repo name."""
    try:
        result = subprocess.run(
            ["git", "-C", project_path, "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            remote_url = result.stdout.strip()
            return remote_url.rstrip("/").split("/")[-1].replace(".git", "")
    except Exception:
        pass
    return os.path.basename(os.path.abspath(project_path))


def _get_git_info(project_path: str) -> tuple[Optional[str], Optional[str]]:
    """Get current git commit and branch."""
    try:
        commit = subprocess.run(
            ["git", "-C", project_path, "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        branch = subprocess.run(
            ["git", "-C", project_path, "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        git_commit = commit.stdout.strip()[:12] if commit.returncode == 0 else None
        git_branch = branch.stdout.strip() if branch.returncode == 0 else None
        return git_commit, git_branch
    except Exception:
        return None, None


def _load_policy(project_path: str) -> Dict[str, Any]:
    """Load policy from cortex.toml if present."""
    policy = {
        "memory": {
            "default_episode_ttl_days": 90,
            "default_fact_ttl_days": 365,
            "default_recipe_ttl_days": 180,
        },
        "security": {
            "max_payload_bytes": 8192,
            "block_secrets": True,
        },
        "ranking": {
            "freshness_decay_days": 30,
            "verified_boost": 1.5,
        },
    }

    # Try cortex.toml in project
    config_path = Path(project_path) / "cortex.toml"
    if config_path.exists():
        try:
            with open(config_path, "rb") as f:
                user_config = tomllib.load(f)
            # Merge user config
            for section, values in user_config.items():
                if section in policy and isinstance(values, dict):
                    policy[section].update(values)
        except Exception:
            pass

    # Environment overrides
    if os.environ.get("CORTEX_MAX_PAYLOAD_BYTES"):
        try:
            policy["security"]["max_payload_bytes"] = int(
                os.environ["CORTEX_MAX_PAYLOAD_BYTES"]
            )
        except ValueError:
            pass

    return policy


# Shared instances (lazy-loaded)
_store: Optional[QdrantMemoryStore] = None
_embedder: Optional[Embedder] = None


def _get_store() -> QdrantMemoryStore:
    """Get shared Qdrant store instance."""
    global _store
    if _store is None:
        _store = QdrantMemoryStore()
    return _store


def _get_embedder() -> Embedder:
    """Get shared embedder instance."""
    global _embedder
    if _embedder is None:
        _embedder = Embedder()
    return _embedder


def build_skill_context(project_path: Optional[str] = None, source: str = "claude-code") -> SkillContext:
    """
    Build SkillContext for a request.

    Args:
        project_path: Project directory (defaults to cwd)
        source: Source identifier (e.g., "claude-code", "manual")

    Returns:
        Fully populated SkillContext
    """
    cwd = project_path or os.getcwd()
    git_commit, git_branch = _get_git_info(cwd)
    policy = _load_policy(cwd)

    return SkillContext(
        repo_id=_get_repo_id(cwd),
        repo_name=_get_repo_name(cwd),
        cwd=cwd,
        git_commit=git_commit,
        git_branch=git_branch,
        now_iso=datetime.now(timezone.utc).isoformat(),
        policy=policy,
        store=_get_store(),
        embedder=_get_embedder(),
        telemetry=None,  # Can be added later
        source=source,
    )


# ============================================================================
# Legacy ContextPack (kept for backwards compatibility during migration)
# ============================================================================

@dataclass
class ContextPack:
    """
    Assembled context for Claude.

    Contains:
    - Code snippets from search
    - Relevant memories
    - Symbol definitions
    - Metadata (files touched, line ranges)
    """

    code_snippets: list[dict] = field(default_factory=list)
    memories: list[dict] = field(default_factory=list)
    definitions: list[dict] = field(default_factory=list)
    references: list[dict] = field(default_factory=list)

    # Metadata
    files_touched: set[str] = field(default_factory=set)
    total_lines: int = 0
    truncated: bool = False

    def add_code(self, snippet: dict) -> None:
        """Add a code snippet."""
        self.code_snippets.append(snippet)
        if snippet.get("file_path"):
            self.files_touched.add(snippet["file_path"])
        self.total_lines += snippet.get("end_line", 0) - snippet.get("start_line", 0)

    def add_memory(self, memory: dict) -> None:
        """Add a relevant memory."""
        self.memories.append(memory)

    def add_definition(self, definition: dict) -> None:
        """Add a symbol definition."""
        self.definitions.append(definition)
        if definition.get("file"):
            self.files_touched.add(definition["file"])

    def add_reference(self, reference: dict) -> None:
        """Add a symbol reference."""
        self.references.append(reference)
        if reference.get("file"):
            self.files_touched.add(reference["file"])

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "code_snippets": self.code_snippets,
            "memories": self.memories,
            "definitions": self.definitions,
            "references": self.references,
            "metadata": {
                "files_touched": list(self.files_touched),
                "total_lines": self.total_lines,
                "truncated": self.truncated,
            },
        }

    def format_for_prompt(self, max_tokens: int = 8000) -> str:
        """
        Format context for inclusion in a prompt.

        Prioritizes:
        1. Memories (most relevant context)
        2. Definitions (precise locations)
        3. Code snippets (supporting evidence)
        """
        parts = []
        estimated_tokens = 0

        # Add memories first
        if self.memories:
            parts.append("## Relevant Memories\n")
            for mem in self.memories[:5]:
                text = f"- [{mem.get('kind', 'memory')}] {mem.get('text', '')[:500]}\n"
                estimated_tokens += len(text) // 4
                if estimated_tokens > max_tokens:
                    self.truncated = True
                    break
                parts.append(text)

        # Add definitions
        if self.definitions and estimated_tokens < max_tokens:
            parts.append("\n## Definitions Found\n")
            for defn in self.definitions[:10]:
                text = f"- {defn.get('name', '?')} ({defn.get('kind', '?')}) at {defn.get('file', '?')}:{defn.get('line', '?')}\n"
                estimated_tokens += len(text) // 4
                if estimated_tokens > max_tokens:
                    self.truncated = True
                    break
                parts.append(text)

        # Add code snippets
        if self.code_snippets and estimated_tokens < max_tokens:
            parts.append("\n## Code Snippets\n")
            for snippet in self.code_snippets[:5]:
                content = snippet.get("content", "")[:1000]
                file_path = snippet.get("file_path", "?")
                start = snippet.get("start_line", "?")

                text = f"### {file_path}:{start}\n```\n{content}\n```\n"
                estimated_tokens += len(text) // 4
                if estimated_tokens > max_tokens:
                    self.truncated = True
                    break
                parts.append(text)

        if self.truncated:
            parts.append("\n*[Context truncated due to length]*\n")

        return "".join(parts)
