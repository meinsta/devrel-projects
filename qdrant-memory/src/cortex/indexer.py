"""Code indexer for processing files and projects."""

import os
import sys
from pathlib import Path
from typing import Callable, Optional

from gitignore_parser import parse_gitignore

from .code_store import QdrantCodeStore
from .parser import CodeParser, get_parser, EXT_TO_LANG


# Default patterns to ignore
DEFAULT_IGNORE_PATTERNS = [
    ".git",
    ".svn",
    ".hg",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    ".env",
    "dist",
    "build",
    ".next",
    ".nuxt",
    "target",  # Rust
    "vendor",  # Go
    ".idea",
    ".vscode",
    "*.min.js",
    "*.min.css",
    "*.map",
    "*.lock",
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "Cargo.lock",
    "poetry.lock",
    "*.pyc",
    "*.pyo",
    "*.so",
    "*.dylib",
    "*.dll",
    "*.exe",
    "*.o",
    "*.a",
    "*.class",
    "*.jar",
    # Media/binary
    "*.png",
    "*.jpg",
    "*.jpeg",
    "*.gif",
    "*.ico",
    "*.svg",
    "*.mp3",
    "*.mp4",
    "*.pdf",
    "*.zip",
    "*.tar",
    "*.gz",
    # Generated
    "*.generated.*",
    "*_pb2.py",  # Protobuf
    "*.pb.go",
]


class CodeIndexer:
    """Index code files into Qdrant for hybrid search."""

    def __init__(
        self,
        store: QdrantCodeStore,
        parser: Optional[CodeParser] = None,
    ):
        self.store = store
        self.parser = parser or get_parser()

    def index_file(
        self,
        file_path: str,
        repo_id: str,
        content: Optional[str] = None,
    ) -> int:
        """
        Index a single file.

        Returns the number of chunks indexed.
        """
        path = Path(file_path)

        # Read content if not provided
        if content is None:
            try:
                content = path.read_text(encoding="utf-8")
            except Exception as e:
                print(f"[indexer] Failed to read {file_path}: {e}", file=sys.stderr)
                return 0

        # Skip empty files
        if not content.strip():
            return 0

        # Detect language
        language = self.parser.detect_language(file_path) or "unknown"

        # Delete existing chunks for this file (re-index)
        self.store.delete_file(str(path), repo_id)

        # Parse into chunks
        chunks = self.parser.chunk_file(file_path, content)

        # Index each chunk
        count = 0
        for chunk in chunks:
            try:
                self.store.index_chunk(
                    repo_id=repo_id,
                    file_path=str(path),
                    content=chunk.content,
                    language=language,
                    symbol_kind=chunk.kind,
                    symbol_name=chunk.name if chunk.kind != "file" else None,
                    start_line=chunk.start_line,
                    end_line=chunk.end_line,
                    parent_symbol=chunk.parent,
                    docstring=chunk.docstring,
                    signature=chunk.signature,
                )
                count += 1
            except Exception as e:
                print(f"[indexer] Failed to index chunk in {file_path}: {e}", file=sys.stderr)

        return count

    def index_project(
        self,
        project_path: str,
        repo_id: str,
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
        max_file_size: int = 100_000,  # 100KB
    ) -> dict:
        """
        Index an entire project directory.

        Args:
            project_path: Root directory to index
            repo_id: Repository identifier
            progress_callback: Optional callback(file_path, current, total)
            max_file_size: Skip files larger than this

        Returns:
            Stats dict with files_indexed, chunks_indexed, files_skipped, errors
        """
        root = Path(project_path).resolve()

        # Build ignore matcher
        ignore_matcher = self._build_ignore_matcher(root)

        # Collect files to index
        files_to_index = []
        for path in root.rglob("*"):
            if not path.is_file():
                continue

            rel_path = path.relative_to(root)

            # Check ignore patterns
            if ignore_matcher and ignore_matcher(str(path)):
                continue

            # Check if supported extension
            if path.suffix.lower() not in EXT_TO_LANG:
                continue

            # Check file size
            try:
                if path.stat().st_size > max_file_size:
                    continue
            except OSError:
                continue

            files_to_index.append(path)

        # Index files
        stats = {
            "files_indexed": 0,
            "chunks_indexed": 0,
            "files_skipped": 0,
            "errors": [],
        }

        total = len(files_to_index)
        for i, file_path in enumerate(files_to_index):
            if progress_callback:
                progress_callback(str(file_path), i + 1, total)

            try:
                chunks = self.index_file(str(file_path), repo_id)
                if chunks > 0:
                    stats["files_indexed"] += 1
                    stats["chunks_indexed"] += chunks
                else:
                    stats["files_skipped"] += 1
            except Exception as e:
                stats["errors"].append(f"{file_path}: {e}")

        return stats

    def _build_ignore_matcher(self, root: Path) -> Optional[Callable[[str], bool]]:
        """Build a function that returns True if a path should be ignored."""
        matchers = []

        # Check for .gitignore
        gitignore_path = root / ".gitignore"
        if gitignore_path.exists():
            try:
                matchers.append(parse_gitignore(gitignore_path))
            except Exception:
                pass

        # Add default patterns
        def default_matcher(path: str) -> bool:
            p = Path(path)
            # Check directory names in path
            for part in p.parts:
                if part in DEFAULT_IGNORE_PATTERNS:
                    return True
            # Check filename patterns
            name = p.name
            for pattern in DEFAULT_IGNORE_PATTERNS:
                if pattern.startswith("*."):
                    if name.endswith(pattern[1:]):
                        return True
                elif name == pattern:
                    return True
            return False

        matchers.append(default_matcher)

        def combined_matcher(path: str) -> bool:
            return any(m(path) for m in matchers)

        return combined_matcher

    def get_project_stats(self, repo_id: str) -> dict:
        """Get statistics about an indexed project."""
        # This would require a count query - simplified version
        return {
            "repo_id": repo_id,
            "status": "indexed",
        }


def create_indexer(
    url: str,
    api_key: Optional[str] = None,
    collection: str = "code_index",
) -> CodeIndexer:
    """Create an indexer with a new store connection."""
    store = QdrantCodeStore(url=url, api_key=api_key, collection=collection)
    return CodeIndexer(store=store)
