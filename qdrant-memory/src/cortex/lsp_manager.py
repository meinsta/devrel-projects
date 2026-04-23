"""LSP Manager - handles language server lifecycle and operations.

This is the core of the "better than Serena" approach:
- LSP for precise symbol understanding (like Serena)
- But backed by Qdrant for hybrid search + memory (unlike Serena)
"""

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from multilspy import SyncLanguageServer
from multilspy.multilspy_config import MultilspyConfig
from multilspy.multilspy_logger import MultilspyLogger


# Language detection mapping
EXTENSION_TO_LANGUAGE = {
    ".py": "python",
    ".pyi": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".rs": "rust",
    ".go": "go",
    ".java": "java",
    ".cs": "csharp",
    ".rb": "ruby",
    ".dart": "dart",
}

# Languages supported by multilspy
SUPPORTED_LANGUAGES = {"python", "rust", "java", "go", "javascript", "typescript", "csharp", "ruby", "dart"}


@dataclass
class LSPResult:
    """Result from an LSP operation."""
    success: bool
    data: Optional[dict | list] = None
    error: Optional[str] = None


@dataclass
class SymbolLocation:
    """A symbol location in code."""
    file_path: str
    line: int  # 0-indexed
    column: int  # 0-indexed
    end_line: Optional[int] = None
    end_column: Optional[int] = None
    name: Optional[str] = None
    kind: Optional[str] = None
    container: Optional[str] = None


@dataclass
class ProjectState:
    """State of an activated project."""
    root_path: str
    language: str
    server: Optional[SyncLanguageServer] = None
    is_running: bool = False


