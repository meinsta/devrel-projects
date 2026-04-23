# Memory Analysis: 2.7B UUID Points, Everything On Disk, 20 GB/Instance

## Quick Triage

The symptom is "memory higher than expected with everything on disk." This maps to Phase 3B: unexpectedly high memory. The calculation gap (expected ~7-8 GB, seeing 20 GB) is real and explainable without connecting to the cluster.

---

## Why Each Instance Uses 20 GB

### Your Calculation Is Correct But Incomplete

The ID tracker estimate of ~7-8 GB for 460M points (460M x 16 bytes = 7.36 GB) is accurate. The ID tracker is always in RAM and cannot be moved to disk. But it is only one of several forced-resident memory consumers.

Here is what "everything on disk" does and does not cover:

| Component | On Disk? | Notes |
|---|---|---|
| Vectors | Yes (`on_disk=true`) | Mmap'd, OS caches pages as needed |
| Payloads | Yes (`on_disk_payload=true`) | Moved to disk |
| HNSW graph | Yes (`hnsw_config.on_disk=true`) | Moved to disk |
| ID tracker | NO | Always in RAM. Not configurable. ~16 bytes/UUID point |
| Payload indexes | NO (by default) | Kept in RAM even when payloads are on disk |
| Collection/segment overhead | NO | 12-14 MB per collection, per shard metadata |

### The Hidden Memory Consumers

At 460M points per instance with UUID IDs, the breakdown is likely:

**1. ID tracker: ~7-8 GB**
- UUID = 16 bytes per point
- 460M points x 16 bytes = 7.36 GB
- This is always in RAM. No way around it.

**2. Payload indexes: likely 2-8 GB depending on schema**
- This is the most probable cause of the remaining 12-13 GB gap
- Payload indexes live in RAM by default even when `on_disk_payload=true`
- `on_disk_payload=true` moves the raw payload data to disk, but index structures stay in RAM
- Common index memory costs at 460M points:
  - Keyword index on a UUID field: ~8-16 bytes per unique value = 4-7 GB for 460M unique UUIDs
  - Full-text index: typically 2-5x the size of the indexed text content
  - Geo index: ~24 bytes per point = 11 GB at 460M points
  - Integer/float index: ~8 bytes per unique value

**3. OS page cache: variable, but inflates reported numbers**
- `htop`, `top`, and `docker stats` report data memory plus OS page cache combined
- Even with vectors on disk, the OS will cache recently accessed mmap pages in unused RAM
- At 20 GB reported per instance, some portion may be cache, not data
- Without running `GET /telemetry`, you cannot know how much is actual data vs cache
- Telemetry separates the two. This is the single most important diagnostic call to make.

**4. Segment overhead**
- Each segment carries its own ID tracker slice, metadata, and internal structures
- If segments have not been fully merged (check `segments_count` in collection info), overhead multiplies
- More than 20 segments per shard is a signal that the optimizer is behind or misconfigured

**5. Collection overhead**
- 12-14 MB per collection baseline
- At scale with many collections this adds up, but unlikely to explain the gap here

### Likely Root Cause

The gap between your 7-8 GB estimate and the observed 20 GB is most likely payload indexes. The calculation only accounted for the ID tracker. If you have any indexed payload fields, especially:

- UUID or high-cardinality keyword fields
- Full-text indexed fields
- Geo fields

...those indexes are sitting in RAM and are not moved to disk by `on_disk_payload=true`. A UUID keyword index alone at 460M points would add 4-7 GB. Two such indexes covers the entire gap.

The second most likely contributor is OS page cache inflating the reported number. You need telemetry data to distinguish data from cache.

---

## Will Doubling the Replication Factor Double Memory?

**Short answer: RF=2 doubles data memory, but total observed memory increase depends on how much of current usage is OS page cache.**

The rule from the skill is:

> RF=2 means 2x data memory (HNSW, ID tracker, quantized vectors) but not 2x OS page cache.

Breaking this down for your scenario:

**If current 20 GB is mostly data memory (worst case):**
- RF=2 would bring each instance to approximately 40 GB
- Data memory scales linearly with replicas because each replica holds a full independent copy of ID tracker, payload indexes, and segment structures
- The HNSW graph is on disk, but its in-RAM index structures still have a resident footprint

**If current 20 GB is partially OS page cache (likely case):**
- Suppose 12 GB is data memory and 8 GB is cache
- RF=2 would increase data to ~24 GB, but cache is shared at the OS level and does not double with replica count
- Observed total might go from 20 GB to ~28-30 GB, not 40 GB

**What you need to know before increasing RF:**

Without telemetry data distinguishing data vs cache, you cannot safely predict whether RF=2 will push instances into dangerous territory. Run `GET /telemetry` on one instance and compare `app.memory_usage` (total including cache) against per-collection `memory_usage` (data only). If data memory is already 80%+ of available RAM per instance, RF=2 will cause OOM crashes during any resharding or replica migration, since that process requires temporary 1.5-2x headroom.

---

## Recommendations

In priority order based on the skill's Phase 4 table and this specific scenario:

**1. Run telemetry before making any changes**
- `GET /telemetry` to separate data memory from OS page cache
- This is required before any other action. The 20 GB number is uninterpretable without it.

**2. Audit payload indexes**
- `GET /collections/{name}` and inspect `payload_schema`
- For each indexed field, ask: is this field actually used in filters?
- UUID fields indexed as keywords are a common mistake at this scale. They cost 4-7 GB per index and are rarely useful for filtering.
- Indexes on fields not used in filters should be dropped entirely
- Indexes on infrequently filtered fields can use per-index `on_disk=true` to move the index structure to disk

**3. Check segment count**
- If `segments_count` is high (>20 per shard), the optimizer may not be merging segments
- Each unmerged segment carries its own ID tracker slice and overhead
- Reduce `default_segment_number` in `optimizers_config` if needed

**4. Check Qdrant version**
- If on a version before v1.13, upgrade. Versions before v1.13 had a known slow memory growth issue (1-12 MB/day) that compounds over time.

**5. Do not increase RF until telemetry is reviewed**
- If data memory is already near capacity, RF=2 will cause OOM during any rebalancing operation
- Know your data vs cache split first

---

## Memory Estimation Reference

The skill's formula:
```
memory_size = number_of_vectors * vector_dimension * 4 bytes * 1.5
```

This 1.5x covers HNSW graph, ID tracker, and segment metadata. It does NOT include payload indexes or collection overhead. Your situation with UUID IDs and potential payload indexes means real memory will exceed this estimate.

For UUID points with payload indexes:
```
estimated_data_memory = (460M * 16 bytes)          # ID tracker: 7.36 GB
                      + (payload_index_size)        # depends entirely on schema
                      + (collection_overhead)       # 12-14 MB per collection
                      + (segment_metadata_overhead) # depends on segment count
```

The gap between 7-8 GB and 20 GB is most likely payload indexes. Inspect the schema.
