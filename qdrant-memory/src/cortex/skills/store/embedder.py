"""Embedder - Text embedding via fastembed.

Lazy-loads the embedding model to avoid startup cost.
Provides a simple embed() interface for text -> vector.
"""

import os
from typing import List, Optional

# Default model - small, fast, good for memory/retrieval
DEFAULT_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


class Embedder:
    """Lazy-loading text embedder using fastembed.

    Usage:
        embedder = Embedder()
        vector = embedder.embed("some text")
        vectors = embedder.embed_batch(["text1", "text2"])
    """

    def __init__(self, model: Optional[str] = None):
        """Initialize embedder with optional model override.

        Args:
            model: Model name (default: all-MiniLM-L6-v2)
        """
        self.model_name = model or os.environ.get("EMBEDDING_MODEL", DEFAULT_MODEL)
        self._model = None

    @property
    def model(self):
        """Lazy-load the embedding model."""
        if self._model is None:
            from fastembed import TextEmbedding

            self._model = TextEmbedding(model_name=self.model_name)
        return self._model

    @property
    def dimension(self) -> int:
        """Get embedding dimension for the current model."""
        # all-MiniLM-L6-v2 produces 384-dim vectors
        # Other models may differ
        model_dims = {
            "sentence-transformers/all-MiniLM-L6-v2": 384,
            "BAAI/bge-small-en-v1.5": 384,
            "BAAI/bge-base-en-v1.5": 768,
        }
        return model_dims.get(self.model_name, 384)

    def embed(self, text: str) -> List[float]:
        """Embed a single text string.

        Args:
            text: Text to embed

        Returns:
            Embedding vector as list of floats
        """
        # fastembed returns a generator, convert to list
        embeddings = list(self.model.embed([text]))
        return embeddings[0].tolist()

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Embed multiple texts efficiently.

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors
        """
        if not texts:
            return []
        embeddings = list(self.model.embed(texts))
        return [e.tolist() for e in embeddings]

    def health(self) -> dict:
        """Check embedder health and return model info."""
        try:
            # Try to load model if not loaded
            _ = self.model
            return {
                "status": "healthy",
                "model": self.model_name,
                "dimension": self.dimension,
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "model": self.model_name,
                "error": str(e),
            }


# Singleton instance for shared use
_embedder: Optional[Embedder] = None


def get_embedder() -> Embedder:
    """Get the global embedder instance."""
    global _embedder
    if _embedder is None:
        _embedder = Embedder()
    return _embedder
