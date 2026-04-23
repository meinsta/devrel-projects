# Qdrant Memory Optimization for Multi-Tenant SaaS

## Your Numbers First

With 500 tenants at 100k vectors each at 768 dimensions, here is what you are dealing with:

**Total vectors:** 500 * 100,000 = 50,000,000 vectors
**Naive float32 RAM:** 50,000,000 * 768 * 4 bytes * 1.5 = ~216 GB

That is obviously impractical to hold in RAM. The good news is your access pattern (only ~20 of 500 tenants active at any time) is exactly the pattern Qdrant's on-disk + page cache strategy is designed for. You can get effective memory usage close to what those 20 active tenants need rather than all 500.

**Active tenant footprint (float32 baseline):** 20 * 100,000 * 768 * 4 * 1.5 = ~8.6 GB

With the optimizations below, you can bring active memory well under 2 GB.

---

## Recommended Architecture: Single Collection with Tenant Isolation

For your scale, a single shared collection with a `tenant_id` payload field and a tenant index is the right approach. Qdrant's tenant index uses the payload filter to efficiently restrict searches to one tenant's vectors without scanning the full dataset.

Do NOT create 500 separate collections. The overhead of managing 500 HNSW graphs, 500 optimizer threads, and 500 sets of segment files will destroy your cluster before multitenancy does.

---

## Step 1: Collection Setup (Do This at Creation Time)

Create the collection with everything on disk plus scalar int8 quantization. This is the single most impactful change you can make.

```python
from qdrant_client import QdrantClient, models

client = QdrantClient(url="http://localhost:6333")

client.create_collection(
    collection_name="tenant_vectors",
    vectors_config=models.VectorParams(
        size=768,
        distance=models.Distance.COSINE,
        on_disk=True,          # vectors live on disk, OS page cache handles hot data
        datatype=models.Datatype.FLOAT16,  # 2x savings at collection creation, free win
    ),
    hnsw_config=models.HnswConfigDiff(
        on_disk=True,          # HNSW graph on disk too; inactive tenants' graph evicted naturally
    ),
    quantization_config=models.ScalarQuantization(
        scalar=models.ScalarQuantizationConfig(
            type=models.ScalarType.INT8,
            quantile=0.99,
            always_ram=True,   # quantized vectors stay in RAM for fast candidate selection
        ),
    ),
    on_disk_payload=True,      # payload (metadata) on disk
)
```

**Why float16 + scalar int8 together?** They stack. float16 cuts the stored vector size in half. Scalar int8 quantization creates a separate compressed copy (1 byte/dim) that lives in RAM for search. The original float16 vectors on disk serve as the rescoring source. Combined effect: the RAM-resident quantized index is ~96 MB per 100k vectors at 768d, versus 432 MB for float32 in RAM.

**Note:** `datatype` cannot be changed after collection creation. Get this right upfront.

---

## Step 2: Tenant Index (Critical for Multitenancy Performance)

```python
# Keyword index with is_tenant=True tells Qdrant this field partitions the data
# Qdrant optimizes storage layout around tenant boundaries
client.create_payload_index(
    collection_name="tenant_vectors",
    field_name="tenant_id",
    field_schema=models.KeywordIndexParams(
        type="keyword",
        is_tenant=True,        # enables tenant-aware segment organization
    ),
)
```

The `is_tenant=True` flag is not just a hint. Qdrant uses it to physically group tenant vectors into the same segments where possible. This means when tenant A's data is evicted from page cache, tenant B's data is likely already together in memory. Cold tenant fetches from disk are more localized.

---

## Step 3: Inserting Points

Always include `tenant_id` in the payload for every point:

```python
from qdrant_client.models import PointStruct

# Upload vectors for a specific tenant
client.upsert(
    collection_name="tenant_vectors",
    points=[
        PointStruct(
            id=point_id,
            vector=embedding_vector,
            payload={
                "tenant_id": "tenant_abc",
                "document_id": "doc_123",
                # other metadata...
            },
        )
        for point_id, embedding_vector in tenant_data
    ],
)
```

---

## Step 4: Searching (Always Filter by Tenant)

Every search must include the tenant filter. This restricts HNSW graph traversal to only that tenant's vectors:

```python
results = client.query_points(
    collection_name="tenant_vectors",
    query=query_embedding,
    query_filter=models.Filter(
        must=[
            models.FieldCondition(
                key="tenant_id",
                match=models.MatchValue(value="tenant_abc"),
            )
        ]
    ),
    search_params=models.SearchParams(
        quantization=models.QuantizationSearchParams(
            rescore=True,        # use full-precision disk vectors to rescore top candidates
            oversampling=2.0,    # fetch 2x candidates before rescoring; tune based on recall needs
        )
    ),
    limit=10,
)
```

---

## Memory Budget After Optimization

| Component | Per 100k tenant (768d) | 20 active tenants |
|---|---|---|
| float32 in RAM (no optimization) | 432 MB | 8,640 MB |
| float16 on disk + scalar int8 in RAM | ~96 MB | ~1,920 MB |
| HNSW graph on disk | ~0 MB RAM | ~0 MB RAM |
| Payload on disk | ~0 MB RAM | ~0 MB RAM |
| Tenant payload index (RAM) | ~5-10 MB | shared, ~5-10 MB total |

