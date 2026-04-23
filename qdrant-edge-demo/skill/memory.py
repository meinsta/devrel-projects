"""
Shared Qdrant Edge shard for the OpenClaw local-memory skill.
Uses fastembed for real local embeddings.
"""

import hashlib
from pathlib import Path

from fastembed import TextEmbedding
from qdrant_edge import (
    Distance,
    EdgeConfig,
    EdgeShard,
    EdgeVectorParams,
    Point,
    Query,
    QueryRequest,
    UpdateOperation,
)

SHARD_DIR = str(Path(__file__).parent.parent / "agent-memory")
VECTOR_NAME = "embedding"
MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
DIM = 384

_model = None


def _get_model() -> TextEmbedding:
    global _model
    if _model is None:
        _model = TextEmbedding(MODEL_NAME)
    return _model


def _embed(texts: list[str]) -> list[list[float]]:
    return [v.tolist() for v in _get_model().embed(texts)]


def _get_or_create_shard() -> EdgeShard:
    path = Path(SHARD_DIR)
    if path.exists() and any(path.iterdir()):
        return EdgeShard.load(SHARD_DIR)

    path.mkdir(parents=True, exist_ok=True)
    return EdgeShard.create(
        SHARD_DIR,
        EdgeConfig(
            vectors={VECTOR_NAME: EdgeVectorParams(size=DIM, distance=Distance.Cosine)}
        ),
    )


def _text_to_id(text: str) -> int:
    return int(hashlib.sha256(text.encode()).hexdigest()[:15], 16)


def store(text: str, metadata: dict | None = None) -> int:
    shard = _get_or_create_shard()
    point_id = _text_to_id(text)
    payload = {"text": text}
    if metadata:
        payload.update(metadata)

    vec = _embed([text])[0]
    shard.update(
        UpdateOperation.upsert_points(
            [Point(id=point_id, vector={VECTOR_NAME: vec}, payload=payload)]
        )
    )
    shard.close()
    return point_id


def search(query: str, limit: int = 5) -> list[dict]:
    shard = _get_or_create_shard()
    query_vec = _embed([query])[0]
    results = shard.query(
        QueryRequest(
            query=Query.Nearest(query_vec, using=VECTOR_NAME),
            limit=limit,
            with_payload=True,
        )
    )
    shard.close()
    return [
        {"id": r.id, "score": round(r.score, 4), **r.payload}
        for r in results
    ]
