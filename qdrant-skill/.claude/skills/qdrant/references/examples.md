# Qdrant Code Examples Reference

This document provides common code patterns and recipes for Qdrant.

## Basic Workflow

### Complete Example: Semantic Search

```python
import os
from qdrant_client import QdrantClient, models

# 1. Connect to Qdrant
client = QdrantClient(
    url=os.environ.get("QDRANT_URL", "localhost"),
    port=6333,
    api_key=os.environ.get("QDRANT_API_KEY"),  # None for local
)

# 2. Create collection
client.recreate_collection(
    collection_name="documents",
    vectors_config=models.VectorParams(
        size=384,
        distance=models.Distance.COSINE,
    ),
)

# 3. Insert vectors
# Assume you have an embedding function
def get_embedding(text: str) -> list[float]:
    # Use your embedding model here
    pass

documents = [
    {"id": 1, "text": "Python is a programming language", "category": "tech"},
    {"id": 2, "text": "Machine learning uses algorithms", "category": "ai"},
    {"id": 3, "text": "Vectors represent semantic meaning", "category": "ai"},
]

client.upsert(
    collection_name="documents",
    points=[
        models.PointStruct(
            id=doc["id"],
            vector=get_embedding(doc["text"]),
            payload={"text": doc["text"], "category": doc["category"]},
        )
        for doc in documents
    ],
)

# 4. Search
query = "What is machine learning?"
results = client.search(
    collection_name="documents",
    query_vector=get_embedding(query),
    limit=3,
)

for result in results:
    print(f"Score: {result.score:.4f} - {result.payload['text']}")
```

## Connection Patterns

### Local Development

```python
# In-memory (for testing)
client = QdrantClient(":memory:")

# Local Docker instance
client = QdrantClient("localhost", port=6333)

# Local with persistence
client = QdrantClient(path="./qdrant_data")
```

### Production (Qdrant Cloud)

```python
import os

client = QdrantClient(
    url=os.environ["QDRANT_URL"],
    api_key=os.environ["QDRANT_API_KEY"],
)
```

### With Retry Logic

```python
from tenacity import retry, stop_after_attempt, wait_exponential
from qdrant_client import QdrantClient
from qdrant_client.http.exceptions import ResponseHandlingException

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=lambda e: isinstance(e, (ConnectionError, ResponseHandlingException)),
)
def create_client():
    return QdrantClient(
        url=os.environ["QDRANT_URL"],
        api_key=os.environ["QDRANT_API_KEY"],
        timeout=30,
    )

client = create_client()
```

## Batch Operations

### Efficient Batch Upsert

```python
from itertools import islice

def chunked(iterable, size):
    """Yield successive chunks from iterable."""
    it = iter(iterable)
    while chunk := list(islice(it, size)):
        yield chunk

# Process in batches of 100
points = [
    models.PointStruct(id=i, vector=get_embedding(text), payload={"text": text})
    for i, text in enumerate(large_text_list)
]

for batch in chunked(points, 100):
    client.upsert(
        collection_name="documents",
        points=batch,
        wait=True,  # Wait for indexing
    )
```

### Parallel Batch Upsert

```python
from concurrent.futures import ThreadPoolExecutor

def upsert_batch(batch):
    client.upsert(collection_name="documents", points=batch, wait=True)

batches = list(chunked(points, 100))

with ThreadPoolExecutor(max_workers=4) as executor:
    executor.map(upsert_batch, batches)
```

## Search Patterns

### Basic Search

```python
results = client.search(
    collection_name="documents",
    query_vector=[0.1, 0.2, ...],
    limit=10,
)
```

### Search with Filter

```python
results = client.search(
    collection_name="documents",
    query_vector=query_embedding,
    query_filter=models.Filter(
        must=[
            models.FieldCondition(
                key="category",
                match=models.MatchValue(value="tech"),
            ),
            models.FieldCondition(
                key="price",
                range=models.Range(gte=10, lte=100),
            ),
        ]
    ),
    limit=10,
)
```

### Search with Score Threshold

```python
results = client.search(
    collection_name="documents",
    query_vector=query_embedding,
    score_threshold=0.7,  # Only return results above this score
    limit=10,
)
```

