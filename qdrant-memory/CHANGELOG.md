# Changelog

All notable changes to Cortex will be documented in this file.

## [0.4.0] - 2025-01-XX

### Added
- **Skills + Harness Architecture**: Refactored into modular skills (LSP, Search, Memory, Index, Edit) with central router
- **Symbol-level editing**: `replace_symbol`, `insert_after_symbol`, `get_symbol` tools for precise code modifications
- **Project state folder** (`.qci/`): On-disk config, state, and logs per project
- **Docker support**: Dockerfile and docker-compose.yml with Qdrant included
- **Initializer**: `qdrant-coding-memory init` command to bootstrap projects
- **Serena-style CLI**: `start-mcp-server --project --context` pattern

### Changed
- Reduced tool surface from 23 to 18 (golden path + advanced)
- Server is now a thin MCP layer over the harness router
- All tools go through policy enforcement

## [0.3.0] - 2025-01-XX

### Added
- **LSP Integration**: Full Language Server Protocol support via multilspy
- **Golden path tools**: `bootstrap()`, `find()`, `where_is()`, `who_calls()`, `doctor()`
- **Safety controls**: `READ_ONLY_MODE`, `PATH_ALLOWLIST`, `PATH_DENYLIST`
- **Scoped filters**: `path_prefix` for directory-scoped searches
- **Tree-sitter parsing**: Fallback symbol extraction for 8 languages

### Changed
- Renamed from "qdrant-coding-memory" to "Cortex"

## [0.2.0] - 2025-01-XX

### Added
- **Hybrid search**: Dense (semantic) + Sparse (BM25) with RRF fusion
- **Code indexing**: `code_index_project`, `code_index_file`
- **Symbol search**: `code_find_symbol`, `code_get_file_symbols`
- Payload filtering by language, symbol_kind, file_path

## [0.1.0] - 2025-01-XX

### Added
- Initial release
- **Memory system**: `memory_remember`, `memory_recall`, `memory_list_recent`, `memory_delete`
- Memory types: episode, fact, recipe
- TTL support for memory expiration
- Git provenance tracking (commit, branch)
- Secret detection policy
