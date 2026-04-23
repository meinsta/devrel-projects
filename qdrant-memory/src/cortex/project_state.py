"""Project State - On-disk project config and state management.

Creates a `.qci/` folder in the project root with:
- config.yaml: Project configuration
- state.json: Runtime state (last indexed, active LSP, etc.)
- logs/: Tool call logs for debugging
- cache/: File hashes for incremental indexing
"""

import hashlib
import json
import os
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional
import yaml


@dataclass
class ProjectConfig:
    """Project configuration (persisted to config.yaml)."""

    # Identity
    project_name: str = ""
    language: str = "auto"

    # Indexing
    include_patterns: list[str] = field(default_factory=lambda: ["src/**", "lib/**", "app/**"])
    exclude_patterns: list[str] = field(default_factory=lambda: [
        "node_modules/**", ".git/**", "dist/**", "build/**",
        "*.min.js", "*.bundle.js", "__pycache__/**", ".venv/**",
        "*.pyc", "*.lock", "package-lock.json", "yarn.lock"
    ])
    max_file_size_kb: int = 100

    # Scopes (suggested path prefixes)
    scopes: dict[str, str] = field(default_factory=lambda: {
        "source": "src/",
        "tests": "tests/",
    })

    # LSP
    lsp_enabled: bool = True
    lsp_languages: list[str] = field(default_factory=list)  # empty = auto-detect

    # Memory
    memory_default_ttl_days: Optional[int] = None
    memory_max_episode_age_days: int = 90


@dataclass
class ProjectState:
    """Runtime state (persisted to state.json)."""

    # Indexing state
    last_indexed_at: Optional[str] = None
    last_indexed_commit: Optional[str] = None
    files_indexed: int = 0
    chunks_indexed: int = 0

    # LSP state
    lsp_activated: bool = False
    lsp_language: Optional[str] = None
    lsp_activated_at: Optional[str] = None

    # Stats
    total_tool_calls: int = 0
    total_searches: int = 0
    total_memories_stored: int = 0

    # Session
    current_session_id: Optional[str] = None
    session_started_at: Optional[str] = None