### Search Specific Payload Fields

```python
results = client.search(
    collection_name="documents",
    query_vector=query_embedding,
    with_payload=["title", "summary"],  # Only return these fields
    with_vectors=False,  # Don't return vectors
    limit=10,
)
```

### Search with Named Vectors

```python
# Search using specific vector
results = client.search(
    collection_name="multimodal",
    query_vector=("text", text_embedding),  # (vector_name, vector)
    limit=10,
)
```

## Hybrid Search

### Dense + Sparse Fusion

```python
from qdrant_client.models import Prefetch, Query, Fusion, FusionQuery, SparseVector

# Assume you have both dense and sparse vectors
dense_query = get_dense_embedding(query)
sparse_query = get_sparse_embedding(query)  # Returns SparseVector

results = client.query_points(
    collection_name="hybrid_collection",
    prefetch=[
        # Dense search
        Prefetch(
            query=dense_query,
            using="dense",  # Named vector
            limit=100,
        ),
        # Sparse search
        Prefetch(
            query=sparse_query,
            using="sparse",  # Named sparse vector
            limit=100,
        ),
    ],
    query=FusionQuery(fusion=Fusion.RRF),
    limit=10,
)
```

### Re-ranking with Cross-Encoder

```python
# First stage: vector search
candidates = client.search(
    collection_name="documents",
    query_vector=query_embedding,
    limit=100,  # Over-fetch for re-ranking
)

# Second stage: re-rank with cross-encoder
from sentence_transformers import CrossEncoder

reranker = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")

pairs = [(query, hit.payload["text"]) for hit in candidates]
scores = reranker.predict(pairs)

# Sort by re-ranker score
reranked = sorted(zip(candidates, scores), key=lambda x: x[1], reverse=True)
top_results = [hit for hit, score in reranked[:10]]
```

## RAG (Retrieval Augmented Generation)

### Basic RAG Pattern

```python
def rag_query(question: str, client: QdrantClient, llm_client) -> str:
    # 1. Embed the question
    question_embedding = get_embedding(question)
    
    # 2. Retrieve relevant documents
    results = client.search(
        collection_name="knowledge_base",
        query_vector=question_embedding,
        limit=5,
    )
    
    # 3. Build context
    context = "\n\n".join([
        f"Document {i+1}:\n{hit.payload['text']}"
        for i, hit in enumerate(results)
    ])
    
    # 4. Generate answer
    prompt = f"""Based on the following documents, answer the question.

Documents:
{context}

Question: {question}

Answer:"""
    
    response = llm_client.complete(prompt)
    return response

# Usage
answer = rag_query("What is vector search?", client, llm)
```

### RAG with Metadata Filtering

```python
def filtered_rag(question: str, user_id: str, client: QdrantClient) -> str:
    results = client.search(
        collection_name="documents",
        query_vector=get_embedding(question),
        query_filter=models.Filter(
            must=[
                # Only search user's documents
                models.FieldCondition(
                    key="user_id",
                    match=models.MatchValue(value=user_id),
                ),
                # Only recent documents
                models.FieldCondition(
                    key="created_at",
                    range=models.DatetimeRange(
                        gte="2024-01-01T00:00:00Z",
                    ),
                ),
            ]
        ),
        limit=5,
    )
    # ... continue with LLM
```

## Multi-tenancy

### Payload-based Tenant Isolation

```python
class TenantQdrant:
    def __init__(self, client: QdrantClient, collection: str):
        self.client = client
        self.collection = collection
    
    def upsert(self, tenant_id: str, points: list):
        # Add tenant_id to all points
        for point in points:
            point.payload["_tenant_id"] = tenant_id
        
        self.client.upsert(
            collection_name=self.collection,
            points=points,
        )
    
    def search(self, tenant_id: str, query_vector: list, limit: int = 10):
        return self.client.search(
            collection_name=self.collection,
            query_vector=query_vector,
            query_filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="_tenant_id",
                        match=models.MatchValue(value=tenant_id),
                    )
                ]
            ),
            limit=limit,
        )

# Usage
tenant_client = TenantQdrant(client, "shared_collection")
tenant_client.upsert("tenant_a", points)
results = tenant_client.search("tenant_a", query_vector)
```

