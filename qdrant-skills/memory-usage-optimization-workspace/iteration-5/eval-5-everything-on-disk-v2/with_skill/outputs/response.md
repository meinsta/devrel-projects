# Memory Usage Analysis: 2.7B UUID Points Across 6 Instances

## Setup Summary

- Total points: 2.7 billion
- Instances: 6
- Points per instance: ~450-460 million (2.7B / 6)
- Configuration: vectors on disk, payloads on disk, HNSW on disk
- Observed RAM per instance: 20 GB
- Expected RAM per instance (ID tracker only): ~7-8 GB (460M x 16 bytes)
- Gap to explain: ~12-13 GB per instance

---

## Why Memory Is Higher Than Your ID Tracker Calculation

Your calculation is correct for the ID tracker alone. The gap comes from several additional contributors that are always in RAM and cannot be moved to disk.

### 1. ID Tracker: Your Baseline Is Right

460 million UUID points x 16 bytes = ~7.36 GB. This is the floor. But the ID tracker is not the only thing always in RAM.

### 2. Segment Overhead: Often the Largest Hidden Consumer

Each segment maintains its own in-memory structures beyond the ID tracker:

- **Bitset for deleted points**: tracks which point IDs are marked deleted. Size scales with segment point count.
- **Version vectors**: each point has an internal version counter for conflict resolution. Adds overhead proportional to point count.
- **Segment metadata and manifest structures**: each segment carries header and config data.

If your collection has not fully optimized (many small segments rather than a few large ones), this multiplies. With 20+ segments per shard, overhead compounds significantly. Check `segments_count` in your collection info. If it is high, the optimizer may not have finished merging, or `default_segment_number` is too high for your shard size.

### 3. HNSW Graph: Even "On Disk" Has In-RAM Components

Setting `hnsw_config.on_disk=true` moves the graph data to mmap files. However:

- The HNSW entry point and top-level graph layer connections are kept in RAM for fast traversal.
- At 460M points, even a partial in-RAM index structure is not negligible.
- The amount varies by `m` parameter (number of connections per node). Default `m=16` means each node stores 16 connection references. Even if node data is mmap'd, index traversal structures may be resident.

At this scale, the HNSW overhead for the resident portion can be several GB depending on your `m` value and index structure.

### 4. Payload Indexes: Frequently Overlooked

Even with `on_disk_payload=true`, payload indexes are kept in RAM by default unless you set `on_disk=true` per index. This is a separate setting.

Common hidden costs:
- **Keyword index on a UUID field**: if you have indexed any UUID field as a keyword, that is ~8-16 bytes per unique value. At 460M unique UUIDs, this is 3.7-7.4 GB by itself.
- **Any other indexed payload fields**: integer, float, and geo indexes all carry per-point in-RAM structures.

Check your `payload_schema` in `GET /collections/{name}`. Any indexed field is a RAM consumer unless explicitly set to `on_disk=true`.

### 5. OS Page Cache: May Be Inflating Your 20 GB Reading

The 20 GB you are observing via `htop`, `top`, or `docker stats` combines actual data memory with OS page cache. Qdrant memory-maps its on-disk files, and the OS caches recently accessed pages in free RAM. This is expected behavior. A node reading 20 GB from those tools could be 8 GB data and 12 GB cache.

**This is the most important thing to verify before assuming a problem exists.**

To separate data memory from cache, call:

```
GET /telemetry
```

Look at `app.memory_usage` versus the sum of `collections.{name}.memory_usage`. The difference is approximately OS page cache.

If data memory is 8-9 GB and the rest is cache, your system is healthy. Cache at this level means Qdrant is actively reading from disk and the OS is doing its job by caching those pages.

### 6. Collection Baseline Overhead

Each collection carries 12-14 MB of fixed overhead for config, metadata, and internal structures. This is minor at your scale but worth noting.

---

## Accounting for the Full 20 GB Gap

| Component | Estimated RAM |
|---|---|
| ID tracker (460M x 16 bytes) | ~7.4 GB |
| Segment metadata, bitsets, version vectors | 1-3 GB (depends on segment count) |
| HNSW resident index structures | 1-3 GB (depends on `m` parameter) |
| Payload indexes (if any UUID or high-cardinality fields are indexed) | 0-7 GB |
| OS page cache (if using htop/top to measure) | variable, often large |

With a UUID payload index, you can easily reach 20 GB in actual data memory. Without it, the 20 GB figure almost certainly includes significant OS page cache.

---

## Will Doubling Replication Factor Double Memory?

Not exactly. The answer depends on what your 20 GB is made of.

**If 20 GB is mostly data memory:** RF=2 doubles data memory because each replica maintains its own ID tracker, segment structures, HNSW resident index, and payload indexes. Data memory goes to ~40 GB per node pair.

**If 20 GB is mostly OS page cache:** RF=2 increases data memory but cache behavior depends on access patterns. The relationship is not linear.

**Practically, for planning purposes:** assume RF=2 doubles your data memory requirement. If data memory is 8 GB today, budget 16 GB after adding a replica. Cache on top of that depends on your query volume and access patterns.

**Critical warning for your scale:** when Qdrant replicates large shards, the default `stream_records` method buffers data in memory during transfer. For shards of this size (460M points), you need 1.5-2x data memory headroom during the replication operation itself. Use snapshot-based replication instead of stream_records to avoid OOM during replica setup.

---

## Recommended Next Steps

**Step 1: Get actual data vs cache split before doing anything else.**

```
GET /telemetry
```

This single call will tell you whether you have a real problem or a measurement artifact.

**Step 2: Check for payload indexes on high-cardinality fields.**

```
GET /collections/{name}
```

Look at `payload_schema`. If any UUID or other high-cardinality field is indexed, that is likely your largest unexpected consumer. Set `on_disk=true` on indexes for fields that are not used in frequent filters.

**Step 3: Check segment count.**

If `segments_count` per shard is high (above 20), the optimizer has not finished merging. Wait for optimization to complete before tuning further.

**Step 4: Check HNSW `m` parameter.**

Higher `m` values increase graph connectivity and recall but also increase the resident memory for index traversal structures. If you used a non-default `m`, factor that in.

**Step 5: If replication factor increase is planned:**

- Confirm you are using snapshot-based replication, not stream_records.
- Ensure each node has at least 1.5x current data memory available before starting the operation.
- Do not start replica changes on all shards simultaneously at this scale.

---

## Summary

Your ID tracker calculation is correct. The gap to 20 GB comes from segment overhead (bitsets, version vectors), HNSW resident structures, possible payload indexes on high-cardinality fields, and likely a significant OS page cache component inflating the reading from system tools. Check telemetry first. If data memory is at or near your calculation, the system is behaving correctly. RF=2 will roughly double data memory, and at this scale you must use snapshot-based replication to avoid OOM during the operation.
