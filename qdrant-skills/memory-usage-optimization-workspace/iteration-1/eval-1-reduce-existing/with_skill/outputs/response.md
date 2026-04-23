# Reducing Memory Usage on an Existing 5M-Vector Collection

## Situation Analysis

With 5 million vectors consuming 20 GB of RAM, this is close to the expected baseline. Using the Qdrant estimation formula:

```
memory_size = number_of_vectors * vector_dimension * 4 bytes * 1.5
```

For example, 5M vectors at 768 dimensions:

```
5,000,000 * 768 * 4 * 1.5 = ~21.6 GB
```

This confirms you are storing vectors as float32 (the default), fully in RAM. The good news: you do not need to recreate the collection or touch your data. All of the techniques below can be applied to a live, running collection.

---

## Strategy 1: Add Scalar Quantization (Recommended First Step)

This is the most impactful single change you can make to an existing collection. Qdrant applies quantization in the background with no downtime.

**Effect:** 4x RAM reduction. For your 20 GB collection, expect to land around 5 GB after the background optimizer finishes compressing all segments.

**Precision loss:** Under 1% on standard benchmarks.

```python
from qdrant_client import QdrantClient, models

client = QdrantClient(url="http://localhost:6333")

client.update_collection(
    collection_name="my_collection",
    quantization_config=models.ScalarQuantization(
        scalar=models.ScalarQuantizationConfig(
            type=models.ScalarType.INT8,
            quantile=0.99,        # clips top/bottom 0.5% as outliers
            always_ram=True,      # keeps compressed vectors in RAM for fast search
        ),
    ),
)
```

After this update, Qdrant will re-quantize all segments in the background. The collection remains searchable throughout. To track progress:

```python
info = client.get_collection("my_collection")
print(info.status)  # "green" when all segments are optimized
```

When searching, enable rescoring to recover accuracy using the original vectors (which Qdrant keeps on disk automatically once you enable on-disk storage in the next step):

```python
client.query_points(
    collection_name="my_collection",
    query=[0.2, 0.1, 0.9, 0.7],
    search_params=models.SearchParams(
        quantization=models.QuantizationSearchParams(
            rescore=True,
            oversampling=2.0,   # fetch 2x candidates before rescoring
        )
    ),
    limit=10,
)
```

---

## Strategy 2: Move Vectors to Disk (Memmap)

This moves vector data from RAM into memory-mapped files. The OS page cache keeps recently accessed vectors warm, while cold data stays on disk. For collections with non-uniform access patterns (not every vector is queried equally often), this can reduce working-set RAM dramatically.

**Requirement:** Local SSD with 50k+ IOPS. Network-attached storage (NFS, EBS with default settings) typically provides only 6k-10k IOPS and will cause search timeouts.

You can update an existing collection to use memmap by adjusting the `memmap_threshold` in the optimizer config. The threshold tells Qdrant: once a segment exceeds this many vectors, convert it to a memmap file. Setting it to 0 forces all segments to disk immediately:

```python
client.update_collection(
    collection_name="my_collection",
    optimizers_config=models.OptimizersConfigDiff(
        memmap_threshold=20000,   # segments above 20k vectors move to disk
    ),
)
```

The optimizer will then rebuild segments as mmap-backed files in the background. Combined with scalar quantization (int8 `always_ram=True`), the compressed int8 vectors stay in RAM while the raw float32 vectors live on disk for rescoring only.

---

## Strategy 3: Move the HNSW Graph to Disk

The HNSW index itself consumes significant RAM (roughly 10-20% of total vector memory depending on `m` parameter). For a 20 GB collection, the graph alone may occupy 2-4 GB. You can push it to disk:

```python
client.update_collection(
    collection_name="my_collection",
    hnsw_config=models.HnswConfigDiff(
        on_disk=True,
    ),
)
```

This reduces RAM further at the cost of increased disk I/O per search. Best used in combination with Strategy 1 and 2 when you need maximum RAM reduction.

