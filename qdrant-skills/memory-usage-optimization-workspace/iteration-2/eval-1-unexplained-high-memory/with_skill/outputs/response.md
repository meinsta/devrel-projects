# Diagnosing 20GB Memory Usage: 460M Points with 16-Byte Vectors

## Your calculation vs. reality

Your math of 7-8 GB is for the raw vector data only:

```
460,000,000 points * 16 bytes/vector = 7.36 GB
```

That accounts for the vector payload bytes and nothing else. Qdrant stores considerably more than raw vector bytes. The 20 GB figure is not surprising once you account for everything described below.

---

## What Qdrant is storing that takes 20 GB

### 1. HNSW graph structure (the largest hidden cost)

The HNSW index is a navigable graph where each vector has edges connecting it to its approximate nearest neighbors. This graph is held in RAM regardless of whether vectors themselves are on disk.

Each point in the HNSW graph stores:
- A list of neighbor IDs for each layer
- Level assignments
- The entry point for search traversal

A rough lower bound: each edge is a 4-byte integer (point ID). With a default `m=16` (16 bidirectional links per node at base layer) and approximately 1.33x overhead for upper layers:

```
460,000,000 points * 16 links * 2 directions * 4 bytes = ~58 GB worst case
```

In practice HNSW memory is lower because upper layers are sparse, but for 460M points this structure alone can easily consume 6-12 GB of RAM depending on your `m` parameter and how many segments exist.

The HNSW graph is always in RAM. It is not mmap'd. It must be in RAM to do graph traversal during search.

**Check your HNSW config:**

```python
info = client.get_collection("my_collection")
print(info.config.hnsw_config)
# Look at m value. Default is 16. Higher m = more RAM, better recall.
```

### 2. ID tracker

Qdrant maintains an in-memory mapping from external point IDs (UUIDs or unsigned integers) to internal sequential IDs and back. For 460M points:

- UUID external IDs: 16 bytes each
- Internal ID mapping: additional 8 bytes per point
- Bitset for deleted points: 1 bit per point (negligible)
- Roaring bitmap structures for efficient filtering: variable but significant

Rough estimate for UUID IDs at 460M points: ~11 GB just for bidirectional ID mapping. If you are using integer IDs instead of UUIDs, this drops to roughly 3-4 GB.

**This is always in RAM.** There is no on-disk option for the ID tracker. It must fit in memory.

### 3. Vector cache via OS page cache (inflating your metrics)

If your vectors are stored via memmap (the default when `on_disk` is not explicitly set), the OS will cache recently accessed mmap pages in the page cache. Tools like `htop`, `top`, and `docker stats` report RSS + shared memory, which includes this cache.

After a week of minimal queries, the cache has not been evicted because there was no memory pressure forcing eviction. The OS holds onto it speculatively.

This is the most common reason the number looks wrong: you are measuring OS-level memory, which includes cache, not just Qdrant's working set.

**To see the actual breakdown**, check the Qdrant metrics endpoint:

```
GET /metrics
```

Look for `qdrant_collections_full_scan_count` and the RAM vs cache split in the Qdrant web dashboard. The dashboard distinguishes data memory (actual working set) from mmap cache.

### 4. Payload storage in RAM

If `on_disk_payload` is not set to `true`, all payload data is stored in RAM. Even small payloads multiply fast at 460M points.

Example: 100 bytes average payload per point:

```
460,000,000 * 100 bytes = 46 GB
```

Even 20 bytes average:

```
460,000,000 * 20 bytes = 9.2 GB
```

**Check your payload config:**

```python
info = client.get_collection("my_collection")
print(info.config.params.on_disk_payload)
# False means payloads are in RAM
```

### 5. Payload indexes

Every payload field you have indexed with `create_payload_index` consumes RAM for the index structure. A keyword index over a high-cardinality field at 460M points can consume multiple gigabytes. A full-text index is typically even larger.

These indexes are built and held in memory for fast filtered search. They are not automatically moved to disk.

### 6. Segment overhead and multiple segments

Qdrant splits a collection into segments. Each segment has:
- Its own HNSW graph (separate allocation)
- Its own ID tracker
- Its own mmap region headers
- Segment metadata

If your collection has not been fully optimized (e.g., the optimizer was running before you stopped ingestion, or you have many small segments), memory overhead multiplies. Six instances each with fragmented segments can easily exceed the theoretical minimum.

