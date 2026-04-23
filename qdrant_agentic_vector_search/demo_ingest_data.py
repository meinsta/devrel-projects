"""
Demo: Data Ingestion for Qdrant Hybrid Search

This script ingests California housing statutes into Qdrant with:
- Dense vectors (semantic embeddings via BGE-small)
- Sparse vectors (keyword matching via BM42)
- Hybrid search ready for RAG demos

Collection created: california_housing_statutes_full

Usage:
    python demo_ingest_data.py
    
Optional flags:
    --limit N         Only ingest N statutes (for testing)
    --recreate        Delete and recreate collection if exists
"""

import os
import sys
import time
import argparse
from dotenv import load_dotenv
from datasets import load_dataset
from qdrant_client import QdrantClient, models
from qdrant_client.models import Distance, VectorParams, SparseVectorParams, SparseIndexParams
from fastembed import TextEmbedding, SparseTextEmbedding

load_dotenv()

# Configuration
QDRANT_URL = os.getenv('QDRANT_CLOUD_URL')
QDRANT_API_KEY = os.getenv('QDRANT_API_KEY')
COLLECTION_NAME = "california_housing_statutes_full"

# Embedding models
DENSE_MODEL_NAME = "BAAI/bge-small-en-v1.5"
SPARSE_MODEL_NAME = "Qdrant/bm42-all-minilm-l6-v2-attentions"

# Vector configuration
DENSE_VECTOR_SIZE = 384
DENSE_VECTOR_NAME = "dense"
SPARSE_VECTOR_NAME = "sparse"

# Batching
BATCH_SIZE = 32
RATE_LIMIT_DELAY = 0.3  # seconds between batches


def print_header():
    """Print demo header."""
    print("\n" + "="*80)
    print("DEMO: DATA INGESTION FOR QDRANT HYBRID SEARCH")
    print("California Housing Law Statutes")
    print("="*80 + "\n")


def check_environment():
    """Validate required environment variables."""
    print("Checking environment...")
    
    if not QDRANT_URL:
        print("❌ Error: QDRANT_CLOUD_URL not set in .env")
        sys.exit(1)
    
    if not QDRANT_API_KEY:
        print("❌ Error: QDRANT_API_KEY not set in .env")
        sys.exit(1)
    
    print(f"✓ Qdrant URL: {QDRANT_URL}")
    print("✓ Environment configured\n")


def load_california_statutes(limit=None):
    """
    Load California statutes from HousingQA dataset.
    
    Args:
        limit: If set, only load this many statutes (for testing)
    
    Returns:
        List of statute dictionaries
    """
    print("STEP 1: Loading California Statutes")
    print("-" * 80)
    print("  → Downloading HousingQA dataset from HuggingFace...")
    
    # Load full corpus
    dataset = load_dataset(
        "reglab/housing_qa",
        "statutes",
        split="corpus",
        trust_remote_code=True
    )
    
    print(f"  → Loaded {len(dataset):,} total statutes")
    print("  → Filtering for California...")
    
    # Filter for California
    california_statutes = []
    for statute in dataset:
        if statute.get('state', '').lower() == 'california':
            california_statutes.append({
                'idx': statute['idx'],
                'citation': statute['citation'],
                'state': statute['state'],
                'text': statute['text'],
                'path': statute.get('path', '')
            })
            
            # Stop if limit reached
            if limit and len(california_statutes) >= limit:
                print(f"  → Limited to {limit} statutes (test mode)")
                break
    
    print(f"✓ Found {len(california_statutes):,} California statutes\n")
    return california_statutes