class ProjectStateManager:
    """
    Manages the .qci/ folder for a project.

    Structure:
    .qci/
    ├── config.yaml      # User-editable project config
    ├── state.json       # Runtime state
    ├── file_hashes.json # For incremental indexing
    └── logs/
        └── tool_calls.jsonl
    """

    QCI_DIR = ".qci"
    CONFIG_FILE = "config.yaml"
    STATE_FILE = "state.json"
    HASHES_FILE = "file_hashes.json"
    LOGS_DIR = "logs"
    TOOL_LOG_FILE = "tool_calls.jsonl"

    def __init__(self, project_path: str):
        self.project_path = Path(project_path).resolve()
        self.qci_path = self.project_path / self.QCI_DIR

        self._config: Optional[ProjectConfig] = None
        self._state: Optional[ProjectState] = None
        self._file_hashes: dict[str, str] = {}

    @property
    def exists(self) -> bool:
        """Check if .qci folder exists."""
        return self.qci_path.exists()

    def init(self, force: bool = False) -> dict:
        """
        Initialize .qci folder.

        Returns:
            {"created": list, "skipped": list}
        """
        result = {"created": [], "skipped": []}

        # Create .qci directory
        if not self.qci_path.exists():
            self.qci_path.mkdir(parents=True)
            result["created"].append(self.QCI_DIR)

        # Create logs directory
        logs_path = self.qci_path / self.LOGS_DIR
        if not logs_path.exists():
            logs_path.mkdir()
            result["created"].append(f"{self.QCI_DIR}/{self.LOGS_DIR}")

        # Create config.yaml
        config_path = self.qci_path / self.CONFIG_FILE
        if not config_path.exists() or force:
            config = self._detect_config()
            self._write_config(config)
            result["created"].append(f"{self.QCI_DIR}/{self.CONFIG_FILE}")
        else:
            result["skipped"].append(f"{self.QCI_DIR}/{self.CONFIG_FILE} (exists)")

        # Create state.json
        state_path = self.qci_path / self.STATE_FILE
        if not state_path.exists() or force:
            state = ProjectState(
                session_started_at=datetime.utcnow().isoformat(),
                current_session_id=hashlib.md5(str(time.time()).encode()).hexdigest()[:8],
            )
            self._write_state(state)
            result["created"].append(f"{self.QCI_DIR}/{self.STATE_FILE}")
        else:
            result["skipped"].append(f"{self.QCI_DIR}/{self.STATE_FILE} (exists)")

        # Add to .gitignore if not already
        self._update_gitignore()

        return result

    def _detect_config(self) -> ProjectConfig:
        """Auto-detect project configuration."""
        config = ProjectConfig()
        config.project_name = self.project_path.name

        # Detect language
        lang_markers = {
            "python": ["pyproject.toml", "setup.py", "requirements.txt"],
            "typescript": ["tsconfig.json"],
            "javascript": ["package.json"],
            "rust": ["Cargo.toml"],
            "go": ["go.mod"],
            "java": ["pom.xml", "build.gradle"],
        }

        for lang, markers in lang_markers.items():
            for marker in markers:
                if (self.project_path / marker).exists():
                    config.language = lang
                    break

        # Detect source directory
        for src in ["src", "lib", "app", "pkg"]:
            if (self.project_path / src).is_dir():
                config.scopes["source"] = f"{src}/"
                break

        # Detect test directory
        for test in ["tests", "test", "__tests__", "spec"]:
            if (self.project_path / test).is_dir():
                config.scopes["tests"] = f"{test}/"
                break

        return config

    def _write_config(self, config: ProjectConfig) -> None:
        """Write config to YAML file."""
        config_path = self.qci_path / self.CONFIG_FILE

        # Convert to dict and add comments
        data = asdict(config)

        header = """# Qdrant Code Intelligence - Project Configuration
# Edit this file to customize indexing, LSP, and memory settings.
# Documentation: https://github.com/YOUR_ORG/qdrant-memory

"""
        config_path.write_text(header + yaml.dump(data, default_flow_style=False, sort_keys=False))

    def _write_state(self, state: ProjectState) -> None:
        """Write state to JSON file."""
        state_path = self.qci_path / self.STATE_FILE
        state_path.write_text(json.dumps(asdict(state), indent=2))

    def _update_gitignore(self) -> None:
        """Add .qci/state.json and .qci/logs to .gitignore."""
        gitignore_path = self.project_path / ".gitignore"

        entries_to_add = [
            "# Qdrant Code Intelligence",
            ".qci/state.json",
            ".qci/file_hashes.json",
            ".qci/logs/",
        ]

        existing_content = ""
        if gitignore_path.exists():
            existing_content = gitignore_path.read_text()

        # Check if already present
        if ".qci/state.json" in existing_content:
            return

        # Append
        with open(gitignore_path, "a") as f:
            if existing_content and not existing_content.endswith("\n"):
                f.write("\n")
            f.write("\n" + "\n".join(entries_to_add) + "\n")

    def get_config(self) -> ProjectConfig:
        """Load project config."""
        if self._config is not None:
            return self._config

        config_path = self.qci_path / self.CONFIG_FILE
        if not config_path.exists():
            return ProjectConfig()

        data = yaml.safe_load(config_path.read_text())
        self._config = ProjectConfig(**data)
        return self._config

    def get_state(self) -> ProjectState:
        """Load project state."""
        if self._state is not None:
            return self._state

        state_path = self.qci_path / self.STATE_FILE
        if not state_path.exists():
            return ProjectState()

        data = json.loads(state_path.read_text())
        self._state = ProjectState(**data)
        return self._state

    def save_state(self) -> None:
        """Persist current state to disk."""
        if self._state is not None:
            self._write_state(self._state)

    def update_state(self, **kwargs) -> None:
        """Update state fields and persist."""
        state = self.get_state()
        for key, value in kwargs.items():
            if hasattr(state, key):
                setattr(state, key, value)
        self._state = state
        self.save_state()

    def log_tool_call(
        self,
        tool_name: str,
        args: dict,
        result: any,
        duration_ms: float,
        error: Optional[str] = None,
    ) -> None:
        """Log a tool call for debugging/observability."""
        if not self.exists:
            return

        log_path = self.qci_path / self.LOGS_DIR / self.TOOL_LOG_FILE

        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "tool": tool_name,
            "args": args,
            "duration_ms": round(duration_ms, 2),
            "error": error,
            "result_type": type(result).__name__ if result else None,
            "result_size": len(result) if isinstance(result, (list, dict, str)) else None,
        }

        with open(log_path, "a") as f:
            f.write(json.dumps(entry) + "\n")

        # Update stats
        state = self.get_state()
        state.total_tool_calls += 1
        if "search" in tool_name.lower() or tool_name in ["find", "where_is", "who_calls"]:
            state.total_searches += 1
        if tool_name == "remember":
            state.total_memories_stored += 1
        self._state = state
        self.save_state()

    def get_file_hashes(self) -> dict[str, str]:
        """Load file hashes for incremental indexing."""
        if self._file_hashes:
            return self._file_hashes

        hashes_path = self.qci_path / self.HASHES_FILE
        if hashes_path.exists():
            self._file_hashes = json.loads(hashes_path.read_text())

        return self._file_hashes

    def save_file_hashes(self, hashes: dict[str, str]) -> None:
        """Save file hashes."""
        self._file_hashes = hashes
        hashes_path = self.qci_path / self.HASHES_FILE
        hashes_path.write_text(json.dumps(hashes, indent=2))

    def get_changed_files(self, file_paths: list[str]) -> list[str]:
        """
        Return files that have changed since last index.

        Uses content hashing for change detection.
        """
        old_hashes = self.get_file_hashes()
        changed = []
        new_hashes = {}

        for file_path in file_paths:
            path = Path(file_path)
            if not path.exists():
                continue

            # Compute hash
            content_hash = hashlib.md5(path.read_bytes()).hexdigest()
            new_hashes[str(path)] = content_hash

            # Check if changed
            if str(path) not in old_hashes or old_hashes[str(path)] != content_hash:
                changed.append(file_path)

        return changed

    def get_recent_logs(self, limit: int = 50) -> list[dict]:
        """Get recent tool call logs."""
        log_path = self.qci_path / self.LOGS_DIR / self.TOOL_LOG_FILE
        if not log_path.exists():
            return []

        lines = log_path.read_text().strip().split("\n")
        logs = []
        for line in lines[-limit:]:
            if line:
                logs.append(json.loads(line))

        return logs

    def get_summary(self) -> dict:
        """Get project state summary for display."""
        config = self.get_config()
        state = self.get_state()

        return {
            "project": {
                "name": config.project_name,
                "language": config.language,
                "path": str(self.project_path),
            },
            "indexing": {
                "last_indexed": state.last_indexed_at,
                "last_commit": state.last_indexed_commit,
                "files": state.files_indexed,
                "chunks": state.chunks_indexed,
            },
            "lsp": {
                "activated": state.lsp_activated,
                "language": state.lsp_language,
            },
            "stats": {
                "total_tool_calls": state.total_tool_calls,
                "total_searches": state.total_searches,
                "total_memories": state.total_memories_stored,
            },
            "scopes": config.scopes,
        }


def get_project_state(project_path: Optional[str] = None) -> ProjectStateManager:
    """Get project state manager for a path."""
    path = project_path or os.getcwd()
    return ProjectStateManager(path)