class LSPManager:
    """
    Manages LSP servers for code intelligence.

    Unlike Serena which uses custom LSP wrappers, we use Microsoft's multilspy
    which handles server binaries, lifecycle, and protocol automatically.
    """

    def __init__(self):
        self._projects: dict[str, ProjectState] = {}
        self._logger = MultilspyLogger()
        # Suppress multilspy's verbose logging
        self._logger.logger.setLevel("WARNING")

    def detect_language(self, project_path: str) -> Optional[str]:
        """Detect primary language of a project."""
        root = Path(project_path)

        # Count files by language
        lang_counts: dict[str, int] = {}
        for ext, lang in EXTENSION_TO_LANGUAGE.items():
            if lang not in SUPPORTED_LANGUAGES:
                continue
            count = len(list(root.rglob(f"*{ext}")))
            if count > 0:
                lang_counts[lang] = lang_counts.get(lang, 0) + count

        if not lang_counts:
            return None

        # Return most common language
        return max(lang_counts, key=lang_counts.get)

    def activate_project(
        self,
        project_path: str,
        language: Optional[str] = None,
    ) -> LSPResult:
        """
        Activate a project and start its language server.

        This is the equivalent of opening a project in an IDE.
        """
        root = Path(project_path).resolve()
        if not root.is_dir():
            return LSPResult(success=False, error=f"Not a directory: {project_path}")

        root_str = str(root)

        # Auto-detect language if not specified
        if not language:
            language = self.detect_language(root_str)
            if not language:
                return LSPResult(
                    success=False,
                    error=f"Could not detect language. Supported: {SUPPORTED_LANGUAGES}"
                )

        if language not in SUPPORTED_LANGUAGES:
            return LSPResult(
                success=False,
                error=f"Unsupported language: {language}. Supported: {SUPPORTED_LANGUAGES}"
            )

        # Check if already activated
        if root_str in self._projects and self._projects[root_str].is_running:
            return LSPResult(
                success=True,
                data={"message": "Project already activated", "language": language}
            )

        # Create and start language server
        try:
            config = MultilspyConfig.from_dict({"code_language": language})
            server = SyncLanguageServer.create(config, self._logger, root_str)

            # Store state (server will be started on first use via context manager)
            self._projects[root_str] = ProjectState(
                root_path=root_str,
                language=language,
                server=server,
                is_running=False,  # Will be set to True when context manager enters
            )

            return LSPResult(
                success=True,
                data={
                    "project": root_str,
                    "language": language,
                    "status": "activated",
                }
            )

        except Exception as e:
            return LSPResult(success=False, error=f"Failed to activate: {e}")

    def deactivate_project(self, project_path: str) -> LSPResult:
        """Stop the language server for a project."""
        root_str = str(Path(project_path).resolve())

        if root_str not in self._projects:
            return LSPResult(success=False, error="Project not activated")

        state = self._projects[root_str]
        if state.server and state.is_running:
            # Server cleanup happens automatically when context exits
            state.is_running = False

        del self._projects[root_str]
        return LSPResult(success=True, data={"message": "Project deactivated"})

    def _get_project(self, file_path: str) -> Optional[ProjectState]:
        """Find the project that contains a file."""
        file_abs = str(Path(file_path).resolve())

        for root, state in self._projects.items():
            if file_abs.startswith(root):
                return state
        return None

    def _ensure_server_running(self, state: ProjectState):
        """Ensure the LSP server is running for a project."""
        if not state.is_running and state.server:
            # The server context manager will be entered
            state.server.__enter__()
            state.is_running = True

    def find_definition(
        self,
        file_path: str,
        line: int,
        column: int,
    ) -> LSPResult:
        """
        Find where a symbol is defined (Go to Definition).

        Args:
            file_path: Path to the file
            line: 0-indexed line number
            column: 0-indexed column number
        """
        state = self._get_project(file_path)
        if not state:
            return LSPResult(success=False, error="File not in an activated project")

        try:
            self._ensure_server_running(state)

            # Get relative path from project root
            rel_path = str(Path(file_path).resolve().relative_to(state.root_path))

            result = state.server.request_definition(rel_path, line, column)

            if not result:
                return LSPResult(success=True, data=[])

            locations = []
            for loc in result:
                locations.append({
                    "file": str(Path(state.root_path) / loc.get("relativePath", "")),
                    "line": loc.get("range", {}).get("start", {}).get("line", 0),
                    "column": loc.get("range", {}).get("start", {}).get("character", 0),
                })

            return LSPResult(success=True, data=locations)

        except Exception as e:
            return LSPResult(success=False, error=f"Definition lookup failed: {e}")

    def find_references(
        self,
        file_path: str,
        line: int,
        column: int,
    ) -> LSPResult:
        """
        Find all references to a symbol.

        This is the killer feature - "who uses this function?"
        """
        state = self._get_project(file_path)
        if not state:
            return LSPResult(success=False, error="File not in an activated project")

        try:
            self._ensure_server_running(state)

            rel_path = str(Path(file_path).resolve().relative_to(state.root_path))
            result = state.server.request_references(rel_path, line, column)

            if not result:
                return LSPResult(success=True, data=[])

            references = []
            for ref in result:
                references.append({
                    "file": str(Path(state.root_path) / ref.get("relativePath", "")),
                    "line": ref.get("range", {}).get("start", {}).get("line", 0),
                    "column": ref.get("range", {}).get("start", {}).get("character", 0),
                })

            return LSPResult(success=True, data=references)

        except Exception as e:
            return LSPResult(success=False, error=f"References lookup failed: {e}")

    def get_document_symbols(self, file_path: str) -> LSPResult:
        """
        Get all symbols defined in a file.

        Returns functions, classes, methods, variables with their locations.
        """
        state = self._get_project(file_path)
        if not state:
            return LSPResult(success=False, error="File not in an activated project")

        try:
            self._ensure_server_running(state)

            rel_path = str(Path(file_path).resolve().relative_to(state.root_path))
            result = state.server.request_document_symbols(rel_path)

            if not result:
                return LSPResult(success=True, data=[])

            symbols = self._flatten_symbols(result, file_path)
            return LSPResult(success=True, data=symbols)

        except Exception as e:
            return LSPResult(success=False, error=f"Document symbols failed: {e}")

    def _flatten_symbols(
        self,
        symbols: list,
        file_path: str,
        parent: Optional[str] = None,
    ) -> list[dict]:
        """Flatten nested document symbols into a list."""
        result = []

        for sym in symbols:
            # LSP SymbolKind enum
            kind_map = {
                1: "file", 2: "module", 3: "namespace", 4: "package",
                5: "class", 6: "method", 7: "property", 8: "field",
                9: "constructor", 10: "enum", 11: "interface", 12: "function",
                13: "variable", 14: "constant", 15: "string", 16: "number",
                17: "boolean", 18: "array", 19: "object", 20: "key",
                21: "null", 22: "enum_member", 23: "struct", 24: "event",
                25: "operator", 26: "type_parameter",
            }

            kind_num = sym.get("kind", 0)
            kind = kind_map.get(kind_num, f"unknown({kind_num})")

            range_info = sym.get("range", sym.get("location", {}).get("range", {}))
            start = range_info.get("start", {})
            end = range_info.get("end", {})

            result.append({
                "name": sym.get("name", ""),
                "kind": kind,
                "file": file_path,
                "start_line": start.get("line", 0),
                "start_column": start.get("character", 0),
                "end_line": end.get("line", 0),
                "end_column": end.get("character", 0),
                "parent": parent,
            })

            # Recurse into children
            children = sym.get("children", [])
            if children:
                result.extend(self._flatten_symbols(children, file_path, sym.get("name")))

        return result

    def workspace_symbol_search(
        self,
        query: str,
        project_path: Optional[str] = None,
    ) -> LSPResult:
        """
        Search for symbols across the workspace by name.

        This is how you find "where is authenticate_user defined?"
        """
        # Find the project
        if project_path:
            root_str = str(Path(project_path).resolve())
            state = self._projects.get(root_str)
        else:
            # Use first activated project
            if not self._projects:
                return LSPResult(success=False, error="No project activated")
            state = list(self._projects.values())[0]

        if not state:
            return LSPResult(success=False, error="Project not found")

        try:
            self._ensure_server_running(state)

            # multilspy's workspace symbol search
            result = state.server.request_workspace_symbols(query)

            if not result:
                return LSPResult(success=True, data=[])

            symbols = []
            for sym in result:
                loc = sym.get("location", {})
                range_info = loc.get("range", {})
                start = range_info.get("start", {})

                symbols.append({
                    "name": sym.get("name", ""),
                    "kind": sym.get("kind", 0),
                    "file": loc.get("uri", "").replace("file://", ""),
                    "line": start.get("line", 0),
                    "column": start.get("character", 0),
                    "container": sym.get("containerName"),
                })

            return LSPResult(success=True, data=symbols)

        except Exception as e:
            return LSPResult(success=False, error=f"Workspace symbol search failed: {e}")

    def hover(
        self,
        file_path: str,
        line: int,
        column: int,
    ) -> LSPResult:
        """
        Get hover information (type info, documentation) for a symbol.
        """
        state = self._get_project(file_path)
        if not state:
            return LSPResult(success=False, error="File not in an activated project")

        try:
            self._ensure_server_running(state)

            rel_path = str(Path(file_path).resolve().relative_to(state.root_path))
            result = state.server.request_hover(rel_path, line, column)

            if not result:
                return LSPResult(success=True, data=None)

            # Extract hover content
            contents = result.get("contents", {})
            if isinstance(contents, dict):
                text = contents.get("value", "")
            elif isinstance(contents, list):
                text = "\n".join(c.get("value", str(c)) if isinstance(c, dict) else str(c) for c in contents)
            else:
                text = str(contents)

            return LSPResult(success=True, data={"content": text})

        except Exception as e:
            return LSPResult(success=False, error=f"Hover failed: {e}")

    def get_completions(
        self,
        file_path: str,
        line: int,
        column: int,
    ) -> LSPResult:
        """Get code completions at a position."""
        state = self._get_project(file_path)
        if not state:
            return LSPResult(success=False, error="File not in an activated project")

        try:
            self._ensure_server_running(state)

            rel_path = str(Path(file_path).resolve().relative_to(state.root_path))
            result = state.server.request_completions(rel_path, line, column)

            if not result:
                return LSPResult(success=True, data=[])

            completions = []
            items = result.get("items", result) if isinstance(result, dict) else result

            for item in items[:50]:  # Limit results
                completions.append({
                    "label": item.get("label", ""),
                    "kind": item.get("kind", 0),
                    "detail": item.get("detail", ""),
                    "documentation": item.get("documentation", ""),
                })

            return LSPResult(success=True, data=completions)

        except Exception as e:
            return LSPResult(success=False, error=f"Completions failed: {e}")

    def health_check(self) -> dict:
        """
        Get status of all LSP servers.

        Useful for debugging "why isn't this working?"
        """
        return {
            "active_projects": [
                {
                    "path": state.root_path,
                    "language": state.language,
                    "server_running": state.is_running,
                }
                for state in self._projects.values()
            ],
            "supported_languages": list(SUPPORTED_LANGUAGES),
        }

    def shutdown(self):
        """Shutdown all language servers."""
        for root_str, state in list(self._projects.items()):
            if state.server and state.is_running:
                try:
                    state.server.__exit__(None, None, None)
                except Exception:
                    pass
            state.is_running = False
        self._projects.clear()


# Global LSP manager instance
_lsp_manager: Optional[LSPManager] = None


def get_lsp_manager() -> LSPManager:
    """Get the global LSP manager instance."""
    global _lsp_manager
    if _lsp_manager is None:
        _lsp_manager = LSPManager()
    return _lsp_manager