def create_or_check_collection(client, recreate=False):
    """
    Create Qdrant collection with dense + sparse vectors.
    
    Args:
        client: QdrantClient instance
        recreate: If True, delete existing collection
    """
    print("STEP 2: Setting Up Qdrant Collection")
    print("-" * 80)
    
    # Check if collection exists
    collections = client.get_collections().collections
    exists = any(c.name == COLLECTION_NAME for c in collections)
    
    if exists:
        if recreate:
            print(f"  → Collection '{COLLECTION_NAME}' exists. Deleting...")
            client.delete_collection(COLLECTION_NAME)
            print("  → Deleted")
        else:
            print(f"  → Collection '{COLLECTION_NAME}' already exists")
            print("  → Use --recreate flag to delete and recreate")
            
            # Get info
            info = client.get_collection(COLLECTION_NAME)
            print(f"  → Current count: {info.points_count:,} points")
            
            user_input = input("\n  Continue and add more statutes? (y/n): ")
            if user_input.lower() != 'y':
                print("\n✓ Exiting without changes\n")
                sys.exit(0)
            
            print("\n  → Will append to existing collection")
            return
    
    # Create new collection with dense + sparse vectors
    print(f"  → Creating collection: {COLLECTION_NAME}")
    print(f"  → Dense vector: {DENSE_MODEL_NAME} ({DENSE_VECTOR_SIZE}D)")
    print(f"  → Sparse vector: {SPARSE_MODEL_NAME}")
    
    client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config={
            DENSE_VECTOR_NAME: VectorParams(
                size=DENSE_VECTOR_SIZE,
                distance=Distance.COSINE
            )
        },
        sparse_vectors_config={
            SPARSE_VECTOR_NAME: SparseVectorParams(
                index=SparseIndexParams(
                    on_disk=False,
                )
            )
        }
    )
    
    print(f"✓ Collection created: {COLLECTION_NAME}\n")


def embed_and_upload(client, statutes, dense_model, sparse_model):
    """
    Generate embeddings and upload statutes to Qdrant.
    
    Args:
        client: QdrantClient instance
        statutes: List of statute dictionaries
        dense_model: TextEmbedding model
        sparse_model: SparseTextEmbedding model
    """
    print("STEP 3: Embedding and Uploading Statutes")
    print("-" * 80)
    
    total_batches = (len(statutes) + BATCH_SIZE - 1) // BATCH_SIZE
    print(f"  → Processing {len(statutes):,} statutes in {total_batches} batches")
    print(f"  → Batch size: {BATCH_SIZE}")
    print()
    
    start_time = time.time()
    
    # Get starting point ID (in case collection already has points)
    try:
        info = client.get_collection(COLLECTION_NAME)
        start_id = info.points_count
    except:
        start_id = 0
    
    for batch_idx in range(0, len(statutes), BATCH_SIZE):
        batch_num = batch_idx // BATCH_SIZE + 1
        batch = statutes[batch_idx:batch_idx + BATCH_SIZE]
        
        # Extract texts
        texts = [s['text'] for s in batch]
        
        # Generate dense embeddings
        dense_embeddings = list(dense_model.embed(texts))
        
        # Generate sparse embeddings
        sparse_embeddings = list(sparse_model.embed(texts))
        
        # Create points
        points = []
        for i, statute in enumerate(batch):
            point_id = start_id + batch_idx + i
            
            # Convert sparse embedding to Qdrant format
            sparse_values = models.SparseVector(
                indices=sparse_embeddings[i].indices.tolist(),
                values=sparse_embeddings[i].values.tolist()
            )
            
            points.append(
                models.PointStruct(
                    id=point_id,
                    vector={
                        DENSE_VECTOR_NAME: dense_embeddings[i].tolist(),
                        SPARSE_VECTOR_NAME: sparse_values
                    },
                    payload={
                        'statute_idx': statute['idx'],
                        'citation': statute['citation'],
                        'state': statute['state'],
                        'text': statute['text'],
                        'path': statute['path']
                    }
                )
            )
        
        # Upload batch
        client.upsert(
            collection_name=COLLECTION_NAME,
            points=points
        )
        
        # Progress
        progress = (batch_num / total_batches) * 100
        print(f"  [{batch_num}/{total_batches}] {progress:.1f}% - Uploaded {len(points)} statutes")
        
        # Rate limiting
        time.sleep(RATE_LIMIT_DELAY)
    
    elapsed = time.time() - start_time
    print(f"\n✓ Uploaded {len(statutes):,} statutes in {elapsed:.1f}s\n")


