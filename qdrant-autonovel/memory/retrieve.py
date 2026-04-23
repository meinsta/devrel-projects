"""Query Qdrant for lessons learned from past chapters."""

from qdrant_client import QdrantClient, models
from memory.schema import COLLECTION_NAME
from memory.embed import embed_dense, embed_sparse


def format_memory(point) -> str:
    """Format a retrieved Qdrant point into a text block for prompt injection."""
    p = point.payload
    parts = [
        f"LESSON FROM CHAPTER {p.get('chapter_num', '?')} (score: {p.get('critique_score', '?')}):",
    ]
    if p.get("weakest_dimension"):
        parts.append(f"- Weakest area: {p['weakest_dimension']}")
    if p.get("top_revisions"):
        for rev in p["top_revisions"][:3]:
            parts.append(f"- Revision needed: {rev}")
    if p.get("ai_patterns"):
        parts.append(f"- AI patterns to avoid: {', '.join(p['ai_patterns'][:3])}")
    if p.get("three_weakest_sentences"):
        parts.append(f"- Weak sentences to avoid repeating: {' | '.join(p['three_weakest_sentences'][:2])}")
    return "\n".join(parts)


def query_chapter_memory(
    client: QdrantClient,
    chapter_num: int,
    outline_text: str,
    condition: str = "qdrant",
    limit: int = 3,
) -> list[str]:
    """Query memory for lessons learned from past chapters.

    Returns a list of formatted text blocks, one per relevant past chapter.
    """
    if condition == "baseline":
        return []

    if chapter_num <= 1:
        return []  # no prior chapters to learn from

    # Filter: only chapters before current, within a window of 5
    chapter_filter = models.Filter(
        must=[
            models.FieldCondition(
                key="chapter_num",
                range=models.Range(
                    gte=max(1, chapter_num - 5),
                    lt=chapter_num,
                ),
            ),
        ],
    )

    if condition == "dense":
        # Dense-only: single semantic query
        results = client.query_points(
            collection_name=COLLECTION_NAME,
            query=embed_dense(outline_text),
            using="dense_semantic",
            query_filter=chapter_filter,
            limit=limit,
        ).points

    elif condition == "qdrant":
        # Full composable: dense + sparse + RRF fusion
        results = client.query_points(
            collection_name=COLLECTION_NAME,
            prefetch=[
                models.Prefetch(
                    query=embed_dense(outline_text),
                    using="dense_semantic",
                    filter=chapter_filter,
                    limit=limit + 2,
                ),
                models.Prefetch(
                    query=embed_sparse(outline_text),
                    using="sparse_keyword",
                    filter=chapter_filter,
                    limit=limit + 2,
                ),
            ],
            query=models.FusionQuery(fusion=models.Fusion.RRF),
            limit=limit,
        ).points
    else:
        return []

    return [format_memory(point) for point in results]
