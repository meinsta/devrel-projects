"""Vector store module using Qdrant with FastEmbed."""

from typing import List, Dict, Any, Optional
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
    PayloadSchemaType
)
import logging
from uuid import uuid4
from rich.progress import Progress, BarColumn, TextColumn, TimeRemainingColumn, SpinnerColumn
from rich.console import Console

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
console = Console()


class QdrantVectorStore:
    """Manage Qdrant vector store with FastEmbed embeddings."""
    
    def __init__(
        self, 
        collection_name: str = "housing_statutes",
        embedding_model: str = "BAAI/bge-small-en-v1.5",
        path: Optional[str] = None,
        use_memory: bool = True,
        cloud_url: Optional[str] = None,
        cloud_api_key: Optional[str] = None
    ):
        """
        Initialize Qdrant client with FastEmbed.
        
        Args:
            collection_name: Name of the collection
            embedding_model: FastEmbed model name
            path: Path for persistent storage (None for in-memory)
            use_memory: Use in-memory mode if True
            cloud_url: Qdrant Cloud URL (e.g., https://xyz.cloud.qdrant.io)
            cloud_api_key: Qdrant Cloud API key
        """
        self.collection_name = collection_name
        self.embedding_model = embedding_model
        
        # Initialize Qdrant client
        if cloud_url and cloud_api_key:
            # Ensure URL has port 6333 for Qdrant Cloud (required)
            clean_url = cloud_url.rstrip("/")
            if ":6333" not in clean_url:
                clean_url = f"{clean_url}:6333"
            # Ensure URL starts with https://
            if not clean_url.startswith("http"):
                clean_url = f"https://{clean_url}"
            
            logger.info(f"Initializing Qdrant Cloud client: {clean_url}")
            logger.info(f"API Key: {'*' * (len(cloud_api_key) - 4)}{cloud_api_key[-4:] if len(cloud_api_key) > 4 else '****'}")
            
            try:
                self.client = QdrantClient(
                    url=clean_url,
                    api_key=cloud_api_key,
                    check_compatibility=False  # Disable compatibility check for cloud
                )
                # Test connection by getting collections
                self.client.get_collections()
                logger.info("Successfully connected to Qdrant Cloud")
            except Exception as e:
                logger.error(f"Failed to connect to Qdrant Cloud: {e}")
                logger.error("\nTroubleshooting:")
                logger.error(f"  1. URL used: {clean_url}")
                logger.error(f"  2. API Key length: {len(cloud_api_key)} characters")
                logger.error("  3. Verify your QDRANT_CLOUD_URL format:")
                logger.error("     ✓ Correct: https://xxx-xxx-xxx.us-west-2-0.aws.cloud.qdrant.io:6333")
                logger.error("  4. Verify your QDRANT_API_KEY:")
                logger.error("     - Get it from Qdrant Cloud dashboard")
                logger.error("     - Ensure it has 'read' and 'write' permissions")
                logger.error("     - Check it's not expired")
                raise
        elif use_memory and path is None:
            logger.info("Initializing Qdrant client in-memory mode")
            self.client = QdrantClient(":memory:")
        else:
            logger.info(f"Initializing Qdrant client with path: {path}")
            self.client = QdrantClient(path=path or "./qdrant_data")
        
        # Vector dimensions for BAAI/bge-small-en-v1.5
        self.vector_size = 384
        
    def create_collection(self, recreate: bool = False, use_fastembed: bool = True):
        """
        Prepare collection for FastEmbed. FastEmbed's add() will create it automatically.
        
        Args:
            recreate: If True, delete existing collection so FastEmbed can recreate it
            use_fastembed: If True, let FastEmbed create collection (recommended)
        """
        # Check if collection exists
        collections = self.client.get_collections().collections
        exists = any(c.name == self.collection_name for c in collections)
        
        if exists:
            if recreate:
                # User explicitly wants to recreate
                logger.info(f"Deleting existing collection: {self.collection_name} (--recreate flag)")
                self.client.delete_collection(self.collection_name)
                logger.info("Collection deleted. FastEmbed will create it with correct configuration.")
            elif use_fastembed:
                # Check if collection is empty (has no points)
                try:
                    collection_info = self.client.get_collection(self.collection_name)
                    points_count = collection_info.points_count if hasattr(collection_info, 'points_count') else 0
                    
                    if points_count == 0:
                        # Empty collection - safe to delete for FastEmbed
                        logger.info(f"Deleting empty collection: {self.collection_name}")
                        logger.info("  (FastEmbed needs to create collection with its own configuration)")
                        self.client.delete_collection(self.collection_name)
                        logger.info("Collection deleted. FastEmbed will create it with correct configuration.")
                    else:
                        # Collection has data - warn but don't delete
                        logger.warning(f"Collection {self.collection_name} exists with {points_count} points")
                        logger.warning("Cannot auto-delete collection with data. Use --recreate flag to force rebuild.")
                        raise ValueError(f"Collection {self.collection_name} exists but may be incompatible with FastEmbed. Use --recreate to rebuild.")
                except Exception as e:
                    # If we can't check, assume it's safe to try (FastEmbed will handle errors)
                    logger.warning(f"Could not check collection status: {e}")
                    logger.info("Will attempt to use existing collection. FastEmbed will handle compatibility.")
            else:
                logger.info(f"Collection {self.collection_name} already exists")
                return
        
        if use_fastembed:
            # Don't create collection manually - let FastEmbed's add() method create it
            # FastEmbed will create the collection with the correct configuration automatically
            logger.info(f"Collection {self.collection_name} will be created automatically by FastEmbed on first add()")
            return
        
        # Manual collection creation (for non-FastEmbed use cases only)
        logger.info(f"Creating collection manually: {self.collection_name}")
        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config=VectorParams(
                size=self.vector_size,
                distance=Distance.COSINE
            )
        )
        logger.info("Collection created successfully")
    
    def upsert_chunks(self, chunks: List[Dict[str, Any]], batch_size: int = 500):
        """
        Upsert statutes to Qdrant with automatic embedding via FastEmbed.
        
        Note: These are not actually "chunks" - each item is a full statute
        kept as a single unit (no chunking). The term "chunk" is used for
        API consistency, but each statute = one passage = one "chunk".
        
        Uses FastEmbed's add() method which handles batching and embedding automatically.
        Increased default batch_size to 500 for better performance with large datasets.
        
        Args:
            chunks: List of statute dictionaries (one per statute, no splitting)
            batch_size: Number of statutes to process per batch (default 500 for better performance)
        """
        if not chunks:
            logger.warning("No statutes to upsert")
            return
        
        total_chunks = len(chunks)
        num_batches = (total_chunks + batch_size - 1) // batch_size
        
        logger.info(f"Uploading {total_chunks:,} statutes in {num_batches} batches (batch_size={batch_size})")
        
        # Use Rich progress bar for better visual feedback
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TextColumn("({task.completed}/{task.total})"),
            TimeRemainingColumn(),
            console=console,
        ) as progress:
            task = progress.add_task(
                f"[cyan]Upserting {total_chunks:,} statutes[/cyan]",
                total=num_batches
            )
            
            # Process in batches
            for i in range(0, len(chunks), batch_size):
                batch = chunks[i:i + batch_size]
                
                # Prepare points for upsert
                points = []
                texts = []
                
                for chunk in batch:
                    # Generate UUID for point ID (Qdrant requires integer or UUID, not string like "0_0")
                    point_id = str(uuid4())
                    
                    # Prepare payload (metadata)
                    payload = {
                        'text': chunk['text'],
                        'citation': chunk['citation'],
                        'state': chunk['state'],
                        'statute_idx': chunk['statute_idx'],
                        'chunk_idx': chunk['chunk_idx'],
                        'path': chunk.get('path', ''),
                        'token_count': chunk.get('token_count', 0),
                        'chunk_id': chunk.get('chunk_id', '')  # Store original chunk_id in metadata
                    }
                    
                    texts.append(chunk['text'])
                    points.append((point_id, payload))
                
                # Embed texts using FastEmbed and upsert
                try:
                    # Use add method with documents - Qdrant will handle embedding
                    self.client.add(
                        collection_name=self.collection_name,
                        documents=texts,
                        metadata=[p[1] for p in points],
                        ids=[p[0] for p in points]
                    )
                    
                    # Update progress
                    progress.update(task, advance=1)
                    
                except AssertionError as e:
                    # Collection exists but is incompatible with FastEmbed
                    if "incompatible vector params" in str(e) or "Collection have incompatible" in str(e):
                        logger.warning(f"Collection {self.collection_name} has incompatible configuration")
                        logger.info("Deleting collection to let FastEmbed recreate it with correct settings...")
                        try:
                            self.client.delete_collection(self.collection_name)
                            logger.info("Collection deleted. Retrying add()...")
                            # Retry the add() - FastEmbed will create collection automatically
                            self.client.add(
                                collection_name=self.collection_name,
                                documents=texts,
                                metadata=[p[1] for p in points],
                                ids=[p[0] for p in points]
                            )
                            progress.update(task, advance=1)
                        except Exception as retry_error:
                            logger.error(f"Error after retry: {retry_error}")
                            raise
                    else:
                        raise
                except Exception as e:
                    logger.error(f"Error upserting batch {i//batch_size}: {e}")
                    raise
        
        # Create payload indexes for filtering (if they don't exist)
        try:
            self.client.create_payload_index(
                collection_name=self.collection_name,
                field_name='state',
                field_schema=PayloadSchemaType.KEYWORD
            )
            logger.info("Created payload index for 'state' field")
        except Exception as e:
            if 'already exists' not in str(e).lower():
                logger.debug(f"Could not create index for 'state': {e}")
        
        logger.info(f"All {total_chunks:,} statutes upserted successfully")
    
    def get_collection_info(self) -> Dict[str, Any]:
        """
        Get information about the collection.
        
        Returns:
            Dictionary with collection statistics
        """
        try:
            info = self.client.get_collection(self.collection_name)
            
            # Handle different vector config structures (dict vs object)
            vector_size = 'N/A'
            try:
                if hasattr(info.config, 'params') and hasattr(info.config.params, 'vectors'):
                    vectors = info.config.params.vectors
                    if isinstance(vectors, dict):
                        # FastEmbed collections might return dict
                        vector_size = vectors.get('size', 'N/A')
                    elif hasattr(vectors, 'size'):
                        # Standard Qdrant collections
                        vector_size = vectors.size
                    elif isinstance(vectors, (list, tuple)) and len(vectors) > 0:
                        # Some collections might have vectors as a list
                        first_vec = vectors[0]
                        if isinstance(first_vec, dict):
                            vector_size = first_vec.get('size', 'N/A')
                        elif hasattr(first_vec, 'size'):
                            vector_size = first_vec.size
            except (AttributeError, TypeError, IndexError):
                # If we can't determine vector size, that's okay - just use 'N/A'
                pass
            
            return {
                'name': self.collection_name,
                'vector_size': vector_size,
                'points_count': info.points_count,
                'vectors_count': info.vectors_count if hasattr(info, 'vectors_count') else info.points_count,
            }
        except Exception as e:
            logger.debug(f"Error getting collection info: {e}")
            # Return minimal info even on error
            return {
                'name': self.collection_name,
                'vector_size': 'N/A',
                'points_count': 0,
                'vectors_count': 0,
            }
    
    def collection_exists(self) -> bool:
        """
        Check if collection exists.
        
        Returns:
            True if collection exists, False otherwise
        """
        try:
            collections = self.client.get_collections().collections
            return any(c.name == self.collection_name for c in collections)
        except Exception as e:
            logger.error(f"Error checking collection existence: {e}")
            return False


def initialize_vector_store(
    chunks: List[Dict[str, Any]],
    collection_name: str = "housing_statutes",
    recreate: bool = False,
    batch_size: int = 100,
    use_memory: bool = True,
    path: Optional[str] = None,
    cloud_url: Optional[str] = None,
    cloud_api_key: Optional[str] = None
) -> QdrantVectorStore:
    """
    Convenience function to initialize vector store and load chunks.
    
    Args:
        chunks: List of chunk dictionaries
        collection_name: Name of the collection
        recreate: Recreate collection if it exists
        batch_size: Batch size for upserting
        use_memory: Use in-memory mode
        path: Path for persistent storage
        cloud_url: Qdrant Cloud URL
        cloud_api_key: Qdrant Cloud API key
        
    Returns:
        Initialized QdrantVectorStore instance
    """
    store = QdrantVectorStore(
        collection_name=collection_name,
        use_memory=use_memory,
        path=path,
        cloud_url=cloud_url,
        cloud_api_key=cloud_api_key
    )
    
    store.create_collection(recreate=recreate)
    store.upsert_chunks(chunks, batch_size=batch_size)
    
    return store