def verify_collection(client):
    """
    Verify collection was created successfully.
    
    Args:
        client: QdrantClient instance
    """
    print("STEP 4: Verifying Collection")
    print("-" * 80)
    
    # Get collection info
    info = client.get_collection(COLLECTION_NAME)
    
    print(f"  Collection: {COLLECTION_NAME}")
    print(f"  Point count: {info.points_count:,}")
    print(f"  Vectors:")
    print(f"    • Dense ({DENSE_VECTOR_NAME}): {DENSE_VECTOR_SIZE}D")
    print(f"    • Sparse ({SPARSE_VECTOR_NAME}): Active")
    
    # Test search
    print("\n  → Running test search...")
    
    dense_model = TextEmbedding(model_name=DENSE_MODEL_NAME)
    sparse_model = SparseTextEmbedding(model_name=SPARSE_MODEL_NAME)
    
    test_query = "Can a landlord evict a tenant?"
    
    # Generate test embeddings
    dense_query = list(dense_model.embed([test_query]))[0].tolist()
    sparse_query_embedding = list(sparse_model.embed([test_query]))[0]
    sparse_query = models.SparseVector(
        indices=sparse_query_embedding.indices.tolist(),
        values=sparse_query_embedding.values.tolist()
    )
    
    # Hybrid search
    results = client.query_points(
        collection_name=COLLECTION_NAME,
        prefetch=[
            models.Prefetch(query=dense_query, using=DENSE_VECTOR_NAME, limit=10),
            models.Prefetch(query=sparse_query, using=SPARSE_VECTOR_NAME, limit=10),
        ],
        query=models.FusionQuery(fusion=models.Fusion.RRF),
        limit=3,
    )
    
    print(f"  → Retrieved {len(results.points)} results")
    
    if results.points:
        print("\n  Top result:")
        top = results.points[0]
        print(f"    Citation: {top.payload.get('citation', 'Unknown')}")
        print(f"    Score: {top.score:.3f}")
        print(f"    Text: {top.payload.get('text', '')[:100]}...")
    
    print("\n✓ Collection verified and ready!\n")


def print_summary(statutes_count):
    """Print completion summary."""
    print("="*80)
    print("INGESTION COMPLETE!")
    print("="*80)
    print(f"""
✅ Successfully ingested {statutes_count:,} California housing statutes

Collection Details:
  • Name: {COLLECTION_NAME}
  • Dense vectors: {DENSE_MODEL_NAME}
  • Sparse vectors: {SPARSE_MODEL_NAME}
  • Hybrid search: RRF fusion enabled

Next Steps:
  1. Run vanilla RAG demo:
     python demo_vanilla_rag.py
  
  2. Run hybrid search demo:
     python demo_qdrant_hybrid_search.py
  
  3. Run agentic RAG demo:
     python demo_crewai_qdrant_agent.py

Ready for demos! 🚀
""")


def main():
    """Main ingestion workflow."""
    parser = argparse.ArgumentParser(description='Ingest California housing statutes for demos')
    parser.add_argument('--limit', type=int, help='Limit number of statutes (for testing)')
    parser.add_argument('--recreate', action='store_true', help='Delete and recreate collection')
    args = parser.parse_args()
    
    # Header
    print_header()
    
    # Validate environment
    check_environment()
    
    # Initialize clients
    print("Initializing...")
    client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
    print("✓ Connected to Qdrant Cloud")
    
    dense_model = TextEmbedding(model_name=DENSE_MODEL_NAME)
    print(f"✓ Loaded dense model: {DENSE_MODEL_NAME}")
    
    sparse_model = SparseTextEmbedding(model_name=SPARSE_MODEL_NAME)
    print(f"✓ Loaded sparse model: {SPARSE_MODEL_NAME}\n")
    
    try:
        # Load data
        statutes = load_california_statutes(limit=args.limit)
        
        # Create/check collection
        create_or_check_collection(client, recreate=args.recreate)
        
        # Embed and upload
        embed_and_upload(client, statutes, dense_model, sparse_model)
        
        # Verify
        verify_collection(client)
        
        # Summary
        print_summary(len(statutes))
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Ingestion interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error during ingestion: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

