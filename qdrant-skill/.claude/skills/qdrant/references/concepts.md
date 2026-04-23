# Qdrant Core Concepts Reference

This document covers the fundamental concepts and architecture of Qdrant.

## Collections

A **collection** is a named set of points (vectors with payloads) that share the same configuration.

### Collection Configuration

```python
from qdrant_client import models

client.create_collection(
    collection_name="my_collection",
    vectors_config=models.VectorParams(
        size=384,                          # Vector dimensions
        distance=models.Distance.COSINE,   # Distance metric
        on_disk=False,                     # Store vectors in RAM
    ),
    # Optional configurations
    hnsw_config=models.HnswConfigDiff(
        m=16,                # Number of edges per node
        ef_construct=100,    # Index build quality
    ),
    optimizers_config=models.OptimizersConfigDiff(
        indexing_threshold=20000,  # When to build HNSW index
    ),
    quantization_config=models.ScalarQuantization(
        scalar=models.ScalarQuantizationConfig(
            type=models.ScalarType.INT8,
            quantile=0.99,
            always_ram=True,
        ),
    ),
)
```

### Named Vectors

Store multiple vector types per point:

```python
client.create_collection(
    collection_name="multimodal",
    vectors_config={
        "text": models.VectorParams(size=384, distance=models.Distance.COSINE),
        "image": models.VectorParams(size=512, distance=models.Distance.EUCLID),
    },
)
```

### Sparse Vectors

For hybrid search with BM25/SPLADE:

```python
client.create_collection(
    collection_name="hybrid",
    vectors_config=models.VectorParams(size=384, distance=models.Distance.COSINE),
    sparse_vectors_config={
        "text-sparse": models.SparseVectorParams(),
    },
)
```

## Points

A **point** consists of:
- **ID**: Unique identifier (integer or UUID)
- **Vector(s)**: Dense and/or sparse embeddings
- **Payload**: JSON metadata

### Point Structure

```python
models.PointStruct(
    id=1,  # or "550e8400-e29b-41d4-a716-446655440000"
    vector=[0.1, 0.2, 0.3, ...],
    payload={
        "title": "Document Title",
        "category": "tech",
        "price": 99.99,
        "tags": ["ai", "ml"],
        "created_at": "2024-01-15T10:30:00Z",
    }
)
```

### Point with Named Vectors

```python
models.PointStruct(
    id=1,
    vector={
        "text": [0.1, 0.2, ...],
        "image": [0.3, 0.4, ...],
    },
    payload={"title": "Multimodal document"}
)
```

### Point with Sparse Vectors

```python
models.PointStruct(
    id=1,
    vector={
        "dense": [0.1, 0.2, ...],
        "sparse": models.SparseVector(
            indices=[10, 50, 100, 500],
            values=[0.5, 0.3, 0.8, 0.2],
        ),
    },
    payload={"text": "Original text content"}
)
```

## Distance Metrics

| Metric | Formula | Use Case | Range |
|--------|---------|----------|-------|
| **Cosine** | 1 - cos(a,b) | Text embeddings (normalized) | [0, 2] |
| **Euclid** | √Σ(aᵢ-bᵢ)² | Image embeddings | [0, ∞) |
| **Dot** | -Σ(aᵢ×bᵢ) | Pre-normalized vectors | (-∞, ∞) |
| **Manhattan** | Σ\|aᵢ-bᵢ\| | Sparse data, outlier-resistant | [0, ∞) |

### Choosing a Distance Metric

- **Cosine**: Default for most text embedding models (OpenAI, Cohere, etc.)
- **Euclid**: Good for image embeddings, when magnitude matters
- **Dot**: Use when vectors are already normalized and you want max performance
- **Manhattan**: Sparse or high-dimensional data, robust to outliers

## Payloads

Payloads are JSON objects attached to points for filtering and retrieval.

### Supported Types

| Type | Example | Filterable |
|------|---------|------------|
| String | `"category": "tech"` | Yes |
| Integer | `"price": 100` | Yes |
| Float | `"score": 0.95` | Yes |
| Boolean | `"active": true` | Yes |
| Array | `"tags": ["a", "b"]` | Yes |
| Object | `"meta": {"key": "val"}` | Nested fields |
| Geo | `"location": {"lat": 52.5, "lon": 13.4}` | Yes |
| DateTime | `"created": "2024-01-15T10:30:00Z"` | Yes |

