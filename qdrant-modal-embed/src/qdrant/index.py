"""Sparse Vector Indexing into Qdrant"""

import logging
from typing import Dict, List, Union

import numpy as np
import torch
from qdrant_client import QdrantClient, models
from sentence_transformers import SparseEncoder
from tqdm import tqdm

logger = logging.getLogger(__name__)


def sparse_embedding_to_qdrant(
    embedding: Union[Dict, torch.Tensor, np.ndarray],
) -> models.SparseVector:
    """
    Convert a sparse embedding to Qdrant SparseVector format.

    SparseEncoder can return different formats depending on configuration:
    - Dict with 'indices' and 'values' tensors
    - Sparse tensor (torch.sparse)
    - Dense tensor (only non-zero values are extracted)

    Args:
        embedding: Sparse embedding from SparseEncoder

    Returns:
        Qdrant SparseVector
    """
    if isinstance(embedding, dict):
        # Dict format: {"indices": tensor, "values": tensor}
        indices = embedding["indices"]
        values = embedding["values"]

        if isinstance(indices, torch.Tensor):
            indices = indices.cpu().numpy()
        if isinstance(values, torch.Tensor):
            values = values.cpu().numpy()

        return models.SparseVector(
            indices=indices.flatten().tolist(),
            values=values.flatten().tolist(),
        )

    elif isinstance(embedding, torch.Tensor):
        if embedding.is_sparse:
            # Sparse tensor
            indices = embedding.coalesce().indices()[0].cpu().numpy()
            values = embedding.coalesce().values().cpu().numpy()
        else:
            # Dense tensor - extract non-zero
            embedding = embedding.cpu()
            nonzero = embedding.nonzero().squeeze(-1)
            if nonzero.dim() == 0:
                nonzero = nonzero.unsqueeze(0)
            indices = nonzero.numpy()
            values = embedding[nonzero].numpy()

        return models.SparseVector(
            indices=indices.flatten().tolist(),
            values=values.flatten().tolist(),
        )

    elif isinstance(embedding, np.ndarray):
        # Numpy array - extract non-zero
        nonzero = np.nonzero(embedding)[0]
        values = embedding[nonzero]

        return models.SparseVector(
            indices=nonzero.tolist(),
            values=values.tolist(),
        )

    else:
        raise ValueError(f"Unsupported embedding type: {type(embedding)}")


def index_sparse_vectors(
    client: QdrantClient,
    collection_name: str,
    model: SparseEncoder,
    documents: List[Dict],
    vector_name: str = "text",
    batch_size: int = 32,
    show_progress: bool = True,
) -> int:
    """
    Index documents with SPLADE sparse vectors into Qdrant.

    Args:
        client: Qdrant client
        collection_name: Target collection name
        model: SparseEncoder model for embedding
        documents: List of dicts with:
            - "product_id": str (unique identifier)
            - "text": str (text to encode)
            - "payload": dict (optional metadata)
        vector_name: Name of sparse vector field
        batch_size: Batch size for encoding
        show_progress: Show progress bar

    Returns:
        Number of indexed documents
    """
    total_indexed = 0
    iterator = range(0, len(documents), batch_size)

    if show_progress:
        iterator = tqdm(iterator, desc="Indexing sparse vectors")

    for i in iterator:
        batch_docs = documents[i : i + batch_size]
        batch_texts = [doc["text"] for doc in batch_docs]

        # Encode batch with SparseEncoder
        embeddings = model.encode(
            batch_texts,
            convert_to_tensor=True,
            show_progress_bar=False,
        )

        # Build points
        points = []
        for j, (doc, emb) in enumerate(zip(batch_docs, embeddings)):
            sparse_vector = sparse_embedding_to_qdrant(emb)

            point = models.PointStruct(
                id=i + j,  # Sequential ID
                vector={vector_name: sparse_vector},
                payload={
                    "product_id": doc["product_id"],
                    "text": doc["text"],
                    **doc.get("payload", {}),
                },
            )
            points.append(point)

        # Upsert batch
        client.upsert(
            collection_name=collection_name,
            points=points,
        )
        total_indexed += len(points)

    logger.info(f"Indexed {total_indexed} documents into {collection_name}")
    return total_indexed


def update_sparse_vectors(
    client: QdrantClient,
    collection_name: str,
    model: SparseEncoder,
    product_ids: List[str],
    texts: List[str],
    vector_name: str = "text",
    batch_size: int = 32,
) -> int:
    """
    Update sparse vectors for existing documents.

    Use this during ANCE training to re-embed products with updated model.

    Args:
        client: Qdrant client
        collection_name: Target collection name
        model: Updated SparseEncoder model
        product_ids: List of product IDs to update
        texts: Corresponding texts to re-encode
        vector_name: Name of sparse vector field
        batch_size: Batch size for encoding

    Returns:
        Number of updated vectors
    """
    total_updated = 0

    for i in tqdm(range(0, len(product_ids), batch_size), desc="Updating vectors"):
        batch_ids = product_ids[i : i + batch_size]
        batch_texts = texts[i : i + batch_size]

        # Re-encode
        embeddings = model.encode(
            batch_texts,
            convert_to_tensor=True,
            show_progress_bar=False,
        )

        # Update vectors
        for pid, emb in zip(batch_ids, embeddings):
            sparse_vector = sparse_embedding_to_qdrant(emb)

            # Find point by product_id and update
            # Note: This requires searching by payload, which is slower
            # For production, consider using a point_id -> product_id mapping
            results = client.scroll(
                collection_name=collection_name,
                scroll_filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="product_id",
                            match=models.MatchValue(value=pid),
                        )
                    ]
                ),
                limit=1,
            )

            if results[0]:
                point_id = results[0][0].id
                client.update_vectors(
                    collection_name=collection_name,
                    points=[
                        models.PointVectors(
                            id=point_id,
                            vector={vector_name: sparse_vector},
                        )
                    ],
                )
                total_updated += 1

    logger.info(f"Updated {total_updated} vectors in {collection_name}")
    return total_updated
