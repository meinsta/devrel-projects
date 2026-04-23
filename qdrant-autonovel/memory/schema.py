"""Qdrant collection schema for autonovel memory."""

import os
from qdrant_client import QdrantClient, models
from dotenv import load_dotenv

load_dotenv()

COLLECTION_NAME = os.environ.get("QDRANT_COLLECTION", "autonovel_memory")


def get_client() -> QdrantClient:
    url = os.environ.get("QDRANT_URL", "http://localhost:6333")
    api_key = os.environ.get("QDRANT_API_KEY", None)
    if url == ":memory:":
        return QdrantClient(":memory:")
    return QdrantClient(url=url, api_key=api_key)


def create_collection(client: QdrantClient, collection_name: str = COLLECTION_NAME):
    """Create the autonovel memory collection with dense + sparse vectors."""
    if client.collection_exists(collection_name):
        return

    client.create_collection(
        collection_name=collection_name,
        vectors_config={
            "dense_semantic": models.VectorParams(
                size=768,  # BAAI/bge-base-en-v1.5
                distance=models.Distance.COSINE,
            ),
        },
        sparse_vectors_config={
            "sparse_keyword": models.SparseVectorParams(
                modifier=models.Modifier.IDF,
            ),
        },
    )
