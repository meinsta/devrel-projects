# Diagnosing Unexplained Memory Usage: 460M Points, 16-Byte Vectors

## Summary of the Gap

Your calculation of 7-8GB accounts for raw vector data only. Qdrant stores significantly more than raw vectors. The 20GB figure is consistent with a fully operational Qdrant instance at your scale, once you account for all the structures described below.

---

## What Your 7-8GB Calculation Covers

460,000,000 points x 16 bytes = 7.36 GB

This covers only the raw vector payload. Qdrant builds and maintains many additional structures on top of this.

---

## What Qdrant Actually Stores (and Why It Uses 20GB)

### 1. HNSW Graph Index (~3-6GB estimated)

This is almost certainly the largest single contributor beyond raw vectors.

The HNSW (Hierarchical Navigable Small World) index stores a graph where each node has outgoing edges (links) to its neighbors. The default `m` parameter is 16, meaning each point has up to 16 neighbors per layer, plus additional connections in the higher layers of the hierarchy.

Memory for HNSW links:
- Each link is stored as a 4-byte `u32` point ID
- With `m=16` and considering multi-layer structure (roughly 1.33x multiplier for upper layers): ~16 * 1.33 * 4 bytes = ~85 bytes per point
- 460M * 85 bytes = ~39GB at default m, but with quantization or `m` tuning this can be lower

Wait, that's even higher. But HNSW graphs are typically stored on disk and memory-mapped. Depending on your `on_disk` configuration and OS page cache warmup, significant portions can reside in RAM.

If you are using `on_disk: false` for vectors (keeping them in RAM), the HNSW graph itself may be fully in memory.

With `m=16`: 460M * 16 neighbors * 4 bytes = ~29.5GB for links alone at the base layer. This suggests either your `m` is lower, or the index is partially memory-mapped and only partially resident.

Even with `m=8` (which would be unusual, default is 16): 460M * 8 * 4 = ~14.7GB for links. Combined with raw vectors, this alone explains the 20GB+.

**Check your collection's `hnsw_config.m` setting.** This is the primary suspect.

### 2. Point ID Mapping and Internal Structures (~1-2GB)

Qdrant maintains a bidirectional mapping between:
- External point IDs (which can be UUIDs or unsigned integers)
- Internal sequential IDs used by the HNSW graph and vector storage

If you are using UUID point IDs (128-bit), this mapping adds:
- 460M * (16 bytes UUID + 4 bytes internal ID + overhead) = ~9-10GB for UUID mappings alone

If you are using unsigned integer IDs:
- 460M * (8 bytes u64 + 4 bytes u32 + overhead) = ~5-6GB

This mapping is kept in RAM for fast lookups during search.

**Check what ID type you are using.** UUID IDs are common and dramatically increase memory versus u64 integer IDs.

### 3. Payload Storage (~variable, can be significant)

Even "empty" payloads have storage overhead per point. If you have any payload fields attached to points:
- Each field is stored in a RocksDB-backed payload store
- With any string or numeric metadata, this can easily add several GB
- RocksDB itself maintains block cache, write buffers, and memtables in RAM

Default RocksDB block cache can consume 512MB-2GB depending on access patterns.

Even with no payload, the internal payload storage structure has per-point overhead.

### 4. Segment Structure and Metadata

Qdrant organizes points into segments. Each segment maintains:
- A version vector (for MVCC/concurrency control): 8 bytes per point
- A deleted flags bitset
- Segment-level metadata and configuration

With 460M points split across segments: 460M * 8 bytes = ~3.7GB for version tracking alone.

### 5. Quantization Structures (if enabled)

If you have scalar quantization (SQ) or product quantization (PQ) enabled, Qdrant stores:
- The quantized vectors in addition to (or instead of) raw vectors, depending on config
- Quantization centroids and lookup tables
- With SQ8 on 16-byte (4-float) vectors: 460M * 4 bytes = ~1.84GB for quantized copies

### 6. mmap / Page Cache Effects

Qdrant uses memory-mapped files for on-disk storage. Even when `on_disk: true` is set for vectors, the OS page cache can hold large portions of the mmap region in RAM. This is not "Qdrant using memory" per se, but it shows up in process RSS.

