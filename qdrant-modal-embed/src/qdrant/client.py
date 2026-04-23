"""Qdrant Client Wrapper for Sparse Vector Operations"""

import logging
import os
from typing import Optional

from qdrant_client import QdrantClient, models

from src.config import settings

logger = logging.getLogger(__name__)


def get_qdrant_client(
    url: Optional[str] = None,
    api_key: Optional[str] = None,
) -> QdrantClient:
    """
    Get a Qdrant client instance.

    Args:
        url: Qdrant cluster URL (defaults to env/settings)
        api_key: Qdrant API key (defaults to env/settings)

    Returns:
        QdrantClient instance
    """
    url = url or os.environ.get("QDRANT_URL") or settings.qdrant_url
    api_key = api_key or os.environ.get("QDRANT_API_KEY") or settings.qdrant_api_key

    if not url:
        raise ValueError(
            "Qdrant URL not configured. Set QDRANT_URL environment variable "
            "or update settings."
        )

    client = QdrantClient(
        url=url,
        api_key=api_key if api_key else None,
        timeout=60,
    )

    logger.info(f"Connected to Qdrant at {url}")
    return client


def create_sparse_collection(
    client: QdrantClient,
    collection_name: str,
    vector_name: str = "text",
    on_disk: bool = False,
    recreate: bool = False,
) -> None:
    """
    Create a Qdrant collection for SPLADE sparse vectors.

    SPLADE outputs sparse vectors with dimension = vocabulary size (~30,522).
    Only non-zero dimensions are stored, making it memory-efficient.

    Args:
        client: Qdrant client
        collection_name: Name for the collection
        vector_name: Name of the sparse vector field (default: "text")
        on_disk: Store vectors on disk for large collections
        recreate: Delete existing collection if it exists
    """
    if recreate:
        try:
            client.delete_collection(collection_name)
            logger.info(f"Deleted existing collection: {collection_name}")
        except Exception:
            pass

    try:
        client.create_collection(
            collection_name=collection_name,
            vectors_config={},  # No dense vectors
            sparse_vectors_config={
                vector_name: models.SparseVectorParams(
                    index=models.SparseIndexParams(
                        on_disk=on_disk,
                    ),
                )
            },
        )
        logger.info(f"Created sparse collection: {collection_name}")
    except Exception as e:
        if "already exists" in str(e).lower():
            logger.info(f"Collection {collection_name} already exists")
        else:
            raise


def delete_collection(
    client: QdrantClient,
    collection_name: str,
) -> None:
    """
    Delete a Qdrant collection.

    Args:
        client: Qdrant client
        collection_name: Name of collection to delete
    """
    try:
        client.delete_collection(collection_name)
        logger.info(f"Deleted collection: {collection_name}")
    except Exception as e:
        logger.warning(f"Failed to delete collection {collection_name}: {e}")


def collection_exists(
    client: QdrantClient,
    collection_name: str,
) -> bool:
    """
    Check if a collection exists.

    Args:
        client: Qdrant client
        collection_name: Name of collection

    Returns:
        True if collection exists
    """
    try:
        client.get_collection(collection_name)
        return True
    except Exception:
        return False


def get_collection_info(
    client: QdrantClient,
    collection_name: str,
) -> dict:
    """
    Get information about a collection.

    Args:
        client: Qdrant client
        collection_name: Name of collection

    Returns:
        Collection information dict
    """
    info = client.get_collection(collection_name)
    return {
        "name": collection_name,
        "points_count": info.points_count,
        "vectors_count": info.vectors_count,
        "indexed_vectors_count": info.indexed_vectors_count,
        "status": info.status,
    }
