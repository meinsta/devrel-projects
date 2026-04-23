"""Tests for the memory module using in-memory Qdrant."""

import pytest
from qdrant_client import QdrantClient

from memory.schema import create_collection
from memory.embed import embed_dense, embed_sparse
from memory.store import upsert_chapter_memory, build_embed_text, extract_arc_tags
from memory.retrieve import query_chapter_memory, format_memory


@pytest.fixture
def client():
    return QdrantClient(":memory:")


@pytest.fixture
def collection(client):
    create_collection(client, "test_memory")
    return "test_memory"


SAMPLE_EVAL = {
    "overall_score": 6.5,
    "raw_judge_score": 7,
    "weakest_dimension": "prose_quality",
    "top_3_revisions": [
        "Vary sentence openings in paragraphs 3-5",
        "Replace generic metaphor in paragraph 7",
        "Cut the redundant internal monologue after the forge scene",
    ],
    "three_weakest_sentences": [
        "He felt a surge of something he couldn't name.",
        "The air was thick with tension.",
        "She looked at him with knowing eyes.",
    ],
    "ai_patterns_detected": [
        "Triadic listing in paragraphs 2, 5, 8",
        "Uniform paragraph length throughout",
    ],
    "voice_adherence": {"score": 7, "note": "Good"},
    "beat_coverage": {"score": 8, "note": "All beats hit"},
    "character_voice": {"score": 5, "note": "Dialogue too polished"},
    "prose_quality": {"score": 5, "note": "Generic in places"},
    "engagement": {"score": 7, "note": "Page-turner"},
    "lore_integration": {"score": 6, "note": "Adequate"},
    "slop": {"slop_penalty": 0.5},
}


class TestEmbedding:
    def test_dense_embedding_shape(self):
        vec = embed_dense("The bronze bells rang across Cantamura.")
        assert len(vec) == 768
        assert all(isinstance(v, float) for v in vec)

    def test_sparse_embedding_nonempty(self):
        sparse = embed_sparse("Cass heard the under-note behind his father's song.")
        assert len(sparse.indices) > 0
        assert len(sparse.values) > 0
        assert len(sparse.indices) == len(sparse.values)


class TestSchema:
    def test_create_collection(self, client):
        create_collection(client, "test_schema")
        assert client.collection_exists("test_schema")

    def test_create_collection_idempotent(self, client):
        create_collection(client, "test_idempotent")
        create_collection(client, "test_idempotent")
        assert client.collection_exists("test_idempotent")


class TestStore:
    def test_build_embed_text(self):
        text = build_embed_text("word " * 600, SAMPLE_EVAL)
        assert "Weakest area: prose_quality" in text
        assert "Revisions needed:" in text

    def test_extract_arc_tags(self):
        tags = extract_arc_tags(SAMPLE_EVAL)
        assert "prose_quality" in tags
        assert "weak_character_voice" in tags
        assert "weak_prose_quality" in tags

    def test_upsert_chapter(self, client, collection):
        import os
        os.environ["QDRANT_COLLECTION"] = collection
        # Monkey-patch COLLECTION_NAME for this test
        import memory.store as store_mod
        orig = store_mod.COLLECTION_NAME
        store_mod.COLLECTION_NAME = collection

        upsert_chapter_memory(
            client=client,
            chapter_num=1,
            chapter_text="Cass pressed his back against the workshop wall. " * 100,
            eval_result=SAMPLE_EVAL,
            run_id="test_run",
            condition="qdrant",
        )

        # Verify point exists
        points = client.scroll(collection_name=collection, limit=10)[0]
        assert len(points) == 1
        assert points[0].payload["chapter_num"] == 1
        assert points[0].payload["critique_score"] == 6.5
        assert points[0].payload["weakest_dimension"] == "prose_quality"

        store_mod.COLLECTION_NAME = orig


class TestRetrieve:
    def _seed_chapters(self, client, collection, n=5):
        """Seed n chapters into the collection."""
        import memory.store as store_mod
        orig = store_mod.COLLECTION_NAME
        store_mod.COLLECTION_NAME = collection

        for i in range(1, n + 1):
            eval_result = {
                **SAMPLE_EVAL,
                "overall_score": 5.0 + i * 0.3,
                "weakest_dimension": f"dimension_{i}",
            }
            upsert_chapter_memory(
                client=client,
                chapter_num=i,
                chapter_text=f"Chapter {i} about Cass and the bells. " * 50,
                eval_result=eval_result,
                run_id="test_run",
                condition="qdrant",
            )

        store_mod.COLLECTION_NAME = orig

    def test_baseline_returns_empty(self, client, collection):
        self._seed_chapters(client, collection)
        result = query_chapter_memory(client, 3, "test outline", condition="baseline")
        assert result == []

    def test_dense_returns_results(self, client, collection):
        import memory.retrieve as ret_mod
        orig = ret_mod.COLLECTION_NAME
        ret_mod.COLLECTION_NAME = collection

        self._seed_chapters(client, collection)
        result = query_chapter_memory(
            client, 4, "Cass heard the bells ringing",
            condition="dense", limit=2,
        )
        assert len(result) > 0
        assert "LESSON FROM CHAPTER" in result[0]

        ret_mod.COLLECTION_NAME = orig

    def test_qdrant_rrf_returns_results(self, client, collection):
        import memory.retrieve as ret_mod
        orig = ret_mod.COLLECTION_NAME
        ret_mod.COLLECTION_NAME = collection

        self._seed_chapters(client, collection)
        result = query_chapter_memory(
            client, 6, "Cass heard the bells ringing across Cantamura",
            condition="qdrant", limit=3,
        )
        assert len(result) > 0
        assert "LESSON FROM CHAPTER" in result[0]

        ret_mod.COLLECTION_NAME = orig

    def test_chapter_1_returns_empty(self, client, collection):
        result = query_chapter_memory(client, 1, "test", condition="qdrant")
        assert result == []

    def test_format_memory(self):
        class FakePoint:
            payload = {
                "chapter_num": 3,
                "critique_score": 6.5,
                "weakest_dimension": "prose_quality",
                "top_revisions": ["Fix sentence variety", "Cut redundancy"],
                "ai_patterns": ["Triadic listing"],
                "three_weakest_sentences": ["Bad sentence one.", "Bad sentence two."],
            }
        formatted = format_memory(FakePoint())
        assert "LESSON FROM CHAPTER 3" in formatted
        assert "prose_quality" in formatted
        assert "Triadic listing" in formatted
