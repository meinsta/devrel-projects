"""Post-evaluation hook for upserting chapter memory."""

from pathlib import Path
from qdrant_client import QdrantClient
from memory.store import upsert_chapter_memory

CHAPTERS_DIR = Path(__file__).parent.parent / "chapters"


def post_evaluate_hook(
    client: QdrantClient,
    chapter_num: int,
    eval_result: dict,
    run_id: str,
    condition: str,
):
    """Called after evaluate.py returns. Upserts chapter memory to Qdrant."""
    if condition == "baseline":
        return

    chapter_path = CHAPTERS_DIR / f"ch_{chapter_num:02d}.md"
    chapter_text = chapter_path.read_text()

    upsert_chapter_memory(
        client=client,
        chapter_num=chapter_num,
        chapter_text=chapter_text,
        eval_result=eval_result,
        run_id=run_id,
        condition=condition,
    )
