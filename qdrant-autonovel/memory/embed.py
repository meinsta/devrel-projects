"""Embedding utilities using fastembed (local, zero API cost)."""

from fastembed import TextEmbedding, SparseTextEmbedding
from qdrant_client.models import SparseVector

# Lazy singletons to avoid loading models until needed
_dense_model = None
_sparse_model = None


def _get_dense_model():
    global _dense_model
    if _dense_model is None:
        _dense_model = TextEmbedding("BAAI/bge-base-en-v1.5")
    return _dense_model


def _get_sparse_model():
    global _sparse_model
    if _sparse_model is None:
        _sparse_model = SparseTextEmbedding("Qdrant/bm25")
    return _sparse_model


def embed_dense(text: str) -> list[float]:
    """Generate a 768-dim dense embedding from text."""
    model = _get_dense_model()
    embeddings = list(model.embed([text]))
    return embeddings[0].tolist()


def embed_sparse(text: str) -> SparseVector:
    """Generate a sparse BM25 embedding from text."""
    model = _get_sparse_model()
    embeddings = list(model.embed([text]))
    sparse = embeddings[0]
    return SparseVector(
        indices=sparse.indices.tolist(),
        values=sparse.values.tolist(),
    )
