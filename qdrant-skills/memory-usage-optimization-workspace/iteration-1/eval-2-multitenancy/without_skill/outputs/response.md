# Memory Optimization for Multi-Tenant Qdrant: 500 Tenants, 20 Active

## Situation Summary

- 500 tenants total, ~20 active at any time
- 100k vectors per tenant at 768 dimensions
- Float32 baseline: 100k * 768 * 4 bytes = ~300 MB per tenant in memory (raw vectors only)
- Naive approach (all tenants in memory): 500 * 300 MB = ~150 GB -- completely impractical

The core insight: you should never load all tenants into memory simultaneously. Qdrant gives you several mechanisms to achieve this.

---

## Strategy 1: One Collection Per Tenant with Quantization

The most straightforward approach for strong per-tenant isolation. Each tenant gets their own collection, and you aggressively quantize vectors to shrink the in-memory footprint.

### Scalar Quantization (int8) -- 4x reduction

```python
from qdrant_client import QdrantClient
from qdrant_client.models import (
    VectorParams,
    Distance,
    ScalarQuantization,
    ScalarQuantizationConfig,
    ScalarType,
    QuantizationSearchParams,
)

client = QdrantClient(url="http://localhost:6333")

def create_tenant_collection(tenant_id: str):
    client.create_collection(
        collection_name=f"tenant_{tenant_id}",
        vectors_config=VectorParams(
            size=768,
            distance=Distance.COSINE,
        ),
        quantization_config=ScalarQuantization(
            scalar=ScalarQuantizationConfig(
                type=ScalarType.INT8,
                quantile=0.99,
                always_ram=True,  # keep quantized index in RAM, full vectors on disk
            )
        ),
    )
```

With `always_ram=True`, only the quantized int8 index lives in RAM. Original float32 vectors are fetched from disk for rescoring only when needed.

Memory per tenant: ~75 MB (down from ~300 MB). Total for 500 tenants if all loaded: ~37.5 GB. But combined with mmap below, most tenants won't be loaded at all.

### Binary Quantization -- 32x reduction (best for high-dimensional vectors at 768d)

```python
from qdrant_client.models import BinaryQuantization, BinaryQuantizationConfig

def create_tenant_collection_binary(tenant_id: str):
    client.create_collection(
        collection_name=f"tenant_{tenant_id}",
        vectors_config=VectorParams(
            size=768,
            distance=Distance.COSINE,
        ),
        quantization_config=BinaryQuantization(
            binary=BinaryQuantizationConfig(
                always_ram=True,
            )
        ),
    )
```

Binary quantization is extremely effective at 768 dimensions. Memory per tenant index: ~12 MB. With oversampling + rescoring, recall stays high (typically 0.95+ for well-distributed embeddings like OpenAI/text-embedding-3).

Search with rescoring to recover accuracy:

```python
results = client.search(
    collection_name=f"tenant_{tenant_id}",
    query_vector=query_vector,
    limit=10,
    search_params=QuantizationSearchParams(
        ignore=False,
        rescore=True,
        oversampling=2.0,  # fetch 2x candidates, rescore with originals
    ),
)
```

---

## Strategy 2: Mmap Storage -- The Key to Inactive Tenant Memory Relief

Mmap (memory-mapped files) lets the OS page vectors in and out of RAM automatically. Inactive tenants consume almost zero RAM; active tenants load pages on demand.

### Configure on-disk payload and vector storage

```python
from qdrant_client.models import OptimizersConfigDiff, HnswConfigDiff

client.create_collection(
    collection_name=f"tenant_{tenant_id}",
    vectors_config=VectorParams(
        size=768,
        distance=Distance.COSINE,
        on_disk=True,  # store full vectors on disk, mmap on access
    ),
    optimizers_config=OptimizersConfigDiff(
        memmap_threshold=10000,  # segments larger than 10k vectors use mmap
    ),
    hnsw_config=HnswConfigDiff(
        on_disk=False,  # keep HNSW graph index in RAM for speed
    ),
)
```

