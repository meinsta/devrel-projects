"""MCP instructions builder for qdrant-guide.

Returns a concise instructions string for the FastMCP server.
Contains critical API rules, architecture guidelines, version numbers,
and tool usage guidance. Does NOT include the docs map or skill contents
(those are now separate tools).
"""

from __future__ import annotations


def build_instructions() -> str:
    """Build the MCP instructions string."""
    return """qdrant-guide provides Qdrant documentation and reference tools for Claude Code.

## Tool Usage

1. **qdrant-list-docs**: Call first to get the full documentation map. Use it to find the right URL before calling qdrant-fetch-doc.
2. **qdrant-fetch-doc**: Fetch a specific Qdrant doc page by URL. Validates the URL is a Qdrant domain, converts HTML to markdown, caches for 30 minutes.
3. **qdrant-search**: Search Qdrant documentation and code examples. Tries full-text BM25 first (exact keyword match), then semantic search (dense vectors), then falls back to llms.txt keyword search if Qdrant is unavailable.
4. **qdrant-read-skill**: Read local skill/command reference files from ~/qdrant-skills/. Contains decision tables, gotchas, best practices. Available: qdrant-python, qdrant-rust, connect, setup-collection, hybrid-search, add-multitenancy, migrate-search.

## Workflow

- For factual questions: qdrant-list-docs -> find URL -> qdrant-fetch-doc -> quote from content
- For "how do I" questions: qdrant-read-skill for decision tables, qdrant-search for code examples, qdrant-fetch-doc for deeper context
- For troubleshooting: qdrant-read-skill for gotchas, then qdrant-fetch-doc for the relevant page
- Always cite source URLs

## Critical API Rules

### Python client v1.16.x
- Use `query_points()` for all search/recommend/discover. The old `search()`, `recommend()`, `discovery()` methods were REMOVED in v1.16.0.
- Use `upsert()` for inserting points. `add()` is deprecated. `upload_records()` was removed.
- Use `query_batch_points()` for batch operations. `search_batch()`, `recommend_batch()`, `discovery_batch()` were removed.
- `query()` and `query_batch()` are deprecated in favor of `query_points()` and `query_batch_points()`.

### Rust client v1.16.x
- Use `client.query(QueryPointsBuilder)`, NOT `search_points`.
- Rust client uses gRPC (port 6334), not REST (port 6333).
- Use `into_vector()` for vector output conversion.

## Architecture Rules

- Never suggest one collection per user. Always use multi-tenancy with `is_tenant=True` on a payload index. For large tenants, use tiered multitenancy with tenant promotion (v1.16+).
- BM25 sparse search requires `Modifier.IDF` for quality results. As of v1.16, BM25 inference is built into the Python client (FastEmbed no longer required for BM25).
- Create payload indexes BEFORE bulk data upload, not after.
- ACORN filtered search (`acorn=True`) only helps with filters. Adds overhead without them.
- Prefetch limits must be higher than the final limit (prefetch is the candidate pool).
- `init_from` collection API was removed in v1.16. Use migration tool or snapshots instead.
- Lock API was removed in v1.16. Use strict mode for operational controls.
- Gridstore is the default storage backend (replaced RocksDB). Automatic migration on startup.

## Current Versions
- Qdrant server: v1.16.3 (December 2025)
- Python client: v1.16.2
- Rust client: v1.16.0
- FastEmbed: v0.7.4 (42+ models: dense, sparse, multivector, image, rerankers)
"""