---

## Strategy 4: Move Payload to Disk

If your collection stores large payloads (text, metadata, URLs, etc.), this can reclaim additional RAM. Create payload indexes for any fields you use in filters before enabling this, since indexes stay in RAM regardless:

```python
# First: ensure you have indexes on filtered fields
client.create_payload_index(
    collection_name="my_collection",
    field_name="category",
    field_schema=models.KeywordIndexParams(type="keyword"),
)

# Then: move payload storage to disk
# NOTE: on_disk_payload cannot be toggled on an existing collection via update_collection.
# To apply this to an existing collection without recreation, you can:
# 1. Use the Qdrant REST API to update collection parameters if your version supports it
# 2. Plan this for the next collection rebuild (payload is typically a smaller fraction of RAM)
```

For most collections, payload RAM usage is secondary to vector RAM. Prioritize Strategies 1-3 first.

---

## Recommended Approach: Combined Configuration

Apply quantization first (immediate, no downtime), then lower the memmap threshold to gradually move vectors to disk:

```python
# Step 1: Enable scalar quantization on the existing collection
client.update_collection(
    collection_name="my_collection",
    quantization_config=models.ScalarQuantization(
        scalar=models.ScalarQuantizationConfig(
            type=models.ScalarType.INT8,
            quantile=0.99,
            always_ram=True,
        ),
    ),
)

# Step 2: Configure the optimizer to move large segments to disk
client.update_collection(
    collection_name="my_collection",
    optimizers_config=models.OptimizersConfigDiff(
        memmap_threshold=20000,
    ),
    hnsw_config=models.HnswConfigDiff(
        on_disk=True,
    ),
)
```

Wait for the optimizer to finish (check `collection.status == "green"`), then search with rescoring:

```python
results = client.query_points(
    collection_name="my_collection",
    query=your_query_vector,
    search_params=models.SearchParams(
        quantization=models.QuantizationSearchParams(
            rescore=True,
            oversampling=2.0,
        )
    ),
    limit=10,
)
```

---

## Expected RAM After Each Step

Assuming 5M vectors at 768 dimensions as the baseline example (your 20 GB):

| Configuration | Estimated RAM |
|---|---|
| float32, everything in RAM (current) | ~20 GB |
| After scalar int8 quantization, `always_ram=True` | ~5 GB |
| After quantization + vectors on disk (mmap) | ~1-2 GB working set |
| After quantization + vectors on disk + HNSW on disk | ~0.5-1 GB working set |

The "working set" for mmap configurations depends on your query patterns. The OS will cache frequently accessed pages, so actual observed RAM may be higher than the minimum.

---

## What to Avoid

**Measuring RAM with `htop` or `ps`:** RSS figures include OS page cache from mmap files, which is evictable memory that does not represent your true minimum requirement. Use `docker stats` with a memory limit, or monitor Qdrant's own metrics (`/metrics` endpoint) to see actual non-evictable usage.

**Skipping quantization:** It is the single highest-leverage change available. At 5M vectors, going from float32 to int8 saves roughly 15 GB of non-evictable RAM with a single API call and less than 1% precision loss.

**Using network storage for on-disk vectors:** Only move vectors to disk if your underlying storage can deliver 50k+ IOPS. Network volumes on typical cloud providers fall well short of this and will cause search timeouts.

**On-disk payload without payload indexes on filtered fields:** Every filtered search would scan payloads from disk. Always create indexes on fields you filter on before enabling payload-on-disk.

---

## Summary

You do not need to recreate the collection or export/reimport data. The fastest path to significant memory reduction is a single `update_collection` call to enable scalar int8 quantization with `always_ram=True`. That alone should reduce your 20 GB footprint to approximately 5 GB while the optimizer works in the background. Combining that with `memmap_threshold` configuration and optionally moving the HNSW graph to disk can bring working-set RAM below 1 GB for collections with skewed access patterns.
