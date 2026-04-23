# Memory Growth After Ingestion Stopped: Is This a Leak?

**Short answer: Almost certainly not a memory leak.**

What you are observing is expected behavior from Qdrant's internal memory management. The pattern you describe (memory grows after ingestion, stays elevated, drops immediately on restart) is a classic signature of intentional caching and OS-level page cache behavior, not a leak.

---

## What Is Actually Happening

### 1. HNSW Index Build and Caching

When you ingest data, Qdrant builds HNSW (Hierarchical Navigable Small World) graph indexes for your vector collections. These indexes are memory-mapped files (`mmap`) on disk. After ingestion, Qdrant:

- Finalizes and flushes segment indexes to disk
- Keeps those memory-mapped regions resident in RAM for fast search access
- May continue background optimization tasks (segment merging, index rebuilds) after ingestion stops

The "continued growth after ingestion" you see is likely the tail end of index optimization work that runs asynchronously. Qdrant does not block ingestion while optimizing; it queues and processes optimization after the last write.

### 2. Segment Optimizer Running Post-Ingestion

Qdrant's optimizer runs continuously in the background. After you stop ingesting, it may still be:

- Merging small segments into larger ones
- Converting raw vectors into HNSW-indexed segments
- Running vacuuming passes

Each of these operations loads data into memory temporarily, and the resulting optimized segments get cached by the OS. This process can take minutes to hours after ingestion stops, depending on collection size and optimizer configuration.

### 3. OS Page Cache (Not Qdrant's Fault)

Linux (and most OS kernels) aggressively cache memory-mapped file reads in the page cache. When Qdrant accesses its `mmap`-backed index files, the OS keeps those pages in RAM as long as free memory is available. This is:

- Beneficial: subsequent queries are served from RAM, not disk
- Expected: the kernel will evict pages under memory pressure from other processes
- Not a leak: the memory is reclaimed immediately when the process restarts or when the OS needs it

The 80% figure you are seeing is almost certainly RSS (Resident Set Size) as reported by tools like `docker stats` or `htop`. This includes page cache and mmap regions that the OS controls, not just heap allocations that Qdrant controls directly.

### 4. Write-Ahead Log (WAL) Buffering

Qdrant maintains a WAL for durability. After ingestion stops, WAL segments that have been applied but not yet garbage collected may still be held in memory. These are typically flushed and freed on restart or when thresholds are hit.

---

## Why Memory Drops on Restart

When Qdrant restarts:

1. The process exits, releasing all heap memory and mmap handles
2. The OS reclaims page cache entries associated with the old process
3. Qdrant reloads only what it needs immediately (lazy loading of mmap regions)
4. No background optimizer tasks are running yet, so memory stays low until queries or new ingestion trigger re-caching

This is exactly the behavior you would expect from a healthy system, not a leaking one.

---

## How to Confirm This Is Not a Leak

Look for these indicators of a true memory leak (none of which should be present):

| True Leak Signal | Expected Behavior |
|---|---|
| Memory grows with zero queries and zero ingestion, indefinitely | Memory stabilizes after optimizer finishes |
| Memory never drops even under OS pressure | OS evicts page cache when other processes need RAM |
| RSS grows faster than your actual data size | RSS correlates with index size + active caches |
| Heap profiler shows unbounded allocations | Heap stays bounded; mmap accounts for most RSS |

To check: monitor memory over 24-48 hours with zero queries and zero ingestion. If it grows past the plateau you already see, that warrants deeper investigation. If it stays flat, you have confirmed this is caching.

---

## Practical Recommendations

### 1. Check Qdrant Metrics

Use the `/metrics` endpoint (Prometheus format) or `/telemetry` to inspect:

```
# Look for these metrics:
qdrant_collections_total
qdrant_segments_count
# And check optimizer status via:
GET /collections/{collection_name}
```

The optimizer status field will show if background work is still pending. If `status` is `"green"` and optimizer shows `0` pending operations, the index work is done and memory should be stable.

### 2. Tune the Optimizer (If Needed)

If you want to reduce peak memory during optimization, you can adjust optimizer thresholds in your collection config or `config.yaml`:

```yaml
# config.yaml
storage:
  optimizers:
    default_segment_number: 4        # fewer, larger segments = less overhead
    max_segment_size_kb: 200000      # larger threshold before splitting
    memmap_threshold_kb: 50000       # when to use mmap vs in-memory
    indexing_threshold_kb: 20000     # min size before building HNSW index
```

Larger `memmap_threshold_kb` values push more data to mmap (OS-managed) rather than heap (process-managed), which can help RSS readings but does not change actual memory pressure.

### 3. Set `on_disk` Vectors for Large Collections

If your collection is large relative to available RAM, configure vectors to be stored on disk:

```json
PUT /collections/{collection_name}
{
  "vectors": {
    "size": 1536,
    "distance": "Cosine",
    "on_disk": true
  }
}
```

This prevents Qdrant from loading all vectors into RAM eagerly and instead relies on OS mmap demand paging.

### 4. Tune the HNSW Index for Memory

```json
"hnsw_config": {
  "m": 16,
  "ef_construct": 100,
  "on_disk": true
}
```

Setting `on_disk: true` for the HNSW index dramatically reduces RSS at the cost of slightly higher query latency (first access hits disk, subsequent ones hit page cache).

### 5. Understand Your Actual Memory Budget

4GB for a Qdrant instance is workable but tight if you have large collections with in-memory indexes. Calculate your expected memory footprint:

```
Expected RAM = (num_vectors * vector_dim * 4 bytes)     # raw vectors
             + (num_vectors * m * 8 bytes)               # HNSW graph (m=16 approx)
             + overhead (WAL, payloads, OS, Qdrant process)
```

For example, 1 million vectors at 1536 dimensions:
- Vectors: 1M * 1536 * 4 = ~5.9GB (would need `on_disk: true`)
- HNSW graph: 1M * 16 * 8 = ~128MB

If your data mathematically requires more RAM than you have, no amount of tuning fixes it without `on_disk` flags or a larger instance.

---

## Summary

Your situation is consistent with normal Qdrant operation:

1. Ingestion stopped, but the optimizer continued building and merging indexes in the background
2. Completed indexes and their OS page cache entries remain resident in RAM
3. Memory appears "stuck" at 80% because the OS prefers to keep cached data rather than evict it
4. Restart clears everything and Qdrant starts fresh with lazy loading

This is not a memory leak. It is caching working as designed.

**Recommended action:** Check `/collections/{name}` for optimizer status. If optimizer is green and memory is stable (not still growing), no intervention is needed. If you need to reclaim memory without restarting, you can reduce page cache pressure by enabling `on_disk` indexing options on your collections.

If memory continues to grow monotonically after the optimizer completes and there is zero query or ingestion activity, please open a GitHub issue with your Qdrant version, collection configuration, and memory metrics over time.