This configuration means:
- Full float32 vectors: on disk, memory-mapped (near-zero RAM for inactive tenants)
- HNSW index graph: in RAM (fast traversal)
- Quantized index (if used): in RAM (`always_ram=True`)

For completely inactive tenants, OS will evict their pages. For active tenants, pages are loaded transparently.

### Use mmap for the HNSW graph too (maximum memory savings)

If you need even more aggressive savings and can tolerate slightly higher latency:

```python
client.create_collection(
    collection_name=f"tenant_{tenant_id}",
    vectors_config=VectorParams(
        size=768,
        distance=Distance.COSINE,
        on_disk=True,
    ),
    hnsw_config=HnswConfigDiff(
        on_disk=True,  # HNSW graph also mmap'd
    ),
    optimizers_config=OptimizersConfigDiff(
        memmap_threshold=5000,
    ),
)
```

---

## Strategy 3: Single Collection with Tenant Filtering (Simpler Ops)

Instead of 500 separate collections, use one collection and tag each vector with a tenant ID. This avoids per-collection overhead and simplifies management.

### Setup

```python
from qdrant_client.models import Filter, FieldCondition, MatchValue

# Create one shared collection with on-disk storage and quantization
client.create_collection(
    collection_name="all_tenants",
    vectors_config=VectorParams(
        size=768,
        distance=Distance.COSINE,
        on_disk=True,
    ),
    quantization_config=BinaryQuantization(
        binary=BinaryQuantizationConfig(always_ram=True)
    ),
    optimizers_config=OptimizersConfigDiff(
        memmap_threshold=10000,
    ),
)

# Create a payload index on tenant_id for efficient filtering
client.create_payload_index(
    collection_name="all_tenants",
    field_name="tenant_id",
    field_schema="keyword",
)
```

### Inserting tenant vectors

```python
from qdrant_client.models import PointStruct
import uuid

def upsert_tenant_vectors(tenant_id: str, vectors: list, payloads: list):
    points = [
        PointStruct(
            id=str(uuid.uuid4()),
            vector=vec,
            payload={"tenant_id": tenant_id, **payload},
        )
        for vec, payload in zip(vectors, payloads)
    ]
    client.upsert(collection_name="all_tenants", points=points)
```

### Searching with tenant isolation

```python
def search_for_tenant(tenant_id: str, query_vector: list, limit: int = 10):
    return client.search(
        collection_name="all_tenants",
        query_vector=query_vector,
        query_filter=Filter(
            must=[
                FieldCondition(
                    key="tenant_id",
                    match=MatchValue(value=tenant_id),
                )
            ]
        ),
        limit=limit,
        search_params=QuantizationSearchParams(
            rescore=True,
            oversampling=2.0,
        ),
    )
```

Trade-off: All tenant data is in one collection, so mmap eviction becomes less targeted. However, you avoid per-collection HNSW graph overhead (each collection carries its own metadata and index structure).

---

## Strategy 4: Collection Aliases for Hot/Cold Tenant Management

Maintain an application-layer concept of hot (active) and cold (inactive) tenants. Configure them differently.

```python
# Hot tenant: HNSW in RAM, quantized index in RAM, full vectors on disk
def configure_hot_tenant(tenant_id: str):
    client.update_collection(
        collection_name=f"tenant_{tenant_id}",
        hnsw_config=HnswConfigDiff(on_disk=False),
        quantization_config=ScalarQuantization(
            scalar=ScalarQuantizationConfig(
                type=ScalarType.INT8,
                always_ram=True,
            )
        ),
    )

# Cold tenant: everything on disk, mmap only
def configure_cold_tenant(tenant_id: str):
    client.update_collection(
        collection_name=f"tenant_{tenant_id}",
        hnsw_config=HnswConfigDiff(on_disk=True),
    )
```

You can schedule a daily job that flips recently-inactive tenants to cold configuration.

---

## Strategy 5: Qdrant Collection Aliases for Blue/Green Tenant Rotation