You can check segment count:

```python
info = client.get_collection("my_collection")
print(info.segments_count)
```

More segments = more overhead. The optimizer merges segments over time, but if optimization was interrupted or is misconfigured it may not have completed.

### 7. The 1.5x multiplier from the estimation formula

The correct memory estimation formula from Qdrant documentation is:

```
memory_size = number_of_vectors * vector_dimension * bytes_per_dim * 1.5
```

For your case with float32 (4 bytes per dimension) and 16-byte vectors (4 dimensions):

```
460,000,000 * 4 dims * 4 bytes * 1.5 = 11 GB
```

That 1.5x multiplier is specifically for HNSW graph, metadata, and optimization overhead. Your 16-byte vectors mean very low dimensionality (4 dimensions of float32 or 8 dimensions of float16), which makes the payload and ID tracking costs proportionally larger relative to the vector cost.

---

## Summary: where the 20 GB comes from

| Component | Estimated contribution | Notes |
|---|---|---|
| Raw vector data | ~7-8 GB | Your original calculation |
| HNSW graph | 3-8 GB | Depends on `m` parameter and segment count |
| ID tracker | 3-11 GB | UUID vs integer IDs matters significantly |
| Payload data | 0-10+ GB | Depends on payload size and `on_disk_payload` |
| Payload indexes | 0-5 GB | Depends on which fields are indexed |
| OS page cache | Variable | Inflates reported memory; not actual working set |

These ranges overlap and stack. 20 GB is completely plausible for a well-configured Qdrant instance at 460M points.

---

## What to do

### Step 1: Get the actual breakdown

Check whether reported memory is data or cache. Run:

```
GET /metrics
```

Or check the Qdrant dashboard. If the data/working set is actually much lower than 20 GB, the rest is OS page cache and is not a problem. It will be evicted under memory pressure.

### Step 2: Check vector and payload config

```python
info = client.get_collection("my_collection")
print(info.config.params.vectors)        # on_disk field
print(info.config.params.on_disk_payload) # payload in RAM or on disk
print(info.config.hnsw_config)           # m parameter
print(info.config.quantization_config)   # quantization setup
```

### Step 3: Set vectors and payloads explicitly on disk

If `on_disk` is not set (or is `False`) on your vector config:

```python
client.update_collection(
    collection_name="my_collection",
    vectors_config=models.VectorParamsDiff(on_disk=True),
)
```

For payloads, create indexes for fields you filter on first, then move payloads to disk:

```python
# Create indexes BEFORE moving payloads to disk
client.create_payload_index(
    collection_name="my_collection",
    field_name="your_filter_field",
    field_schema=models.KeywordIndexParams(type="keyword"),
)

# Then move payloads to disk
client.update_collection(
    collection_name="my_collection",
    params=models.CollectionParamsDiff(on_disk_payload=True),
)
```

### Step 4: Add quantization if not already configured

For 16-byte vectors (very low dimensionality), scalar quantization may not help much, but it reduces the always-in-RAM footprint if you configure it correctly:

```python
client.update_collection(
    collection_name="my_collection",
    vectors_config=models.VectorParamsDiff(on_disk=True),
    quantization_config=models.ScalarQuantization(
        scalar=models.ScalarQuantizationConfig(
            type=models.ScalarType.INT8,
            always_ram=True,
        ),
    ),
)
```

The correct pattern: quantized vectors in RAM (small, fast for candidate selection), originals on disk (only read during rescoring).

### Step 5: Check ID type

If you are using UUID external IDs and can switch to sequential integer IDs, the ID tracker memory drops by approximately 2-3x. This requires re-indexing but can save several gigabytes at 460M points.

---

## Why stopping ingestion and queries did not change anything

This is expected behavior. The ID tracker and HNSW graph are structural. They do not shrink when queries stop. The OS page cache persists until memory pressure forces eviction. None of the components described above release memory because the system went idle.

Memory would drop after:
- A restart (cache is cleared, structures are reloaded from disk)
- Explicit quantization and `on_disk=True` configuration changes followed by optimizer completion
- Moving payloads to disk and waiting for segments to be re-optimized

The 20 GB is not a leak. It is structural overhead from a dataset at this scale, combined with OS caching behavior.
