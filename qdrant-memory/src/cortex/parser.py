"""Tree-sitter based code parser for symbol extraction."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import tree_sitter_python
import tree_sitter_javascript
import tree_sitter_typescript
import tree_sitter_rust
import tree_sitter_go
import tree_sitter_java
import tree_sitter_c
import tree_sitter_cpp
from tree_sitter import Language, Parser, Node


@dataclass
class Symbol:
    """Represents an extracted code symbol."""
    kind: str  # function, class, method, variable, etc.
    name: str
    content: str
    start_line: int
    end_line: int
    start_byte: int
    end_byte: int
    parent: Optional[str] = None
    docstring: Optional[str] = None
    signature: Optional[str] = None
    children: list["Symbol"] = field(default_factory=list)


# Language configurations
LANGUAGE_CONFIG = {
    "python": {
        "language": Language(tree_sitter_python.language()),
        "extensions": [".py", ".pyi"],
        "symbol_queries": {
            "function": "(function_definition name: (identifier) @name) @func",
            "class": "(class_definition name: (identifier) @name) @class",
            "method": "(function_definition name: (identifier) @name) @method",
            "variable": "(assignment left: (identifier) @name) @var",
        },
    },
    "javascript": {
        "language": Language(tree_sitter_javascript.language()),
        "extensions": [".js", ".jsx", ".mjs", ".cjs"],
        "symbol_queries": {
            "function": "(function_declaration name: (identifier) @name) @func",
            "class": "(class_declaration name: (identifier) @name) @class",
            "variable": "(variable_declarator name: (identifier) @name) @var",
            "arrow_function": "(arrow_function) @arrow",
        },
    },
    "typescript": {
        "language": Language(tree_sitter_typescript.language_typescript()),
        "extensions": [".ts"],
        "symbol_queries": {
            "function": "(function_declaration name: (identifier) @name) @func",
            "class": "(class_declaration name: (identifier) @name) @class",
            "interface": "(interface_declaration name: (type_identifier) @name) @interface",
            "type": "(type_alias_declaration name: (type_identifier) @name) @type",
        },
    },
    "tsx": {
        "language": Language(tree_sitter_typescript.language_tsx()),
        "extensions": [".tsx"],
        "symbol_queries": {
            "function": "(function_declaration name: (identifier) @name) @func",
            "class": "(class_declaration name: (identifier) @name) @class",
            "interface": "(interface_declaration name: (type_identifier) @name) @interface",
        },
    },
    "rust": {
        "language": Language(tree_sitter_rust.language()),
        "extensions": [".rs"],
        "symbol_queries": {
            "function": "(function_item name: (identifier) @name) @func",
            "struct": "(struct_item name: (type_identifier) @name) @struct",
            "enum": "(enum_item name: (type_identifier) @name) @enum",
            "impl": "(impl_item) @impl",
            "trait": "(trait_item name: (type_identifier) @name) @trait",
        },
    },
    "go": {
        "language": Language(tree_sitter_go.language()),
        "extensions": [".go"],
        "symbol_queries": {
            "function": "(function_declaration name: (identifier) @name) @func",
            "method": "(method_declaration name: (field_identifier) @name) @method",
            "struct": "(type_declaration (type_spec name: (type_identifier) @name)) @struct",
            "interface": "(type_declaration (type_spec name: (type_identifier) @name type: (interface_type))) @interface",
        },
    },
    "java": {
        "language": Language(tree_sitter_java.language()),
        "extensions": [".java"],
        "symbol_queries": {
            "class": "(class_declaration name: (identifier) @name) @class",
            "method": "(method_declaration name: (identifier) @name) @method",
            "interface": "(interface_declaration name: (identifier) @name) @interface",
        },
    },
    "c": {
        "language": Language(tree_sitter_c.language()),
        "extensions": [".c", ".h"],
        "symbol_queries": {
            "function": "(function_definition declarator: (function_declarator declarator: (identifier) @name)) @func",
            "struct": "(struct_specifier name: (type_identifier) @name) @struct",
        },
    },
    "cpp": {
        "language": Language(tree_sitter_cpp.language()),
        "extensions": [".cpp", ".cc", ".cxx", ".hpp", ".hxx", ".h"],
        "symbol_queries": {
            "function": "(function_definition declarator: (function_declarator declarator: (identifier) @name)) @func",
            "class": "(class_specifier name: (type_identifier) @name) @class",
            "struct": "(struct_specifier name: (type_identifier) @name) @struct",
        },
    },
}

# Extension to language mapping
EXT_TO_LANG = {}
for lang, config in LANGUAGE_CONFIG.items():
    for ext in config["extensions"]:
        EXT_TO_LANG[ext] = lang


class CodeParser:
    """Parse code files and extract symbols using tree-sitter."""

    def __init__(self):
        self._parsers: dict[str, Parser] = {}

    def _get_parser(self, language: str) -> Optional[Parser]:
        """Get or create a parser for the given language."""
        if language not in LANGUAGE_CONFIG:
            return None

        if language not in self._parsers:
            parser = Parser()
            parser.language = LANGUAGE_CONFIG[language]["language"]
            self._parsers[language] = parser

        return self._parsers[language]

    def detect_language(self, file_path: str) -> Optional[str]:
        """Detect language from file extension."""
        ext = Path(file_path).suffix.lower()
        return EXT_TO_LANG.get(ext)

    def parse_file(self, file_path: str, content: Optional[str] = None) -> list[Symbol]:
        """
        Parse a file and extract all symbols.

        Args:
            file_path: Path to the file
            content: Optional file content (will read from disk if not provided)

        Returns:
            List of extracted symbols
        """
        language = self.detect_language(file_path)
        if not language:
            return []

        if content is None:
            try:
                content = Path(file_path).read_text(encoding="utf-8")
            except Exception:
                return []

        parser = self._get_parser(language)
        if not parser:
            return []

        tree = parser.parse(content.encode("utf-8"))
        return self._extract_symbols(tree.root_node, content, language)

    def _extract_symbols(
        self,
        root: Node,
        content: str,
        language: str,
        parent_name: Optional[str] = None,
    ) -> list[Symbol]:
        """Recursively extract symbols from AST."""
        symbols = []
        lines = content.split("\n")

        def visit(node: Node, parent: Optional[str] = None):
            symbol = self._node_to_symbol(node, content, lines, language, parent)
            if symbol:
                symbols.append(symbol)
                # For classes, extract methods as children
                if symbol.kind in ("class", "struct", "impl"):
                    for child in node.children:
                        visit(child, symbol.name)
            else:
                # Continue traversing
                for child in node.children:
                    visit(child, parent)

        visit(root, parent_name)
        return symbols

    def _node_to_symbol(
        self,
        node: Node,
        content: str,
        lines: list[str],
        language: str,
        parent: Optional[str],
    ) -> Optional[Symbol]:
        """Convert a tree-sitter node to a Symbol if it's a recognized type."""
        kind = self._get_symbol_kind(node, language)
        if not kind:
            return None

        name = self._extract_name(node, language)
        if not name and kind not in ("file",):
            return None

        # Extract content
        start_byte = node.start_byte
        end_byte = node.end_byte
        symbol_content = content[start_byte:end_byte]

        # Extract docstring (look for preceding comment/string)
        docstring = self._extract_docstring(node, content, language)

        # Extract signature (first line for functions/methods)
        signature = None
        if kind in ("function", "method"):
            signature = self._extract_signature(node, content, language)

        return Symbol(
            kind=kind,
            name=name or "",
            content=symbol_content,
            start_line=node.start_point[0] + 1,  # 1-indexed
            end_line=node.end_point[0] + 1,
            start_byte=start_byte,
            end_byte=end_byte,
            parent=parent,
            docstring=docstring,
            signature=signature,
        )

    def _get_symbol_kind(self, node: Node, language: str) -> Optional[str]:
        """Map tree-sitter node type to symbol kind."""
        type_mapping = {
            # Python
            "function_definition": "function",
            "class_definition": "class",
            "decorated_definition": None,  # Will be handled by child
            # JavaScript/TypeScript
            "function_declaration": "function",
            "class_declaration": "class",
            "method_definition": "method",
            "interface_declaration": "interface",
            "type_alias_declaration": "type",
            # Rust
            "function_item": "function",
            "struct_item": "struct",
            "enum_item": "enum",
            "impl_item": "impl",
            "trait_item": "interface",
            # Go
            "method_declaration": "method",
            "type_declaration": "type",
            # Java
            "method_declaration": "method",
            # C/C++
            "function_definition": "function",
            "class_specifier": "class",
            "struct_specifier": "struct",
        }
        return type_mapping.get(node.type)

    def _extract_name(self, node: Node, language: str) -> Optional[str]:
        """Extract the name of a symbol from its AST node."""
        # Look for name child
        for child in node.children:
            if child.type in ("identifier", "type_identifier", "field_identifier"):
                return child.text.decode("utf-8")
            if child.type == "name":
                return child.text.decode("utf-8")
            # For function declarators (C/C++)
            if child.type == "declarator":
                return self._extract_name(child, language)
            if child.type == "function_declarator":
                return self._extract_name(child, language)
        return None

    def _extract_docstring(
        self, node: Node, content: str, language: str
    ) -> Optional[str]:
        """Extract docstring/comment preceding the symbol."""
        # Look for preceding sibling that's a comment or string
        if node.prev_sibling:
            prev = node.prev_sibling
            if prev.type in ("comment", "string", "expression_statement"):
                text = content[prev.start_byte:prev.end_byte].strip()
                # Clean up docstring markers
                for marker in ['"""', "'''", "//", "/*", "*/", "#"]:
                    text = text.strip(marker)
                return text.strip()[:500]  # Limit length

        # For Python, check first child (docstring inside function)
        if language == "python" and node.children:
            for child in node.children:
                if child.type == "block":
                    for block_child in child.children:
                        if block_child.type == "expression_statement":
                            expr = block_child.children[0] if block_child.children else None
                            if expr and expr.type == "string":
                                text = content[expr.start_byte:expr.end_byte]
                                for marker in ['"""', "'''"]:
                                    text = text.strip(marker)
                                return text.strip()[:500]
                    break
        return None

    def _extract_signature(
        self, node: Node, content: str, language: str
    ) -> Optional[str]:
        """Extract function/method signature."""
        # Get text up to the body/block
        for child in node.children:
            if child.type in ("block", "compound_statement", "declaration_list", "{"):
                sig = content[node.start_byte:child.start_byte].strip()
                # Clean up and limit
                sig = " ".join(sig.split())[:200]
                return sig
        # Fallback: first line
        text = content[node.start_byte:node.end_byte]
        first_line = text.split("\n")[0].strip()
        return first_line[:200]

    def chunk_file(
        self,
        file_path: str,
        content: Optional[str] = None,
        max_chunk_size: int = 2000,
    ) -> list[Symbol]:
        """
        Parse file and return chunks suitable for indexing.

        For small files, returns the whole file as one chunk.
        For larger files, returns individual functions/classes.
        Falls back to line-based chunking for unsupported languages.
        """
        if content is None:
            try:
                content = Path(file_path).read_text(encoding="utf-8")
            except Exception:
                return []

        language = self.detect_language(file_path)

        # If unsupported language or parse fails, use line-based chunking
        if not language:
            return self._chunk_by_lines(file_path, content, max_chunk_size)

        symbols = self.parse_file(file_path, content)

        # If no symbols found, chunk the whole file
        if not symbols:
            return self._chunk_by_lines(file_path, content, max_chunk_size)

        # Filter to top-level symbols (functions, classes)
        top_level = [s for s in symbols if s.kind in ("function", "class", "struct", "interface", "method", "impl", "type")]

        # If still too few, return whole file
        if len(top_level) < 2 and len(content) < max_chunk_size:
            return [Symbol(
                kind="file",
                name=Path(file_path).name,
                content=content,
                start_line=1,
                end_line=len(content.split("\n")),
                start_byte=0,
                end_byte=len(content),
            )]

        return top_level if top_level else self._chunk_by_lines(file_path, content, max_chunk_size)

    def _chunk_by_lines(
        self,
        file_path: str,
        content: str,
        max_chunk_size: int,
    ) -> list[Symbol]:
        """Fallback: chunk by lines for unsupported languages."""
        lines = content.split("\n")
        chunks = []
        current_chunk = []
        current_size = 0
        start_line = 1

        for i, line in enumerate(lines, 1):
            line_size = len(line) + 1  # +1 for newline
            if current_size + line_size > max_chunk_size and current_chunk:
                chunks.append(Symbol(
                    kind="file",
                    name=f"{Path(file_path).name}:{start_line}-{i-1}",
                    content="\n".join(current_chunk),
                    start_line=start_line,
                    end_line=i - 1,
                    start_byte=0,  # Approximate
                    end_byte=current_size,
                ))
                current_chunk = [line]
                current_size = line_size
                start_line = i
            else:
                current_chunk.append(line)
                current_size += line_size

        # Don't forget the last chunk
        if current_chunk:
            chunks.append(Symbol(
                kind="file",
                name=f"{Path(file_path).name}:{start_line}-{len(lines)}",
                content="\n".join(current_chunk),
                start_line=start_line,
                end_line=len(lines),
                start_byte=0,
                end_byte=current_size,
            ))

        return chunks


# Global parser instance
_parser: Optional[CodeParser] = None


def get_parser() -> CodeParser:
    """Get the global parser instance."""
    global _parser
    if _parser is None:
        _parser = CodeParser()
    return _parser
