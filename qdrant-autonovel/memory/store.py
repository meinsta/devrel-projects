"""Upsert chapter memory into Qdrant after evaluation."""

from qdrant_client import QdrantClient, models
from memory.schema import COLLECTION_NAME
from memory.embed import embed_dense, embed_sparse


def build_embed_text(chapter_text: str, eval_result: dict) -> str:
    """Build the text to embed: chapter excerpt + critique highlights."""
    # First 500 words of the chapter
    words = chapter_text.split()
    excerpt = " ".join(words[:500])

    # Critique highlights
    parts = [excerpt]

    if "weakest_dimension" in eval_result:
        parts.append(f"Weakest area: {eval_result['weakest_dimension']}")

    if "top_3_revisions" in eval_result:
        parts.append("Revisions needed: " + "; ".join(eval_result["top_3_revisions"]))

    if "three_weakest_sentences" in eval_result:
        parts.append("Weak sentences: " + " | ".join(eval_result["three_weakest_sentences"]))

    if "ai_patterns_detected" in eval_result:
        parts.append("AI patterns: " + ", ".join(eval_result["ai_patterns_detected"]))

    return "\n".join(parts)


def extract_arc_tags(eval_result: dict) -> list[str]:
    """Extract arc-relevant tags from evaluation result."""
    tags = []
    if "weakest_dimension" in eval_result:
        tags.append(eval_result["weakest_dimension"])

    # Extract dimension names where score < 6 (problem areas)
    for key in ["voice_adherence", "beat_coverage", "character_voice",
                "prose_quality", "engagement", "lore_integration"]:
        if key in eval_result and isinstance(eval_result[key], dict):
            score = eval_result[key].get("score", 10)
            if score < 6:
                tags.append(f"weak_{key}")

    return tags


def upsert_chapter_memory(
    client: QdrantClient,
    chapter_num: int,
    chapter_text: str,
    eval_result: dict,
    run_id: str,
    condition: str,
):
    """Upsert a chapter's memory into Qdrant."""
    embed_text = build_embed_text(chapter_text, eval_result)
    dense_vector = embed_dense(embed_text)
    sparse_vector = embed_sparse(embed_text)

    # Extract scores from eval result
    def get_score(key):
        val = eval_result.get(key)
        if isinstance(val, dict):
            return val.get("score", 0)
        return 0

    payload = {
        "chapter_num": chapter_num,
        "critique_score": eval_result.get("overall_score", 0),
        "raw_judge_score": eval_result.get("raw_judge_score", 0),
        "arc_tags": extract_arc_tags(eval_result),
        "voice_score": get_score("voice_adherence"),
        "prose_score": get_score("prose_quality"),
        "engagement_score": get_score("engagement"),
        "weakest_dimension": eval_result.get("weakest_dimension", ""),
        "top_revisions": eval_result.get("top_3_revisions", []),
        "ai_patterns": eval_result.get("ai_patterns_detected", []),
        "three_weakest_sentences": eval_result.get("three_weakest_sentences", []),
        "word_count": len(chapter_text.split()),
        "run_id": run_id,
        "condition": condition,
    }

    client.upsert(
        collection_name=COLLECTION_NAME,
        points=[
            models.PointStruct(
                id=chapter_num,
                vector={
                    "dense_semantic": dense_vector,
                    "sparse_keyword": sparse_vector,
                },
                payload=payload,
            )
        ],
    )
