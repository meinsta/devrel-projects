"""Build the local qdrant-edge search index from Qdrant documentation.

Fetches all doc pages listed in qdrant_docs_map.md, chunks them,
embeds with fastembed, and stores in a local EdgeShard.
"""

import asyncio
import re
import shutil
from pathlib import Path

from qdrant_edge import (
    Distance,
    EdgeConfig,
    EdgeShard,
    Point,
    UpdateOperation,
    VectorDataConfig,
)

from qdrant_guide.config import (
    CHUNK_MAX_CHARS,
    EMBEDDING_DIM,
    EMBEDDING_MODEL,
    SHARD_DIR,
    detect_language,
)
from qdrant_guide.doc_cache import DocCache

_DOCS_MAP_PATH = Path(__file__).parent / "qdrant_docs_map.md"

# Match markdown links: [title](url)
_LINK_PATTERN = re.compile(r"\[([^\]]+)\]\((https://[^)]+)\)")


def _extract_urls_from_docs_map() -> list[tuple[str, str]]:
    """Extract (title, url) pairs from the docs map markdown."""
    content = _DOCS_MAP_PATH.read_text()
    return _LINK_PATTERN.findall(content)


def _chunk_text(text: str, source_url: str, title: str) -> list[dict]:
    """Split text into chunks of roughly CHUNK_MAX_CHARS by paragraph boundaries."""
    paragraphs = text.split("\n\n")
    chunks = []
    current = ""

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        if len(current) + len(para) + 2 > CHUNK_MAX_CHARS and current:
            chunks.append({
                "content": current.strip(),
                "source": source_url,
                "title": title,
                "language": detect_language(source_url),
            })
            current = para
        else:
            current = current + "\n\n" + para if current else para

    if current.strip():
        chunks.append({
            "content": current.strip(),
            "source": source_url,
            "title": title,
            "language": detect_language(source_url),
        })

    return chunks


async def _fetch_all_docs(urls: list[tuple[str, str]]) -> list[dict]:
    """Fetch all doc pages and chunk them."""
    cache = DocCache()
    all_chunks = []
    total = len(urls)

    try:
        for i, (title, url) in enumerate(urls):
            print(f"  [{i + 1}/{total}] {title}")
            try:
                content = await cache.fetch_page(url)
                chunks = _chunk_text(content, url, title)
                all_chunks.extend(chunks)
            except Exception as exc:
                print(f"    error: {exc}")
    finally:
        await cache.close()

    return all_chunks


def build_index() -> None:
    """Build the local edge shard from all Qdrant documentation pages."""
    print("extracting URLs from docs map...")
    urls = _extract_urls_from_docs_map()
    print(f"found {len(urls)} documentation pages")

    print("fetching and chunking documentation...")
    chunks = asyncio.run(_fetch_all_docs(urls))
    print(f"created {len(chunks)} chunks")

    if not chunks:
        print("error: no chunks to index")
        return

    print(f"embedding chunks with {EMBEDDING_MODEL}...")
    from fastembed import TextEmbedding

    model = TextEmbedding(EMBEDDING_MODEL)
    texts = [c["content"] for c in chunks]
    embeddings = list(model.embed(texts))
    print(f"generated {len(embeddings)} embeddings ({EMBEDDING_DIM}d)")

    # Recreate shard directory
    if SHARD_DIR.exists():
        print(f"removing existing shard at {SHARD_DIR}")
        shutil.rmtree(SHARD_DIR)
    SHARD_DIR.mkdir(parents=True, exist_ok=True)

    print(f"writing edge shard to {SHARD_DIR}...")
    config = EdgeConfig(
        vector_data={
            "dense": VectorDataConfig(size=EMBEDDING_DIM, distance=Distance.Cosine)
        }
    )
    shard = EdgeShard(str(SHARD_DIR), config)

    # Insert in batches of 100
    batch_size = 100
    points = []
    for idx, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
        points.append(Point(
            id=idx + 1,
            vector={"dense": embedding.tolist()},
            payload=chunk,
        ))

        if len(points) >= batch_size:
            shard.update(UpdateOperation.upsert_points(points))
            points = []

    if points:
        shard.update(UpdateOperation.upsert_points(points))

    shard.flush()
    shard.close()
    print(f"done. indexed {len(chunks)} chunks into {SHARD_DIR}")
