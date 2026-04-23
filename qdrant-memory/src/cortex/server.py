"""MCP server - Thin shim over skills.

Exposes 4 memory tools + doctor.
All logic lives in skills; this is just the MCP interface.
"""

import sys
from typing import List, Optional

from mcp.server.fastmcp import FastMCP

from .harness.router import get_router


# Initialize FastMCP server
mcp = FastMCP(name="Cortex")


# =============================================================================
# GOLDEN PATH TOOLS (4 memory tools + doctor)
# =============================================================================

@mcp.tool()
def remember(
    kind: str,
    text: str,
    tags: List[str] = [],
    ttl_days: Optional[int] = None,
) -> dict:
    """
    Store a coding memory.

    Kinds:
    - episode: What happened (errors hit, solutions found, commands run)
    - fact: Stable knowledge (conventions, constraints, architecture)
    - recipe: How-to instructions (build, deploy, test)

    Git commit and branch are automatically captured.

    Args:
        kind: "episode", "fact", or "recipe"
        text: Memory content
        tags: Optional tags for categorization
        ttl_days: Time-to-live in days (uses defaults if not specified)

    Returns:
        {"success": bool, "id": str} or {"success": false, "error": str}
    """
    router = get_router()
    return router.handle("remember", {
        "kind": kind,
        "text": text,
        "tags": tags,
        "ttl_days": ttl_days,
    })


@mcp.tool()
def recall(
    query: str,
    kinds: Optional[List[str]] = None,
    tags: Optional[List[str]] = None,
    since_days: Optional[int] = None,
    limit: int = 8,
) -> dict:
    """
    Search for relevant memories.

    Returns memories matching the query, ranked by:
    - Semantic similarity to query
    - Freshness (newer = higher)
    - Verified status (verified = boosted)
    - Query-type fit (bug queries prefer episodes, how-to queries prefer recipes)

    Args:
        query: Natural language query (min 2 chars)
        kinds: Filter by memory types (episode, fact, recipe)
        tags: Filter by tags
        since_days: Only memories from last N days
        limit: Max results (default 8)

    Returns:
        {"success": bool, "memories": list, "count": int}
    """
    router = get_router()
    return router.handle("recall", {
        "query": query,
        "kinds": kinds,
        "tags": tags,
        "since_days": since_days,
        "limit": limit,
    })


@mcp.tool()
def list_recent(
    kind: Optional[str] = None,
    limit: int = 20,
) -> dict:
    """
    List recent memories by creation time.

    Args:
        kind: Filter by memory type (episode, fact, recipe)
        limit: Max results (default 20, max 100)

    Returns:
        {"success": bool, "memories": list, "count": int}
    """
    router = get_router()
    return router.handle("list_recent", {
        "kind": kind,
        "limit": limit,
    })


@mcp.tool()
def delete(memory_id: str) -> dict:
    """
    Delete a memory by ID.

    Args:
        memory_id: UUID of memory to delete

    Returns:
        {"success": bool, "deleted_id": str} or {"success": false, "error": str}
    """
    router = get_router()
    return router.handle("delete", {
        "memory_id": memory_id,
    })


@mcp.tool()
def doctor() -> dict:
    """
    Comprehensive system diagnostic.

    Checks:
    - QDRANT_URL environment variable
    - Store connectivity
    - Embedder health
    - Repo detection

    Use when something isn't working.

    Returns:
        Diagnostic report with pass/fail for each check.
    """
    router = get_router()
    return router.handle("doctor", {})


# =============================================================================
# ENTRY POINT
# =============================================================================

def main() -> None:
    """Entry point for the MCP server."""
    try:
        mcp.run()
    except Exception as e:
        print(f"[cortex] fatal: {e}", file=sys.stderr)
        raise


if __name__ == "__main__":
    main()
