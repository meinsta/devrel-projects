"""
Multi-Embedding Provider

Manages multiple embedding models for named vector support.
Each vector name maps to a different embedding model.
"""

from typing import Dict

from mcp_server_qdrant.embeddings.base import EmbeddingProvider
from mcp_server_qdrant.embeddings.fastembed import FastEmbedProvider


class MultiEmbeddingProvider:
    """
    Manages multiple embedding providers for named vector support.

    Example:
        provider = MultiEmbeddingProvider({
            "code": "jinaai/jina-embeddings-v2-base-code",
            "text": "sentence-transformers/all-MiniLM-L6-v2"
        })

        # Embed with specific model
        code_vectors = await provider.embed_documents("code", ["def foo(): pass"])
        text_vectors = await provider.embed_documents("text", ["A function definition"])
    """

    def __init__(self, vector_configs: Dict[str, str]):
        """
        Initialize with a mapping of vector names to model names.

        :param vector_configs: Dict mapping vector name to embedding model name
                              e.g., {"code": "jinaai/jina-embeddings-v2-base-code"}
        """
        self._providers: Dict[str, EmbeddingProvider] = {}
        self._vector_configs = vector_configs

        for vector_name, model_name in vector_configs.items():
            self._providers[vector_name] = FastEmbedProvider(model_name)

    def get_vector_names(self) -> list[str]:
        """Get all configured vector names."""
        return list(self._providers.keys())

    def get_provider(self, vector_name: str) -> EmbeddingProvider:
        """Get the embedding provider for a specific vector name."""
        if vector_name not in self._providers:
            raise ValueError(f"Unknown vector name: {vector_name}. Available: {self.get_vector_names()}")
        return self._providers[vector_name]

    def get_vector_size(self, vector_name: str) -> int:
        """Get the vector size for a specific vector name."""
        return self.get_provider(vector_name).get_vector_size()

    def get_all_vector_configs(self) -> Dict[str, int]:
        """Get all vector names and their sizes."""
        return {name: provider.get_vector_size() for name, provider in self._providers.items()}

    async def embed_documents(self, vector_name: str, documents: list[str]) -> list[list[float]]:
        """
        Embed documents using the specified vector's embedding model.

        :param vector_name: Name of the vector (e.g., "code", "text")
        :param documents: List of documents to embed
        :return: List of embedding vectors
        """
        provider = self.get_provider(vector_name)
        return await provider.embed_documents(documents)

    async def embed_query(self, vector_name: str, query: str) -> list[float]:
        """
        Embed a query using the specified vector's embedding model.

        :param vector_name: Name of the vector (e.g., "code", "text")
        :param query: Query string to embed
        :return: Embedding vector
        """
        provider = self.get_provider(vector_name)
        return await provider.embed_query(query)

    async def embed_all(self, documents: list[str]) -> Dict[str, list[list[float]]]:
        """
        Embed documents with ALL configured embedding models.

        :param documents: List of documents to embed
        :return: Dict mapping vector name to list of embeddings
        """
        results = {}
        for vector_name in self._providers:
            results[vector_name] = await self.embed_documents(vector_name, documents)
        return results

    async def embed_query_all(self, query: str) -> Dict[str, list[float]]:
        """
        Embed a query with ALL configured embedding models.

        :param query: Query string to embed
        :return: Dict mapping vector name to embedding vector
        """
        results = {}
        for vector_name in self._providers:
            results[vector_name] = await self.embed_query(vector_name, query)
        return results