## Recommendations

### Item-to-Item Recommendations

```python
def get_similar_items(item_id: int, limit: int = 10):
    # Get the item's vector
    item = client.retrieve(
        collection_name="products",
        ids=[item_id],
        with_vectors=True,
    )[0]
    
    # Find similar items (excluding itself)
    results = client.search(
        collection_name="products",
        query_vector=item.vector,
        query_filter=models.Filter(
            must_not=[
                models.HasIdCondition(has_id=[item_id])
            ]
        ),
        limit=limit,
    )
    
    return results
```

### User-based Recommendations

```python
def get_user_recommendations(user_id: str, limit: int = 10):
    # Get user's interaction history
    user_items = get_user_history(user_id)
    
    # Get vectors for interacted items
    item_vectors = client.retrieve(
        collection_name="products",
        ids=user_items,
        with_vectors=True,
    )
    
    # Average the vectors to create user profile
    import numpy as np
    user_vector = np.mean([item.vector for item in item_vectors], axis=0).tolist()
    
    # Find similar items not yet interacted with
    results = client.search(
        collection_name="products",
        query_vector=user_vector,
        query_filter=models.Filter(
            must_not=[
                models.HasIdCondition(has_id=user_items)
            ]
        ),
        limit=limit,
    )
    
    return results
```

## Data Management

### Update Payload

```python
# Update single point's payload
client.set_payload(
    collection_name="documents",
    payload={"status": "processed", "processed_at": "2024-01-15T10:00:00Z"},
    points=[1, 2, 3],  # Point IDs
)

# Overwrite entire payload
client.overwrite_payload(
    collection_name="documents",
    payload={"new_field": "value"},
    points=[1],
)

# Delete payload keys
client.delete_payload(
    collection_name="documents",
    keys=["old_field"],
    points=[1, 2, 3],
)
```

### Delete Points

```python
# Delete by IDs
client.delete(
    collection_name="documents",
    points_selector=models.PointIdsList(points=[1, 2, 3]),
)

# Delete by filter
client.delete(
    collection_name="documents",
    points_selector=models.FilterSelector(
        filter=models.Filter(
            must=[
                models.FieldCondition(
                    key="status",
                    match=models.MatchValue(value="deleted"),
                )
            ]
        )
    ),
)
```

### Scroll Through All Points

```python
def iterate_all_points(collection_name: str, batch_size: int = 100):
    """Iterate through all points in a collection."""
    offset = None
    
    while True:
        results, offset = client.scroll(
            collection_name=collection_name,
            limit=batch_size,
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )
        
        for point in results:
            yield point
        
        if offset is None:
            break

# Usage
for point in iterate_all_points("documents"):
    print(point.id, point.payload)
```

## Monitoring

### Collection Info

```python
info = client.get_collection("documents")
print(f"Points: {info.points_count}")
print(f"Vectors: {info.vectors_count}")
print(f"Indexed: {info.indexed_vectors_count}")
print(f"Status: {info.status}")
```

### Check Index Status

```python
def wait_for_index(collection_name: str, timeout: int = 300):
    """Wait for HNSW index to be built."""
    import time
    
    start = time.time()
    while time.time() - start < timeout:
        info = client.get_collection(collection_name)
        if info.status == models.CollectionStatus.GREEN:
            return True
        time.sleep(5)
    
    return False
```

## Error Handling

```python
from qdrant_client.http.exceptions import (
    UnexpectedResponse,
    ResponseHandlingException,
)
from qdrant_client.http.api_client import ApiException

try:
    results = client.search(
        collection_name="documents",
        query_vector=query_embedding,
        limit=10,
    )
except UnexpectedResponse as e:
    print(f"API error: {e.status_code} - {e.reason_phrase}")
except ResponseHandlingException as e:
    print(f"Response handling error: {e}")
except ApiException as e:
    print(f"API exception: {e}")
except Exception as e:
    print(f"Unexpected error: {e}")
```
