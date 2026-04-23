"""
Qdrant Edge + FastEmbed: local vector memory for agents.
No server. No cloud. Just a folder on disk.
"""

import shutil
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

SHARD_DIR = "./agent-memory"
VECTOR_NAME = "embedding"
MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
DIM = 384

# Load embedding model (runs locally, ~30MB)
print(f"Loading model: {MODEL_NAME}")
model = TextEmbedding(MODEL_NAME)

# Clean slate
if Path(SHARD_DIR).exists():
    shutil.rmtree(SHARD_DIR)
Path(SHARD_DIR).mkdir(parents=True, exist_ok=True)


def embed(texts: list[str]) -> list[list[float]]:
    return [v.tolist() for v in model.embed(texts)]


# 1. Create a local shard (just a folder)
print("\n=== Creating local Qdrant Edge shard ===\n")
shard = EdgeShard.create(
    SHARD_DIR,
    EdgeConfig(
        vectors={VECTOR_NAME: EdgeVectorParams(size=DIM, distance=Distance.Cosine)}
    ),
)

# 2. Agent learns some knowledge
docs = [
    {"id": 1, "text": "how to reset your password", "category": "auth"},
    {"id": 2, "text": "setting up two-factor authentication", "category": "auth"},
    {"id": 3, "text": "account recovery options", "category": "auth"},
    {"id": 4, "text": "shipping and delivery times", "category": "logistics"},
    {"id": 5, "text": "refund and return policy", "category": "billing"},
    {"id": 6, "text": "login troubleshooting guide", "category": "auth"},
]

texts = [d["text"] for d in docs]
vectors = embed(texts)

points = [
    Point(
        id=d["id"],
        vector={VECTOR_NAME: vec},
        payload={"text": d["text"], "category": d["category"]},
    )
    for d, vec in zip(docs, vectors)
]

print(f"Upserting {len(points)} documents...\n")
shard.update(UpdateOperation.upsert_points(points))

# 3. Agent searches
queries = [
    "help me log in",
    "I want my money back",
    "where is my package",
]

for q in queries:
    print(f'=== Agent searches: "{q}" ===\n')
    query_vec = embed([q])[0]

    results = shard.query(
        QueryRequest(
            query=Query.Nearest(query_vec, using=VECTOR_NAME),
            limit=3,
            with_payload=True,
        )
    )

    for i, r in enumerate(results, 1):
        print(f"  {i}. [{r.score:.4f}] {r.payload['text']}")
    print()

# 4. Done
shard.close()
print(f"Shard stored at: {SHARD_DIR}/")
print("No server was harmed in the making of this demo.")
