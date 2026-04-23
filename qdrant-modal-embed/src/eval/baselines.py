"""Baseline Evaluation using Qdrant with FastEmbed-GPU

Uses FastEmbed-GPU for local embedding with CUDA acceleration:
- Qdrant/bm25: Traditional BM25 sparse retrieval
- prithivida/Splade_PP_en_v1: Off-the-shelf SPLADE (GPU-accelerated)
- sentence-transformers/all-MiniLM-L6-v2: Dense embedding baseline

FastEmbed-GPU is used for local inference with GPU support.
"""

import logging
import os
from typing import Dict, List

from qdrant_client import QdrantClient, models
from tqdm import tqdm

from src.config import settings
from src.eval.retrieval_metrics import evaluate_retrieval, print_metrics

logger = logging.getLogger(__name__)

# FastEmbed model names for sparse retrieval
BM25_MODEL = "Qdrant/bm25"
SPLADE_MODEL = "prithivida/Splade_PP_en_v1"

# Dense embedding models
DENSE_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
DENSE_DIM = 384  # Embedding dimension for all-MiniLM-L6-v2


def get_qdrant_client() -> QdrantClient:
    """Get Qdrant client from environment."""
    url = os.environ.get("QDRANT_URL") or settings.qdrant_url
    api_key = os.environ.get("QDRANT_API_KEY") or settings.qdrant_api_key

    if not url:
        raise ValueError("QDRANT_URL not set")

    return QdrantClient(url=url, api_key=api_key)


def create_baseline_collection(
    client: QdrantClient,
    collection_name: str,
    enable_bm25: bool = True,
    enable_splade: bool = True,
    enable_dense: bool = False,
    recreate: bool = False,
) -> None:
    """
    Create collection with sparse and/or dense vector configurations.

    Args:
        client: Qdrant client
        collection_name: Collection name
        enable_bm25: Enable BM25 sparse vectors
        enable_splade: Enable SPLADE sparse vectors
        enable_dense: Enable dense vectors
        recreate: Delete existing collection
    """
    if recreate:
        try:
            client.delete_collection(collection_name)
            logger.info(f"Deleted existing collection: {collection_name}")
        except Exception:
            pass

    sparse_config = {}
    vectors_config = {}

    if enable_bm25:
        sparse_config["bm25"] = models.SparseVectorParams(
            modifier=models.Modifier.IDF,  # Enable IDF weighting for BM25
        )

    if enable_splade:
        sparse_config["splade"] = models.SparseVectorParams()

    if enable_dense:
        vectors_config["dense"] = models.VectorParams(
            size=DENSE_DIM,
            distance=models.Distance.COSINE,
        )

    client.create_collection(
        collection_name=collection_name,
        vectors_config=vectors_config if vectors_config else {},
        sparse_vectors_config=sparse_config if sparse_config else None,
    )

    logger.info(f"Created baseline collection: {collection_name}")


def index_with_fastembed(
    client: QdrantClient,
    collection_name: str,
    documents: List[Dict],
    batch_size: int = 32,
    show_progress: bool = True,
) -> int:
    """
    Index documents using FastEmbed for local sparse embedding.

    Args:
        client: Qdrant client
        collection_name: Target collection
        documents: List of {"product_id": str, "text": str, "payload": dict}
        batch_size: Batch size for embedding and upsert
        show_progress: Show progress bar

    Returns:
        Number of indexed documents
    """
    from fastembed import SparseTextEmbedding

    # Initialize FastEmbed models with GPU support for SPLADE
    logger.info("Loading FastEmbed models (SPLADE with CUDA)...")
    bm25_model = SparseTextEmbedding(model_name=BM25_MODEL)
    splade_model = SparseTextEmbedding(
        model_name=SPLADE_MODEL,
        providers=["CUDAExecutionProvider", "CPUExecutionProvider"],
    )

    total = 0
    iterator = range(0, len(documents), batch_size)

    if show_progress:
        iterator = tqdm(iterator, desc="Indexing with FastEmbed")

    for i in iterator:
        batch = documents[i : i + batch_size]
        texts = [doc["text"] for doc in batch]

        # Compute sparse embeddings locally
        bm25_embeddings = list(bm25_model.embed(texts))
        splade_embeddings = list(splade_model.embed(texts))

        points = []
        for j, doc in enumerate(batch):
            bm25_emb = bm25_embeddings[j]
            splade_emb = splade_embeddings[j]

            point = models.PointStruct(
                id=i + j,
                vector={
                    "bm25": models.SparseVector(
                        indices=bm25_emb.indices.tolist(),
                        values=bm25_emb.values.tolist(),
                    ),
                    "splade": models.SparseVector(
                        indices=splade_emb.indices.tolist(),
                        values=splade_emb.values.tolist(),
                    ),
                },
                payload={
                    "product_id": doc["product_id"],
                    "text": doc["text"],
                    **doc.get("payload", {}),
                },
            )
            points.append(point)

        client.upsert(collection_name=collection_name, points=points)
        total += len(points)

    logger.info(f"Indexed {total} documents with FastEmbed")
    return total