Use aliases so your application logic doesn't need to change collection names:

```python
# On tenant activation (warming up)
client.update_aliases(
    change_aliases_operations=[
        {
            "create_alias": {
                "collection_name": f"tenant_{tenant_id}",
                "alias_name": f"active_{tenant_id}",
            }
        }
    ]
)

# Query via alias
results = client.search(
    collection_name=f"active_{tenant_id}",
    query_vector=query_vector,
    limit=10,
)
```

---

## Memory Budget Estimation

### With binary quantization + on_disk=True for full vectors + HNSW in RAM

Per tenant (in RAM, when active):
- Binary quantized index: 100k * 768 / 8 bytes = ~9.6 MB
- HNSW graph: roughly 100k * ~64 bytes per node (m=16 default) = ~6.4 MB
- Total per active tenant: ~16 MB

For 20 active tenants: ~320 MB RAM total for indexes.
Inactive tenants: near-zero RAM (OS evicts mmap pages).

### With scalar quantization (int8) + on_disk=True + HNSW in RAM

Per active tenant:
- int8 index: 100k * 768 = ~76.8 MB
- HNSW graph: ~6.4 MB
- Total per active tenant: ~83 MB

For 20 active tenants: ~1.66 GB. Still very manageable.

---

## Recommended Configuration for Your Use Case

Given 500 tenants / 20 active / 100k vectors / 768d, the optimal approach is:

1. **One collection per tenant** (cleaner isolation, simpler access control).
2. **Binary quantization with `always_ram=True`** (32x memory reduction on the searchable index).
3. **`on_disk=True` for full vectors** (mmap, near-zero cost for inactive tenants).
4. **HNSW `on_disk=False`** (keep graph in RAM for active tenants, accept eviction for inactive).
5. **Rescoring enabled** (`oversampling=2.0`, `rescore=True`) to recover recall.

```python
from qdrant_client import QdrantClient
from qdrant_client.models import (
    VectorParams,
    Distance,
    BinaryQuantization,
    BinaryQuantizationConfig,
    HnswConfigDiff,
    OptimizersConfigDiff,
)

client = QdrantClient(url="http://localhost:6333")

def provision_tenant(tenant_id: str):
    """Provision a new tenant collection with optimal memory settings."""
    collection_name = f"tenant_{tenant_id}"

    client.create_collection(
        collection_name=collection_name,
        vectors_config=VectorParams(
            size=768,
            distance=Distance.COSINE,
            on_disk=True,           # full vectors live on disk
        ),
        quantization_config=BinaryQuantization(
            binary=BinaryQuantizationConfig(
                always_ram=True,    # binary index stays in RAM when accessed
            )
        ),
        hnsw_config=HnswConfigDiff(
            on_disk=False,          # HNSW graph in RAM (fast traversal)
            m=16,                   # standard connectivity
            ef_construct=100,       # build quality
        ),
        optimizers_config=OptimizersConfigDiff(
            memmap_threshold=5000,  # use mmap for segments with 5k+ vectors
            indexing_threshold=20000,
        ),
    )

    return collection_name
```

This setup keeps your active-tenant memory footprint around 300-500 MB total for 20 active tenants, rather than hundreds of gigabytes.

---

## Operational Tips

- **Disk IOPS matter.** With on-disk vectors, use NVMe SSDs. Cold-read latency on spinning disks is unacceptable for interactive search.
- **OS page cache is your friend.** Don't restrict OS memory too aggressively. Let the page cache hold recently accessed tenant data.
- **Monitor with Qdrant's telemetry endpoint.** `GET /metrics` exposes memory stats per collection, helping you identify which tenants are consuming RAM unexpectedly.
- **Shard carefully.** With 500 collections, avoid replication unless you truly need HA per tenant. Replication doubles the storage and memory pressure.
- **Segment merging.** Keep `max_segment_size` tuned. Too many small segments degrade mmap performance. The default optimizer settings handle this but verify after heavy ingestion bursts.
