"""MCP server entry point for qdrant-guide.

Follows the mcp-code-snippets pattern: FastMCP instance at module level,
tools defined with @mcp.tool() decorators, mcp.run() in __main__.
"""

import os
from pathlib import Path
from typing import Annotated, Optional

from fastmcp import FastMCP
from mcp.types import TextContent
from pydantic import Field

from qdrant_guide.config import (
    ALLOWED_DOC_PREFIXES,
    BUNDLED_SHARD_ARCHIVE,
    EMBEDDING_DIM,
    EMBEDDING_MODEL,
    SHARD_DIR,
    SKILL_FILE_MAP,
)
from qdrant_guide.doc_cache import DocCache
from qdrant_guide.prompt import build_instructions

# Module-level instances
mcp = FastMCP(name="qdrant-guide", instructions=build_instructions())
_doc_cache = DocCache()
_DOCS_MAP_PATH = Path(__file__).parent / "qdrant_docs_map.md"

# Lazy-loaded resources
_embedding_model = None
_edge_shard = None


def _get_embedding_model():
    """Lazy-load jina-code embedding model on first use."""
    global _embedding_model
    if _embedding_model is None:
        from fastembed import TextEmbedding

        _embedding_model = TextEmbedding(EMBEDDING_MODEL)
    return _embedding_model


def _ensure_shard_extracted():
    """Extract the bundled shard archive if no local shard exists."""
    if SHARD_DIR.exists():
        return
    if not BUNDLED_SHARD_ARCHIVE.exists():
        return

    import tarfile

    SHARD_DIR.mkdir(parents=True, exist_ok=True)
    with tarfile.open(BUNDLED_SHARD_ARCHIVE, "r:gz") as tar:
        members = [
            m for m in tar.getmembers()
            if not os.path.basename(m.name).startswith("._")
        ]
        tar.extractall(SHARD_DIR, members=members)


def _get_edge_shard():
    """Lazy-load the local qdrant-edge shard on first use."""
    global _edge_shard
    if _edge_shard is None:
        _ensure_shard_extracted()
        if not SHARD_DIR.exists():
            return None
        from qdrant_edge import EdgeShard

        _edge_shard = EdgeShard(str(SHARD_DIR))
    return _edge_shard


# ---------------------------------------------------------------------------
# Tool 1: qdrant-list-docs
# ---------------------------------------------------------------------------

@mcp.tool(
    name="qdrant-list-docs",
    description=(
        "List all Qdrant documentation pages with URLs and descriptions. "
        "Call this first to find the right URL before using qdrant-fetch-doc."
    ),
)
async def list_docs() -> list[TextContent]:
    """Return the full qdrant_docs_map.md content."""
    try:
        content = _DOCS_MAP_PATH.read_text()
    except FileNotFoundError:
        return [TextContent(
            type="text",
            text="Error: qdrant_docs_map.md not found. Package may be installed incorrectly.",
        )]
    return [TextContent(type="text", text=content)]


# ---------------------------------------------------------------------------
# Tool 2: qdrant-fetch-doc
# ---------------------------------------------------------------------------

@mcp.tool(
    name="qdrant-fetch-doc",
    description=(
        "Fetch a specific Qdrant documentation page by URL and return it as "
        "markdown. Use qdrant-list-docs first to find the right URL."
    ),
)
async def fetch_doc(
    url: Annotated[
        str,
        Field(
            description=(
                "Full URL of the Qdrant doc page, e.g. "
                "https://qdrant.tech/documentation/concepts/search/"
            )
        ),
    ],
) -> list[TextContent]:
    """Fetch a Qdrant doc page, validate URL, convert HTML to markdown."""
    if not url.startswith(ALLOWED_DOC_PREFIXES):
        return [TextContent(
            type="text",
            text=(
                f"Error: URL must be a Qdrant documentation URL "
                f"(qdrant.tech, python-client.qdrant.tech, or "
                f"docs.rs/qdrant-client). Got: {url}"
            ),
        )]

    try:
        content = await _doc_cache.fetch_page(url)
    except Exception as exc:
        return [TextContent(type="text", text=f"Error fetching {url}: {exc}")]

    return [TextContent(type="text", text=f"# Content from {url}\n\n{content}")]


# ---------------------------------------------------------------------------
# Tool 3: qdrant-search
# ---------------------------------------------------------------------------

@mcp.tool(
    name="qdrant-search",
    description=(
        "Search Qdrant documentation and code examples using a local vector "
        "index. Tries keyword-filtered semantic search first, then pure "
        "semantic search, then falls back to llms.txt keyword search if no "
        "index is built. Use the language filter to scope results to a "
        "specific client library (python, rust, go, java, typescript, dotnet)."
    ),
)
async def search(
    query: Annotated[
        str,
        Field(description="Search query for Qdrant documentation"),
    ],
    language: Annotated[
        Optional[str],
        Field(
            default=None,
            description=(
                "Filter results by client language: python, rust, go, java, "
                "typescript, dotnet. Omit for general Qdrant docs."
            ),
        ),
    ] = None,
) -> list[TextContent]:
    """Search: keyword-filtered semantic -> pure semantic -> llms.txt fallback."""
    shard = _get_edge_shard()
    if shard is None:
        return await _fallback_llms_search(
            query, error="No local index. Run: qdrant-guide --rebuild-index"
        )

    try:
        from qdrant_edge import (
            FieldCondition,
            Filter,
            MatchText,
            MatchValue,
            Query,
            QueryRequest,
        )

        model = _get_embedding_model()
        query_vector = list(model.embed([query]))[0].tolist()

        # Build language filter conditions if specified
        lang_conditions = []
        if language:
            lang_conditions.append(
                FieldCondition(key="language", match=MatchValue(value=language))
            )

        # Step 1: keyword-filtered semantic search
        try:
            keyword_conditions = [
                FieldCondition(key="content", match=MatchText(text=query))
            ] + lang_conditions
            filtered_results = shard.query(QueryRequest(
                query=Query.Nearest(query_vector, using="dense"),
                filter=Filter(must=keyword_conditions),
                limit=5,
                with_payload=True,
            ))
        except Exception:
            filtered_results = []

        if filtered_results:
            return _format_results(filtered_results, query, method="keyword+semantic")

        # Step 2: semantic search (with language filter if specified)
        lang_filter = Filter(must=lang_conditions) if lang_conditions else None
        semantic_results = shard.query(QueryRequest(
            query=Query.Nearest(query_vector, using="dense"),
            filter=lang_filter,
            limit=5,
            with_payload=True,
        ))

        if semantic_results:
            return _format_results(semantic_results, query, method="semantic")

        return [TextContent(
            type="text",
            text=f"No results for '{query}' in local index.",
        )]

    except Exception as exc:
        return await _fallback_llms_search(query, error=str(exc))