def index_with_dense(
    client: QdrantClient,
    collection_name: str,
    documents: List[Dict],
    batch_size: int = 32,
    show_progress: bool = True,
) -> int:
    """
    Index documents using dense embeddings with FastEmbed.

    Args:
        client: Qdrant client
        collection_name: Target collection
        documents: List of {"product_id": str, "text": str, "payload": dict}
        batch_size: Batch size for embedding and upsert
        show_progress: Show progress bar

    Returns:
        Number of indexed documents
    """
    from fastembed import TextEmbedding

    # Initialize FastEmbed dense model
    logger.info(f"Loading FastEmbed dense model: {DENSE_MODEL}...")
    dense_model = TextEmbedding(
        model_name=DENSE_MODEL,
        providers=["CUDAExecutionProvider", "CPUExecutionProvider"],
    )

    total = 0
    iterator = range(0, len(documents), batch_size)

    if show_progress:
        iterator = tqdm(iterator, desc="Indexing with dense embeddings")

    for i in iterator:
        batch = documents[i : i + batch_size]
        texts = [doc["text"] for doc in batch]

        # Compute dense embeddings
        dense_embeddings = list(dense_model.embed(texts))

        points = []
        for j, doc in enumerate(batch):
            dense_emb = dense_embeddings[j]

            point = models.PointStruct(
                id=i + j,
                vector={"dense": dense_emb.tolist()},
                payload={
                    "product_id": doc["product_id"],
                    "text": doc["text"],
                    **doc.get("payload", {}),
                },
            )
            points.append(point)

        client.upsert(collection_name=collection_name, points=points)
        total += len(points)

    logger.info(f"Indexed {total} documents with dense embeddings")
    return total


def evaluate_dense(
    client: QdrantClient,
    collection_name: str,
    queries: List[Dict],
    k_values: List[int] = [10, 50, 100],
    show_progress: bool = True,
) -> Dict[str, float]:
    """
    Evaluate dense embedding retrieval.

    Args:
        client: Qdrant client
        collection_name: Collection to search
        queries: List of {"query_id", "query", "relevance": {pid: label}}
        k_values: Evaluation cutoffs
        show_progress: Show progress bar

    Returns:
        Dict of evaluation metrics
    """
    from fastembed import TextEmbedding

    # Initialize FastEmbed dense model
    logger.info(f"Loading FastEmbed dense model for queries: {DENSE_MODEL}...")
    dense_model = TextEmbedding(
        model_name=DENSE_MODEL,
        providers=["CUDAExecutionProvider", "CPUExecutionProvider"],
    )

    retrieved_results = []
    max_k = max(k_values)

    iterator = queries
    if show_progress:
        iterator = tqdm(queries, desc="Evaluating dense")

    for q in iterator:
        query_text = q["query"]

        # Encode query with dense model
        query_embeddings = list(dense_model.embed([query_text]))
        query_emb = query_embeddings[0]

        # Search with dense vector
        results = client.query_points(
            collection_name=collection_name,
            query=query_emb.tolist(),
            using="dense",
            limit=max_k,
            with_payload=True,
        )

        retrieved_ids = [p.payload.get("product_id", "") for p in results.points]

        retrieved_results.append({
            "query_id": q["query_id"],
            "retrieved_ids": retrieved_ids,
        })

    return evaluate_retrieval(
        retrieved_results=retrieved_results,
        ground_truth=queries,
        k_values=k_values,
    )