### Payload Indexes

Create indexes for faster filtering:

```python
# Keyword index (exact match)
client.create_payload_index(
    collection_name="my_collection",
    field_name="category",
    field_schema=models.PayloadSchemaType.KEYWORD,
)

# Integer index (range queries)
client.create_payload_index(
    collection_name="my_collection",
    field_name="price",
    field_schema=models.PayloadSchemaType.INTEGER,
)

# Full-text index
client.create_payload_index(
    collection_name="my_collection",
    field_name="description",
    field_schema=models.TextIndexParams(
        type=models.TextIndexType.TEXT,
        tokenizer=models.TokenizerType.WORD,
        min_token_len=2,
        max_token_len=15,
        lowercase=True,
    ),
)

# Geo index
client.create_payload_index(
    collection_name="my_collection",
    field_name="location",
    field_schema=models.PayloadSchemaType.GEO,
)
```

## Filtering

Qdrant supports rich filtering on payload fields.

### Filter Conditions

```python
from qdrant_client import models

# Match exact value
models.FieldCondition(key="category", match=models.MatchValue(value="tech"))

# Match any of values
models.FieldCondition(key="category", match=models.MatchAny(any=["tech", "science"]))

# Match except values
models.FieldCondition(key="category", match=models.MatchExcept(except_=["spam"]))

# Range filter
models.FieldCondition(key="price", range=models.Range(gte=10, lte=100))

# Geo radius
models.FieldCondition(
    key="location",
    geo_radius=models.GeoRadius(
        center=models.GeoPoint(lat=52.5, lon=13.4),
        radius=1000,  # meters
    ),
)

# Geo bounding box
models.FieldCondition(
    key="location",
    geo_bounding_box=models.GeoBoundingBox(
        top_left=models.GeoPoint(lat=52.6, lon=13.3),
        bottom_right=models.GeoPoint(lat=52.4, lon=13.5),
    ),
)

# Full-text search
models.FieldCondition(key="description", match=models.MatchText(text="search query"))

# Check field exists
models.IsEmptyCondition(is_empty=models.PayloadField(key="optional_field"))

# Check field is null
models.IsNullCondition(is_null=models.PayloadField(key="nullable_field"))
```

### Combining Filters

```python
# AND logic
models.Filter(
    must=[
        models.FieldCondition(key="category", match=models.MatchValue(value="tech")),
        models.FieldCondition(key="price", range=models.Range(lte=100)),
    ]
)

# OR logic
models.Filter(
    should=[
        models.FieldCondition(key="category", match=models.MatchValue(value="tech")),
        models.FieldCondition(key="category", match=models.MatchValue(value="science")),
    ]
)

# NOT logic
models.Filter(
    must_not=[
        models.FieldCondition(key="status", match=models.MatchValue(value="deleted")),
    ]
)

# Combined
models.Filter(
    must=[
        models.FieldCondition(key="active", match=models.MatchValue(value=True)),
    ],
    should=[
        models.FieldCondition(key="priority", match=models.MatchValue(value="high")),
        models.FieldCondition(key="urgent", match=models.MatchValue(value=True)),
    ],
    must_not=[
        models.FieldCondition(key="archived", match=models.MatchValue(value=True)),
    ],
)
```

## Quantization

Reduce memory usage by compressing vectors.

### Scalar Quantization

Converts float32 to int8 (4x compression):

```python
client.update_collection(
    collection_name="my_collection",
    quantization_config=models.ScalarQuantization(
        scalar=models.ScalarQuantizationConfig(
            type=models.ScalarType.INT8,
            quantile=0.99,        # Calibration quantile
            always_ram=True,      # Keep quantized in RAM
        ),
    ),
)
```

### Binary Quantization

Converts to 1-bit per dimension (32x compression):

```python
client.update_collection(
    collection_name="my_collection",
    quantization_config=models.BinaryQuantization(
        binary=models.BinaryQuantizationConfig(
            always_ram=True,
        ),
    ),
)
```

