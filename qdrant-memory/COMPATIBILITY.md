# Cortex Compatibility Matrix

## Supported Platforms

| Platform | Status | Notes |
|----------|--------|-------|
| macOS (Apple Silicon) | ✅ Tested | Primary dev platform |
| macOS (Intel) | ✅ Should work | Not actively tested |
| Linux (x86_64) | ✅ Should work | Docker tested |
| Windows | ⚠️ Partial | Use WSL2 for best results |

## Python Versions

| Version | Status |
|---------|--------|
| 3.13 | ✅ Supported |
| 3.12 | ✅ Supported |
| 3.11 | ✅ Supported (minimum) |
| 3.10 | ❌ Not supported |

## Qdrant Versions

| Version | Status |
|---------|--------|
| 1.12+ | ✅ Supported |
| 1.9-1.11 | ⚠️ Should work |
| < 1.9 | ❌ Not supported (missing sparse vectors) |

## Language Server Support (LSP)

LSP features require language servers to be installed. We use [multilspy](https://github.com/microsoft/multilspy) which auto-manages servers.

| Language | Server | Status | Notes |
|----------|--------|--------|-------|
| Python | Pyright | ✅ Full | Best supported |
| TypeScript | tsserver | ✅ Full | |
| JavaScript | tsserver | ✅ Full | |
| Rust | rust-analyzer | ✅ Full | |
| Go | gopls | ✅ Full | |
| Java | jdtls | ✅ Full | Requires JDK |
| C# | OmniSharp | ⚠️ Partial | |
| Ruby | Solargraph | ⚠️ Partial | |
| Dart | dart | ⚠️ Partial | |

## Tree-sitter Support (Indexing Fallback)

When LSP isn't available, we use tree-sitter for symbol extraction.

| Language | Status |
|----------|--------|
| Python | ✅ Full |
| TypeScript | ✅ Full |
| JavaScript | ✅ Full |
| Rust | ✅ Full |
| Go | ✅ Full |
| Java | ✅ Full |
| C | ✅ Full |
| C++ | ✅ Full |

## MCP Client Compatibility

| Client | Status | Notes |
|--------|--------|-------|
| Claude Code | ✅ Full | Primary target |
| Claude Desktop | ✅ Should work | Use stdio transport |
| Cursor | ⚠️ Untested | Should work via MCP |
| VS Code + Continue | ⚠️ Untested | |

## Known Issues

### Windows
- Path handling may have issues with backslashes
- Some LSP servers have Windows-specific quirks
- **Workaround**: Use WSL2

### Large Repositories
- Initial indexing can be slow for repos with 10k+ files
- **Workaround**: Use `.gitignore` patterns in `.qci/config.yaml`

### Memory Usage
- Embedding models load ~500MB into memory
- Each LSP server adds ~100-300MB
- **Workaround**: Deactivate LSP when not needed

## Reporting Issues

If you encounter compatibility issues:

1. Run `doctor()` and include the output
2. Include your OS, Python version, and Qdrant version
3. Open an issue at: https://github.com/thierrydamiba/cortex/issues