def _format_results(points, query_text: str, method: str) -> list[TextContent]:
    """Format edge shard search results into tool output."""
    formatted = []
    for point in points:
        payload = point.payload or {}
        content = payload.get("content", "")
        source = payload.get("source", "unknown")
        title = payload.get("title", "")
        score = f" (score: {point.score:.3f})" if point.score else ""

        header = f"**{title}**\n" if title else ""
        formatted.append(f"{header}{content}\nSource: {source}{score}")

    text = (
        f"Search results for '{query_text}' ({method}):\n\n"
        + "\n\n---\n\n".join(formatted)
    )
    return [TextContent(type="text", text=text)]


async def _fallback_llms_search(
    query_text: str, error: Optional[str] = None
) -> list[TextContent]:
    """Fall back to keyword search over the llms.txt doc index."""
    llms_txt = await _doc_cache.fetch_llms_txt()
    query_lower = query_text.lower()

    matches = []
    for line in llms_txt.splitlines():
        stripped = line.strip()
        if stripped and query_lower in stripped.lower():
            matches.append(stripped)

    prefix = ""
    if error:
        prefix = f"({error}. Falling back to doc index.)\n\n"

    if not matches:
        text = f"{prefix}No matches for '{query_text}'. Full doc index:\n\n{llms_txt}"
    else:
        text = f"{prefix}Matching docs for '{query_text}':\n\n" + "\n".join(matches)

    return [TextContent(type="text", text=text)]


# ---------------------------------------------------------------------------
# Tool 4: qdrant-read-skill
# ---------------------------------------------------------------------------

@mcp.tool(
    name="qdrant-read-skill",
    description=(
        "Read a local Qdrant skill or command reference file. Contains "
        "decision tables, gotchas, and best practices. Available: "
        "qdrant-python, qdrant-rust, connect, setup-collection, "
        "hybrid-search, add-multitenancy, migrate-search."
    ),
)
async def read_skill(
    name: Annotated[
        str,
        Field(description="Skill or command name, e.g. 'qdrant-python', 'hybrid-search'"),
    ],
) -> list[TextContent]:
    """Read a local skill/command file from the qdrant-skills repo."""
    path = SKILL_FILE_MAP.get(name)

    if path is None or not path.exists():
        available = ", ".join(sorted(SKILL_FILE_MAP.keys()))
        return [TextContent(
            type="text",
            text=f"Unknown or missing file: '{name}'. Available: {available}",
        )]

    content = path.read_text()
    return [TextContent(type="text", text=content)]


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def _package_shard():
    """Compress the current shard (segments only) into the package data dir."""
    import tarfile

    if not SHARD_DIR.exists():
        print(f"error: no shard found at {SHARD_DIR}")
        print("run: qdrant-guide --rebuild-index")
        return

    segments_dir = SHARD_DIR / "segments"
    if not segments_dir.exists():
        print(f"error: no segments directory in {SHARD_DIR}")
        return

    BUNDLED_SHARD_ARCHIVE.parent.mkdir(parents=True, exist_ok=True)

    def _exclude_junk(info: tarfile.TarInfo):
        """Skip macOS resource forks and other junk."""
        basename = os.path.basename(info.name)
        if basename.startswith("._") or basename == ".DS_Store":
            return None
        return info

    print(f"packaging shard from {SHARD_DIR}...")
    with tarfile.open(BUNDLED_SHARD_ARCHIVE, "w:gz") as tar:
        tar.add(str(segments_dir), arcname="segments", filter=_exclude_junk)

    size_mb = BUNDLED_SHARD_ARCHIVE.stat().st_size / (1024 * 1024)
    print(f"wrote {BUNDLED_SHARD_ARCHIVE} ({size_mb:.1f} MB)")
    print("rebuild the wheel to include the updated shard: uv build")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="qdrant-guide MCP server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse", "streamable-http"],
        default="stdio",
    )
    parser.add_argument(
        "--rebuild-index",
        action="store_true",
        help="Rebuild the local search index from Qdrant documentation, then exit.",
    )
    parser.add_argument(
        "--package-shard",
        action="store_true",
        help="Package the current shard into the source tree for distribution.",
    )
    args = parser.parse_args()

    if args.rebuild_index:
        from qdrant_guide.indexer import build_index

        build_index()
        return

    if args.package_shard:
        _package_shard()
        return

    mcp.run(transport=args.transport)


if __name__ == "__main__":
    main()