**Effective RAM for 20 active tenants: roughly 2 GB**, depending on OS page cache pressure and how much rescoring data gets pulled in. The OS handles eviction of the 480 inactive tenants' data automatically.

---

## Bulk Upload Strategy (For Initial Load or Tenant Onboarding)

When onboarding a new tenant with 100k vectors, disable indexing during the upload to avoid continuous HNSW rebuilding:

```python
# Temporarily disable indexing
client.update_collection(
    collection_name="tenant_vectors",
    optimizers_config=models.OptimizersConfigDiff(indexing_threshold=0),
)

# Upload the tenant's 100k vectors in batches
BATCH_SIZE = 1000
for batch in chunked(tenant_points, BATCH_SIZE):
    client.upsert(collection_name="tenant_vectors", points=batch)

# Re-enable indexing; Qdrant builds HNSW in one pass
client.update_collection(
    collection_name="tenant_vectors",
    optimizers_config=models.OptimizersConfigDiff(indexing_threshold=20000),
)
```

For the initial bulk load of all 500 tenants, set `m=0` on the collection too:

```python
# During initial load only
client.update_collection(
    collection_name="tenant_vectors",
    hnsw_config=models.HnswConfigDiff(m=0),
    optimizers_config=models.OptimizersConfigDiff(indexing_threshold=0),
)

# After all data is loaded, restore
client.update_collection(
    collection_name="tenant_vectors",
    hnsw_config=models.HnswConfigDiff(m=16),
    optimizers_config=models.OptimizersConfigDiff(indexing_threshold=20000),
)
```

---

## Disk Requirements

With float16 on disk, your total storage:

50,000,000 vectors * 768 dims * 2 bytes (float16) = ~72 GB for raw vectors

Add ~20-30% for HNSW graph on disk, payloads, and segment overhead. Plan for ~100 GB total disk.

**Disk IOPS requirement:** You need local NVMe SSD with 50k+ IOPS. Cloud network-attached disks (AWS EBS gp2, etc.) typically max at 6k-10k IOPS and will cause search timeouts under concurrent load. Use local NVMe (AWS i3/i4i instances, GCP n2 with local SSD, etc.) or provision extremely high IOPS volumes.

---

## If You Need to Go Further (Optional)

If after scalar int8 quantization your RAM budget is still too tight, consider binary quantization. At 768d with cosine distance embeddings, recall is usually acceptable with oversampling:

```python
client.create_collection(
    collection_name="tenant_vectors",
    vectors_config=models.VectorParams(
        size=768,
        distance=models.Distance.COSINE,
        on_disk=True,
    ),
    quantization_config=models.BinaryQuantization(
        binary=models.BinaryQuantizationConfig(
            always_ram=True,
        ),
    ),
    on_disk_payload=True,
)
```

Search with higher oversampling to compensate for binary precision loss:

```python
results = client.query_points(
    collection_name="tenant_vectors",
    query=query_embedding,
    query_filter=models.Filter(
        must=[models.FieldCondition(key="tenant_id", match=models.MatchValue(value="tenant_abc"))]
    ),
    search_params=models.SearchParams(
        quantization=models.QuantizationSearchParams(
            rescore=True,
            oversampling=4.0,  # higher oversampling needed for binary vs scalar
        )
    ),
    limit=10,
)
```

Binary quantization drops RAM to ~12 MB per 100k tenant at 768d (vs ~96 MB for scalar int8). Measure recall on your actual embeddings before committing.

---

## Pitfalls to Avoid

**Do not create one collection per tenant.** 500 collections means 500 separate HNSW optimizers, 500 separate WAL files, and 500 sets of threads competing for resources. Qdrant is not designed for this scale of collection count. Use one collection with tenant filtering.

**Do not use `on_disk_payload=True` without creating a payload index on `tenant_id`.** Without the index, every tenant-filtered search will scan raw payload files from disk for every candidate vector. The payload index keeps the filterable keys in RAM.

**Do not measure RAM with `htop` or `free`.** RSS includes OS page cache for mmap files, which the OS will evict under pressure. Use Docker memory limits or cgroup accounting to measure actual committed memory.

**Do not put Qdrant on network-attached storage for vector data.** Network disks at 6k-10k IOPS will cause timeouts when even one active tenant triggers a large HNSW traversal from cold disk. Local NVMe is non-negotiable for on-disk vector search.

---

## Summary

The three things that matter most for your workload, in order of impact:

1. **`on_disk=True` on vectors + `hnsw_config on_disk=True`** -- moves inactive tenant data out of RAM entirely, relying on OS page cache to keep the 20 active tenants warm.
2. **Scalar int8 quantization with `always_ram=True`** -- keeps compressed indexes in RAM for fast candidate selection; full-precision rescoring uses disk I/O only for the final top-k.
3. **`is_tenant=True` on the tenant_id payload index** -- enables Qdrant to physically co-locate tenant vectors in segments, making page cache eviction and warming more efficient.

Combined, these bring your effective RAM footprint from ~8.6 GB (for 20 active tenants, float32) down to roughly 2 GB, while keeping the 480 inactive tenants at near-zero RAM cost.
