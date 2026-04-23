# Memory Usage Investigation: 460M Points, 16-byte Vectors, 20GB per Instance

## Your Calculation vs Reality

Your baseline estimate is roughly correct for raw vector data. 460 million points at 16 bytes each is approximately 7.36 GB of raw vector storage. The gap to 20 GB is real and explainable. Here is what Qdrant is storing beyond the raw vectors.

---

## What Is Actually Consuming Those Extra ~12-13 GB

### 1. The HNSW Graph (Likely the Largest Contributor)

The HNSW graph is always kept in RAM by default. It is never swapped out unless you explicitly set `hnsw_config.on_disk=True`. For 460 million points, this is substantial.

The graph stores edges between nodes. With default `m=16`, each point maintains up to 32 edges at the base layer and 16 at upper layers. Each edge is a 4-byte integer. Rough estimate: 460M * 32 * 4 bytes = approximately 59 GB at the extreme, though effective usage depends on how many points are actually indexed and the actual graph structure. Even at a conservative estimate, the HNSW graph alone can add several gigabytes on top of your vector calculation.

Check whether `hnsw_config.on_disk` is set in your collection config:

```python
info = client.get_collection("your_collection")
print(info.config.hnsw_config)
```

If it is not set to `on_disk=True`, the entire graph is resident in RAM across all six instances.

### 2. The ID Tracker (Always in RAM, No Exception)

The ID tracker maintains a bidirectional mapping between your external point IDs and Qdrant's internal IDs. This structure is always held in RAM. There is no configuration to move it to disk. For 460 million points, this mapping alone consumes a meaningful amount of memory that your raw vector calculation does not account for.

### 3. Payload Data

If `on_disk_payload` is not set to `True` in your collection configuration, every payload document for all 460 million points is loaded into RAM. Even small payloads add up: 460M points with an average payload of just 20 bytes is 9.2 GB before accounting for storage overhead.

Check your payload configuration:

```python
info = client.get_collection("your_collection")
print(info.config.params.on_disk_payload)
```

If this returns `False` or `None`, payloads are in RAM.

### 4. Payload Indexes

Each payload field you have indexed (keyword, integer, float, geo, full-text) maintains an in-memory index structure. This is separate from the payload data itself.

Full-text indexes are a particularly common hidden cause of high memory. A full-text index across 460 million documents can consume gigabytes of RAM, well beyond what most teams expect when they add a text search field.

To see what indexes exist:

```python
info = client.get_collection("your_collection")
print(info.payload_schema)
```

If you have full-text indexes on any fields, that is a serious candidate for your unexplained memory.

### 5. Segment Metadata and Optimization Overhead

The standard memory formula applies a 1.5x multiplier over raw vector size to account for segment metadata, temporary optimization segments, and structural overhead. Even with vectors on disk via mmap, this overhead is partially resident in RAM.

### 6. OS Page Cache (May or May Not Apply Here)

Tools like `htop`, `top`, `docker stats`, and most infrastructure monitoring systems report data memory plus OS page cache as a single combined number. Qdrant stores vectors on disk via memory mapping and intentionally allows the OS to cache frequently accessed pages.

A node can show 95% memory usage while Qdrant's actual data footprint is only 17%. The rest is cache, which is evicted under pressure and does not cause crashes.

However, you noted that queries have been minimal for a week. With low query activity, the OS cache would have limited opportunity to warm up. If your 20 GB is primarily cache, you would expect it to be lower under low-query conditions, not stable at 20 GB. This suggests the bulk of your usage is actual data memory, not cache.

To confirm, check the Qdrant metrics endpoint directly rather than relying on OS-level monitoring:

```
GET http://<your-qdrant-host>:6333/metrics
```

Look for `qdrant_collections_total_ram_bytes` and related metrics. The Qdrant web dashboard also separates data from cache in the cluster view. This single check will tell you whether the 20 GB is real data or OS cache.

---

## The Most Likely Culprits Given Your Situation

Given that ingestion has stopped, queries are minimal, and usage is still stable at 20 GB across all six instances, the explanation is almost certainly a combination of:

1. **HNSW graph in RAM**: The graph for 460M points is large. If `hnsw_config.on_disk` is not set, this is resident memory that will not shrink regardless of query or ingestion activity.

2. **Payloads in RAM**: If `on_disk_payload` is `False`, all payload documents for 460M points are loaded and held.

3. **Payload indexes or full-text indexes**: These are in RAM by design and do not evict.

The stability of the 20 GB figure across a quiet week strongly points to data memory rather than cache. Cache would fluctuate more in a low-traffic scenario.

---

## Recommended Next Steps (No Restarts, No Config Changes Yet)

First, gather the actual configuration before touching anything:

```python
info = client.get_collection("your_collection")

# Check vector storage and quantization
print("Vector config:", info.config.params.vectors)
print("Quantization:", info.config.quantization_config)
print("On-disk payload:", info.config.params.on_disk_payload)

# Check HNSW config
print("HNSW config:", info.config.hnsw_config)

# Check payload indexes
print("Payload schema:", info.payload_schema)
```

Then check the metrics endpoint to separate data from cache. Once you have those two pieces of information, the actual source of the 20 GB will be clear.

Do not apply configuration changes (moving to `on_disk_payload`, enabling quantization, setting `hnsw_config.on_disk`) before understanding the current state. Changing storage configuration on a live collection of this size has operational implications and should only happen once you know exactly what you are targeting.

---

## Summary Table: RAM Components for Your Scale

| Component | In RAM by default | Configurable to disk |
|---|---|---|
| Raw vectors (mmap) | Via OS cache only | Yes, already on disk |
| HNSW graph | Yes, always | Yes, `hnsw_config.on_disk=True` |
| ID tracker | Yes, always | No |
| Payload data | Yes | Yes, `on_disk_payload=True` |
| Payload indexes | Yes | No |
| Full-text indexes | Yes | No |
| Collection overhead | ~12-14 MB per collection | No |

Your 20 GB is almost certainly a combination of HNSW graph, ID tracker, and payload data (if payloads are non-trivial and `on_disk_payload` is not set). The metrics endpoint will confirm which ones dominate.
