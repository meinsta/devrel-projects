"""
Qdrant service for vector database operations.
"""

from typing import List, Dict, Any, Optional
from qdrant_client import QdrantClient, AsyncQdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
    SearchRequest as QdrantSearchRequest
)
from fastembed import TextEmbedding
import logging
from uuid import uuid4

logger = logging.getLogger(__name__)


class QdrantService:
    """Service for interacting with Qdrant vector database."""
    
    def __init__(
        self,
        url: str,
        api_key: Optional[str] = None,
        collection_name: str = "legal_docs",
        embedding_model: str = "BAAI/bge-small-en-v1.5"
    ):
        """
        Initialize Qdrant service.
        
        Args:
            url: Qdrant server URL
            api_key: Optional API key for Qdrant Cloud
            collection_name: Name of the collection
            embedding_model: FastEmbed model name
        """
        self.collection_name = collection_name
        self.embedding_model_name = embedding_model
        
        # Initialize sync client for non-async operations
        if api_key:
            self.client = QdrantClient(url=url, api_key=api_key)
        else:
            self.client = QdrantClient(url=url)
        
        # Initialize embedding model
        self.embedding_model = TextEmbedding(model_name=embedding_model)
        
        logger.info(f"Qdrant service initialized: {url}, collection: {collection_name}")
    
    def _embed_text(self, text: str) -> List[float]:
        """Generate embedding for text."""
        embeddings = list(self.embedding_model.embed([text]))
        return embeddings[0].tolist()
    
    def _embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts."""
        embeddings = list(self.embedding_model.embed(texts))
        return [emb.tolist() for emb in embeddings]
    
    async def health_check(self) -> bool:
        """Check if Qdrant is accessible."""
        try:
            collections = self.client.get_collections()
            return True
        except Exception as e:
            logger.error(f"Qdrant health check failed: {e}")
            return False
    
    async def collection_exists(self) -> bool:
        """Check if collection exists."""
        try:
            collections = self.client.get_collections()
            return any(c.name == self.collection_name for c in collections.collections)
        except Exception as e:
            logger.error(f"Error checking collection: {e}")
            return False
    
    async def create_collection(self, vector_size: int = 384, recreate: bool = False):
        """
        Create collection if it doesn't exist.
        
        Args:
            vector_size: Dimension of vectors (384 for bge-small)
            recreate: Delete existing collection first
        """
        try:
            exists = await self.collection_exists()
            
            if exists and recreate:
                logger.info(f"Deleting existing collection: {self.collection_name}")
                self.client.delete_collection(self.collection_name)
                exists = False
            
            if not exists:
                logger.info(f"Creating collection: {self.collection_name}")
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(
                        size=vector_size,
                        distance=Distance.COSINE
                    )
                )
                logger.info("Collection created successfully")
            else:
                logger.info(f"Collection {self.collection_name} already exists")
        
        except Exception as e:
            logger.error(f"Error creating collection: {e}")
            raise
    
    async def upsert_documents(self, documents: List[Dict[str, Any]]):
        """
        Upsert documents into collection.
        
        Args:
            documents: List of document dictionaries with 'text' and metadata
        """
        try:
            # Extract texts and prepare points
            texts = [doc['text'] for doc in documents]
            embeddings = self._embed_texts(texts)
            
            points = []
            for i, (doc, embedding) in enumerate(zip(documents, embeddings)):
                point = PointStruct(
                    id=doc.get('id', str(uuid4())),
                    vector=embedding,
                    payload={
                        'text': doc['text'],
                        'document_id': doc.get('document_id', ''),
                        'title': doc.get('title', ''),
                        'section': doc.get('section', ''),
                        'source': doc.get('source', ''),
                        'citation': doc.get('citation', ''),
                        'chunk_index': doc.get('chunk_index', 0),
                        'keywords': doc.get('keywords', [])
                    }
                )
                points.append(point)
            
            # Upsert in batches
            batch_size = 100
            for i in range(0, len(points), batch_size):
                batch = points[i:i + batch_size]
                self.client.upsert(
                    collection_name=self.collection_name,
                    points=batch
                )
            
            logger.info(f"Upserted {len(points)} documents")
        
        except Exception as e:
            logger.error(f"Error upserting documents: {e}")
            raise
    
    async def search(
        self,
        query: str,
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None,
        score_threshold: Optional[float] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for similar documents using vector similarity.
        
        Args:
            query: Query text
            top_k: Number of results
            filters: Optional metadata filters
            score_threshold: Minimum similarity score
            
        Returns:
            List of search results with scores and metadata
        """
        try:
            # Generate query embedding
            query_embedding = self._embed_text(query)
            
            # Build filter
            query_filter = None
            if filters:
                conditions = []
                for key, value in filters.items():
                    conditions.append(
                        FieldCondition(
                            key=key,
                            match=MatchValue(value=value)
                        )
                    )
                if conditions:
                    query_filter = Filter(must=conditions)
            
            # Search
            results = self.client.search(
                collection_name=self.collection_name,
                query_vector=query_embedding,
                query_filter=query_filter,
                limit=top_k,
                score_threshold=score_threshold
            )
            
            # Format results
            formatted_results = []
            for result in results:
                formatted_results.append({
                    'text': result.payload.get('text', ''),
                    'score': result.score,
                    'metadata': {
                        'document_id': result.payload.get('document_id', ''),
                        'title': result.payload.get('title', ''),
                        'section': result.payload.get('section', ''),
                        'source': result.payload.get('source', ''),
                        'citation': result.payload.get('citation', ''),
                        'chunk_index': result.payload.get('chunk_index', 0)
                    }
                })
            
            logger.info(f"Found {len(formatted_results)} results for query: {query[:50]}...")
            return formatted_results
        
        except Exception as e:
            logger.error(f"Error searching: {e}")
            raise
    
    async def get_all_documents(self) -> List[Dict[str, Any]]:
        """Get all unique documents in the collection."""
        try:
            # Scroll through all points
            points, _ = self.client.scroll(
                collection_name=self.collection_name,
                limit=1000,
                with_payload=True,
                with_vectors=False
            )
            
            # Group by document_id
            documents = {}
            for point in points:
                doc_id = point.payload.get('document_id', '')
                if doc_id and doc_id not in documents:
                    documents[doc_id] = {
                        'document_id': doc_id,
                        'title': point.payload.get('title', ''),
                        'source': point.payload.get('source', ''),
                        'citation': point.payload.get('citation', ''),
                        'num_chunks': 0
                    }
                if doc_id in documents:
                    documents[doc_id]['num_chunks'] += 1
            
            return list(documents.values())
        
        except Exception as e:
            logger.error(f"Error getting documents: {e}")
            raise
    
    async def get_document_by_id(self, document_id: str) -> List[Dict[str, Any]]:
        """Get all chunks for a specific document."""
        try:
            # Search with filter
            points, _ = self.client.scroll(
                collection_name=self.collection_name,
                scroll_filter=Filter(
                    must=[
                        FieldCondition(
                            key="document_id",
                            match=MatchValue(value=document_id)
                        )
                    ]
                ),
                limit=1000,
                with_payload=True,
                with_vectors=False
            )
            
            # Sort by chunk_index
            chunks = sorted(
                [p.payload for p in points],
                key=lambda x: x.get('chunk_index', 0)
            )
            
            return chunks
        
        except Exception as e:
            logger.error(f"Error getting document: {e}")
            raise