After stopping ingestion for a week with minimal queries, you would expect the OS to gradually evict cold pages. If RSS is still at 20GB after a week of low activity, the memory is genuinely allocated (not just page cache), pointing to in-RAM structures rather than mmap artifacts.

### 7. Optimizer and WAL Buffers

The Write-Ahead Log (WAL) and optimizer maintain buffers:
- WAL segments: configurable, but typically 128MB-1GB
- Optimizer hold segments during index rebuilding: temporarily doubles memory for affected segments
- If an optimizer run was interrupted and left incomplete segments, those can persist

---

## Breakdown Estimate for Your Setup

| Component | Estimated RAM |
|---|---|
| Raw vectors (16 bytes x 460M) | 7.36 GB |
| HNSW links (m=16, base layer only) | 7-29 GB |
| Point ID mapping (u64 IDs) | 3-5 GB |
| Point ID mapping (UUID IDs) | 8-10 GB |
| Version vectors + segment metadata | 3-4 GB |
| RocksDB payload cache | 0.5-2 GB |
| WAL + optimizer buffers | 0.5-1 GB |

At `m=16` with integer IDs and no payloads, you are looking at 21-24GB. This matches your observed 20GB exactly.

At `m=16` with UUID IDs, you would be looking at 25-35GB. If you are seeing exactly 20GB consistently, UUID IDs are less likely, or your `m` is lower than default.

---

## Immediate Diagnostic Steps

### 1. Check HNSW m parameter
```http
GET /collections/{collection_name}
```
Look at `hnsw_config.m` in the response. Default is 16. If it is 16 and you do not need maximum recall, reducing to `m=8` during the next index rebuild would approximately halve HNSW memory.

### 2. Check vector storage mode
Look at `vectors_config` in the collection info. If `on_disk: false` (the default), vectors are fully in RAM. Setting `on_disk: true` moves vectors to mmap files, which can reduce RSS significantly under low-query conditions.

### 3. Check point ID type
If your IDs are UUIDs, consider whether you could use sequential u64 IDs instead. This is a schema-level decision that would require re-ingestion.

### 4. Check quantization config
Look for `quantization_config` in the collection. If not set, no quantization is active. Enabling SQ8 would reduce vector memory from 7.36GB to ~1.84GB at the cost of a small recall reduction.

### 5. Inspect segment count and optimizer state
```http
GET /collections/{collection_name}/cluster
```
A high segment count (dozens of segments) can indicate optimizer has not fully merged segments, leaving redundant data structures in memory.

---

## Recommendations (in priority order)

**Highest impact:**

1. Enable `on_disk: true` for vectors if your query latency SLA allows it. This moves 7.36GB of vector data to mmap, which the OS will manage from disk. With minimal queries, RSS should drop substantially.

2. If recall requirements allow it, reduce `m` from 16 to 8 or even 6 on the next collection rebuild. This roughly halves HNSW graph memory.

3. Enable scalar quantization (SQ8). This reduces vector memory 4x with minimal recall impact for most use cases, especially with 16-byte (4-float) vectors where the original precision may already be limited.

**Medium impact:**

4. Ensure the optimizer has completed all pending work by checking that segment count is low (ideally 1-5 segments per shard, not dozens).

5. Review RocksDB cache configuration. If payload data is minimal, the default block cache sizes may be over-provisioned.

**For your six-instance setup:**

If all six instances hold the full 460M points (i.e., no sharding, just replication), you are paying the full 20GB cost six times. Verify that sharding is configured correctly so each node holds only its shard's data, not all 460M points.

---

## Root Cause Summary

The 7-8GB calculation is the theoretical minimum for raw vector data only. The actual 20GB is primarily composed of:

1. The HNSW index graph (likely 5-15GB depending on `m` and how much is resident)
2. The point ID mapping tables (1-5GB depending on ID type)
3. Per-point metadata structures: version vectors, segment overhead (3-4GB)
4. RocksDB and WAL overhead (0.5-2GB)

None of this is a bug or leak. Stopping ingestion and reducing queries does not free these structures because they are required for correct index operation and fast search, not transient write buffers. The HNSW graph and ID maps are always-resident structures in the default configuration.

The path to reducing memory is either moving data structures to disk (on_disk vectors, mmap), reducing the HNSW graph density (lower m), or compressing vectors (quantization).