**Best for**: OpenAI `text-embedding-3-*`, Cohere v3 models

### Product Quantization

Compresses by clustering (configurable compression):

```python
client.update_collection(
    collection_name="my_collection",
    quantization_config=models.ProductQuantization(
        product=models.ProductQuantizationConfig(
            compression=models.CompressionRatio.X16,
            always_ram=True,
        ),
    ),
)
```

### Quantization Comparison

| Type | Compression | Recall | Best For |
|------|-------------|--------|----------|
| Scalar | 4x | 99%+ | General purpose |
| Binary | 32x | 95%+ | OpenAI, Cohere v3 |
| Product | 4-64x | 97%+ | Large scale |

## HNSW Index

Qdrant uses HNSW (Hierarchical Navigable Small World) for approximate nearest neighbor search.

### HNSW Parameters

```python
client.update_collection(
    collection_name="my_collection",
    hnsw_config=models.HnswConfigDiff(
        m=16,               # Edges per node (higher = better recall, more memory)
        ef_construct=100,   # Build-time search width (higher = better index)
        full_scan_threshold=10000,  # Switch to brute force below this
        max_indexing_threads=0,     # 0 = auto
        on_disk=False,      # Store index in RAM
    ),
)
```

### Search Parameters

```python
results = client.search(
    collection_name="my_collection",
    query_vector=[0.1, 0.2, ...],
    search_params=models.SearchParams(
        hnsw_ef=128,        # Search-time search width (higher = better recall)
        exact=False,        # True = brute force
    ),
    limit=10,
)
```

### Tuning Guidelines

| Scenario | m | ef_construct | hnsw_ef |
|----------|---|--------------|---------|
| Speed priority | 8 | 50 | 64 |
| Balanced | 16 | 100 | 128 |
| Recall priority | 32 | 200 | 256 |

## Sharding

Distribute collections across multiple nodes.

### Automatic Sharding

```python
client.create_collection(
    collection_name="large_collection",
    vectors_config=models.VectorParams(size=384, distance=models.Distance.COSINE),
    shard_number=6,          # Number of shards
    replication_factor=2,    # Copies per shard
)
```

### Sharding Guidelines

- **Rule of thumb**: 1 shard per 1M vectors
- **Replication**: 2+ for high availability
- **Distribution**: Shards spread across nodes automatically

## Multi-tenancy

Isolate data for multiple tenants in a single collection.

### Approach 1: Payload-based

```python
# Add tenant_id to every point
client.upsert(
    collection_name="shared",
    points=[
        models.PointStruct(
            id=1,
            vector=[0.1, ...],
            payload={"tenant_id": "tenant_a", "data": "..."},
        ),
    ],
)

# Always filter by tenant
results = client.search(
    collection_name="shared",
    query_vector=[0.1, ...],
    query_filter=models.Filter(
        must=[models.FieldCondition(key="tenant_id", match=models.MatchValue(value="tenant_a"))]
    ),
)
```

### Approach 2: Collection per Tenant

Better isolation but more management overhead:

```python
client.create_collection(collection_name=f"tenant_{tenant_id}", ...)
```

## Hybrid Search

Combine dense and sparse vectors for better retrieval.

### Setup

```python
client.create_collection(
    collection_name="hybrid",
    vectors_config=models.VectorParams(size=384, distance=models.Distance.COSINE),
    sparse_vectors_config={
        "bm25": models.SparseVectorParams(),
    },
)
```

### Query

```python
from qdrant_client.models import Prefetch, Query

results = client.query_points(
    collection_name="hybrid",
    prefetch=[
        Prefetch(query=[0.1, 0.2, ...], using="", limit=100),  # Dense
        Prefetch(
            query=models.SparseVector(indices=[10, 50], values=[0.5, 0.3]),
            using="bm25",
            limit=100,
        ),  # Sparse
    ],
    query=models.FusionQuery(fusion=models.Fusion.RRF),  # Reciprocal Rank Fusion
    limit=10,
)
```

### Fusion Methods

- **RRF (Reciprocal Rank Fusion)**: Default, works well generally
- **DBSFusion**: Distribution-Based Score Fusion, normalizes scores
