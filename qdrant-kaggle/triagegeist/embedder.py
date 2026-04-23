"""Embed patient records and upload to Qdrant."""

import time

import pandas as pd
from qdrant_client import QdrantClient, models
from tqdm import tqdm

from triagegeist.config import (
    COLLECTION_NAME,
    DISTANCE_METRIC,
    EMBEDDING_DIM,
    EMBEDDING_MODEL,
    QDRANT_API_KEY,
    QDRANT_URL,
)
from triagegeist.data_loader import build_payloads, serialize_patient


def get_client() -> QdrantClient:
    kwargs = {"url": QDRANT_URL}
    if QDRANT_API_KEY:
        kwargs["api_key"] = QDRANT_API_KEY
    return QdrantClient(**kwargs)


def create_collection(client: QdrantClient, collection_name: str = COLLECTION_NAME):
    """Create collection with optimized settings for triage retrieval."""
    if client.collection_exists(collection_name):
        print(f"collection '{collection_name}' already exists, skipping creation")
        return

    client.create_collection(
        collection_name=collection_name,
        vectors_config=models.VectorParams(
            size=EMBEDDING_DIM,
            distance=getattr(models.Distance, DISTANCE_METRIC.upper(), models.Distance.COSINE),
        ),
        # Payload indices for filtered search (bias analysis, demographic slicing)
        optimizers_config=models.OptimizersConfigDiff(
            indexing_threshold=20000,
        ),
    )

    # Create payload indices for filtered retrieval
    for field in ["triage_acuity", "age_group", "sex", "insurance_type",
                  "chief_complaint_system", "arrival_mode", "disposition"]:
        client.create_payload_index(
            collection_name=collection_name,
            field_name=field,
            field_schema=models.PayloadSchemaType.KEYWORD,
        )

    # Numeric indices for range filtering
    for field in ["age", "news2_score", "shock_index"]:
        client.create_payload_index(
            collection_name=collection_name,
            field_name=field,
            field_schema=models.PayloadSchemaType.FLOAT,
        )

    print(f"created collection '{collection_name}' (dim={EMBEDDING_DIM})")


def embed_and_upload(
    client: QdrantClient,
    df: pd.DataFrame,
    collection_name: str = COLLECTION_NAME,
    batch_size: int = 128,
):
    """Serialize patient records, embed with Fastembed, upload to Qdrant."""
    print(f"serializing {len(df)} patient records...")
    texts = [serialize_patient(row) for _, row in tqdm(df.iterrows(), total=len(df), desc="serialize")]

    print(f"building payloads...")
    payloads = build_payloads(df)

    # Use patient_id as point ID (must be int for Qdrant)
    ids = df["patient_id"].tolist()

    print(f"embedding and uploading {len(texts)} records (batch_size={batch_size})...")
    t0 = time.perf_counter()

    # Fastembed handles batching internally
    client.upload_collection(
        collection_name=collection_name,
        vectors=_embed_texts(texts, batch_size),
        payload=payloads,
        ids=ids,
        parallel=4,
    )

    elapsed = time.perf_counter() - t0
    print(f"uploaded {len(texts)} points in {elapsed:.1f}s ({len(texts)/elapsed:.0f} pts/s)")


def _embed_texts(texts: list[str], batch_size: int) -> list[list[float]]:
    """Embed texts using Fastembed via a local model."""
    from fastembed import TextEmbedding

    model = TextEmbedding(model_name=EMBEDDING_MODEL)
    all_embeddings = []
    for batch_embeddings in tqdm(
        model.embed(texts, batch_size=batch_size),
        total=len(texts),
        desc="embed",
    ):
        all_embeddings.append(batch_embeddings.tolist())
    return all_embeddings


def embed_queries(texts: list[str]) -> list[list[float]]:
    """Embed query texts for search."""
    from fastembed import TextEmbedding

    model = TextEmbedding(model_name=EMBEDDING_MODEL)
    return [e.tolist() for e in model.embed(texts)]