def evaluate_baseline(
    client: QdrantClient,
    collection_name: str,
    queries: List[Dict],
    model_name: str,
    vector_name: str,
    k_values: List[int] = [10, 50, 100],
    show_progress: bool = True,
) -> Dict[str, float]:
    """
    Evaluate a baseline model using FastEmbed for query encoding.

    Args:
        client: Qdrant client
        collection_name: Collection to search
        queries: List of {"query_id", "query", "relevance": {pid: label}}
        model_name: FastEmbed model name (BM25_MODEL or SPLADE_MODEL)
        vector_name: Vector field name ("bm25" or "splade")
        k_values: Evaluation cutoffs
        show_progress: Show progress bar

    Returns:
        Dict of evaluation metrics
    """
    from fastembed import SparseTextEmbedding

    # Initialize FastEmbed model for query encoding (GPU for SPLADE)
    logger.info(f"Loading FastEmbed model for {vector_name}...")
    if model_name == SPLADE_MODEL:
        sparse_model = SparseTextEmbedding(
            model_name=model_name,
            providers=["CUDAExecutionProvider", "CPUExecutionProvider"],
        )
    else:
        sparse_model = SparseTextEmbedding(model_name=model_name)

    retrieved_results = []
    max_k = max(k_values)

    iterator = queries
    if show_progress:
        iterator = tqdm(queries, desc=f"Evaluating {vector_name}")

    for q in iterator:
        query_text = q["query"]

        # Encode query with FastEmbed
        query_embeddings = list(sparse_model.embed([query_text]))
        query_emb = query_embeddings[0]

        # Search with sparse vector
        results = client.query_points(
            collection_name=collection_name,
            query=models.SparseVector(
                indices=query_emb.indices.tolist(),
                values=query_emb.values.tolist(),
            ),
            using=vector_name,
            limit=max_k,
            with_payload=True,
        )

        retrieved_ids = [p.payload.get("product_id", "") for p in results.points]

        retrieved_results.append({
            "query_id": q["query_id"],
            "retrieved_ids": retrieved_ids,
        })

    return evaluate_retrieval(
        retrieved_results=retrieved_results,
        ground_truth=queries,
        k_values=k_values,
    )


def run_baseline_evaluation(
    products: List[Dict],
    queries: List[Dict],
    collection_name: str = "esci_baselines",
    recreate: bool = True,
) -> Dict[str, Dict[str, float]]:
    """
    Run full baseline evaluation with BM25 and SPLADE.

    Args:
        products: List of product dicts for indexing
        queries: List of query dicts with relevance labels
        collection_name: Qdrant collection name
        recreate: Recreate collection from scratch

    Returns:
        Dict mapping model_name -> metrics
    """
    client = get_qdrant_client()

    # Create collection
    logger.info("Creating baseline collection...")
    create_baseline_collection(
        client=client,
        collection_name=collection_name,
        enable_bm25=True,
        enable_splade=True,
        recreate=recreate,
    )

    # Index products with FastEmbed
    logger.info(f"Indexing {len(products)} products with FastEmbed...")
    index_with_fastembed(
        client=client,
        collection_name=collection_name,
        documents=products,
    )

    results = {}

    # Evaluate BM25
    logger.info("Evaluating BM25 baseline...")
    results["bm25"] = evaluate_baseline(
        client=client,
        collection_name=collection_name,
        queries=queries,
        model_name=BM25_MODEL,
        vector_name="bm25",
    )
    print_metrics(results["bm25"], "BM25 Baseline")

    # Evaluate SPLADE
    logger.info("Evaluating SPLADE baseline...")
    results["splade"] = evaluate_baseline(
        client=client,
        collection_name=collection_name,
        queries=queries,
        model_name=SPLADE_MODEL,
        vector_name="splade",
    )
    print_metrics(results["splade"], "SPLADE Baseline (Off-the-shelf)")

    return results


def run_dense_evaluation(
    products: List[Dict],
    queries: List[Dict],
    collection_name: str = "esci_dense",
    recreate: bool = True,
) -> Dict[str, float]:
    """
    Run dense embedding baseline evaluation.

    Args:
        products: List of product dicts for indexing
        queries: List of query dicts with relevance labels
        collection_name: Qdrant collection name
        recreate: Recreate collection from scratch

    Returns:
        Dict of evaluation metrics
    """
    client = get_qdrant_client()

    # Create collection with dense vectors only
    logger.info("Creating dense baseline collection...")
    create_baseline_collection(
        client=client,
        collection_name=collection_name,
        enable_bm25=False,
        enable_splade=False,
        enable_dense=True,
        recreate=recreate,
    )

    # Index products with dense embeddings
    logger.info(f"Indexing {len(products)} products with dense embeddings...")
    index_with_dense(
        client=client,
        collection_name=collection_name,
        documents=products,
    )

    # Evaluate
    logger.info("Evaluating dense baseline...")
    metrics = evaluate_dense(
        client=client,
        collection_name=collection_name,
        queries=queries,
    )
    print_metrics(metrics, f"Dense Baseline ({DENSE_MODEL})")

    return metrics


def cleanup_baseline_collection(
    client: QdrantClient,
    collection_name: str = "esci_baselines",
) -> None:
    """Delete baseline collection."""
    try:
        client.delete_collection(collection_name)
        logger.info(f"Deleted collection: {collection_name}")
    except Exception as e:
        logger.warning(f"Failed to delete {collection_name}: {e}")
