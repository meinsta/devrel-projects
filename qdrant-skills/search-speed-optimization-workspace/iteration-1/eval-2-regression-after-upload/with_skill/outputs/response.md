# Diagnosing Search Latency Regression After Bulk Upload

## Quick Triage

Your symptom is: "Search was fast (~20ms), now it's slow (200-300ms) after a data upload." This maps directly to **Phase 3D: Search was fast, now it's slow** in the diagnostic process.

---

## Phase 1: Detect (Information Gathered)

From what you've provided:

- **Qdrant version:** 1.12
- **Vector count:** ~2M vectors
- **Dimensions:** 768
- **Storage:** SSD-backed cluster
- **Baseline latency:** ~20ms per query (last week)
- **Current latency:** 200-300ms per query (10-15x regression)
- **Recent change:** Large data upload over the weekend
- **Config changes:** None reported

**Information we still need** (but can reason about):

1. `optimizer_status` from `GET /collections/{name}` (likely the key signal)
2. Current segment count vs. segment count before the upload
3. Whether quantization is enabled
4. Whether HNSW `ef` was set at query time or using collection defaults
5. RAM usage and whether the OS page cache is under pressure

---

## Phase 2: Classify

| Symptom | Match? |
|---|---|
| Single query latency too high | Yes, but as a consequence |
| Filtered search slow | Not reported |
| **Search was fast, now it's slow** | **Primary match** |

Classification: **Performance regression (Phase 3D)**, triggered by the weekend bulk upload.

---

## Phase 3D: Diagnosis

Walking through the 3D checklist in order of likelihood:

### 1. Optimizer is still running (MOST LIKELY cause)

This is the most probable root cause. After a bulk upload, the optimizer must:

- Merge the newly created segments (upload data lands in many small temporary segments)
- Rebuild HNSW indexes on the merged segments
- Apply quantization (if configured) to the new data

For 2M vectors at 768 dimensions, HNSW index construction is not trivial. Depending on the size of the upload relative to the existing data, the optimizer could still be rebuilding. During this process, search performance degrades significantly because:

- Queries must fan out across many unindexed or partially-indexed segments
- HNSW graphs in newly created segments may not yet be built, causing fallback to brute-force scan within those segments
- CPU resources are split between optimizer work and serving queries

**How to confirm:** Check `optimizer_status` in the collection info response (`GET /collections/{collection_name}`). If it shows anything other than `"ok"`, the optimizer is still running. Wait for it to finish, then re-test. Ref: [Optimizer monitoring](https://qdrant.tech/documentation/concepts/optimizer/#optimization-monitoring)

### 2. Unmerged segments from bulk upload (HIGHLY LIKELY, related to #1)

Even if the optimizer has finished running, or if it ran partially, there may be many small segments that have not been merged yet. Each search query must fan out to every segment. If the upload created dozens of small segments (which bulk uploads typically do), the per-segment overhead compounds.

**How to confirm:** Check the segment count in the collection info. If you see a segment count significantly higher than before (e.g., 20+ segments per shard), this is contributing to the problem. The merge optimizer should eventually consolidate these, but it may still be in progress. Ref: [Merge optimizer](https://qdrant.tech/documentation/concepts/optimizer/#merge-optimizer)

**What the timeline looks like:** A "big data upload" on 2M vectors at 768 dimensions on an SSD cluster could take anywhere from minutes to hours for the optimizer to fully process, depending on:
- How much data was uploaded (was it 100K vectors or 1M?)
- CPU cores available
- Whether the optimizer is configured with appropriate thresholds

### 3. Page cache eviction (POSSIBLE secondary cause)

The bulk upload process itself consumes significant RAM and I/O bandwidth. This can evict the OS page cache that was keeping HNSW graph data and vector data hot in memory. After the upload finishes, search queries must re-read data from SSD until the cache warms back up.

With 2M vectors at 768 dimensions (float32), the raw vector data alone is roughly:
- 2,000,000 x 768 x 4 bytes = ~5.7 GB

The HNSW graph adds additional memory. If total working set exceeds available RAM minus what the upload process consumed, cache eviction is a contributing factor.

**How to confirm:** Monitor memory usage on the nodes. If available RAM is low and disk I/O is high during searches, cache eviction is happening. This should resolve over time as the cache warms up, but only after the upload process and optimizer have stopped competing for resources.

### 4. Data volume growth (LESS LIKELY as sole cause)

More vectors means more HNSW hops during search. However, HNSW scales logarithmically with data size. Going from, say, 1.5M to 2M vectors would not cause a 10-15x regression by itself. This might account for a 10-20% increase, not a 10x increase.

This factor is worth noting but is almost certainly not the primary cause of a jump from 20ms to 200-300ms.

### 5. Config change or version change (RULED OUT)

You confirmed no config changes were made, and no version upgrade was performed. This eliminates these possibilities.

---

## Root Cause Assessment

**Primary cause: The optimizer is still rebuilding segments and HNSW indexes after the weekend bulk upload.** This is the classic "search was fast, now 5x slower after upload" pattern documented in the common patterns table.

**Contributing factors:** Possible page cache eviction from the upload I/O load, and unmerged small segments adding per-segment overhead to each query.

---

## Phase 4: Recommendations

In order of priority:

### Immediate Actions (no config changes needed)

**1. Check optimizer status and wait for completion.**

```bash
curl -s http://localhost:6333/collections/{collection_name} | jq '.result.optimizer_status'
```

If it returns anything other than `"ok"`, the optimizer is still working. This is the most likely explanation. Search latency should return to near-baseline once the optimizer finishes merging segments and rebuilding HNSW indexes. Do not make config changes while the optimizer is running.

Ref: [Optimizer monitoring](https://qdrant.tech/documentation/concepts/optimizer/#optimization-monitoring)

**2. Check segment count.**

```bash
curl -s http://localhost:6333/collections/{collection_name} | jq '.result.segments_count'
```

If segments are in the dozens (>20 per shard), the merge optimizer has not finished consolidating. This directly explains the regression. Each query fans out to all segments, and many small segments with partial or missing HNSW indexes will fall back to slower search.

Ref: [Merge optimizer](https://qdrant.tech/documentation/concepts/optimizer/#merge-optimizer)

**3. Monitor until optimizer completes, then re-benchmark.**

Set up a simple monitoring loop:

```bash
watch -n 10 'curl -s http://localhost:6333/collections/{collection_name} | jq "{optimizer_status: .result.optimizer_status, segments_count: .result.segments_count}"'
```

Once `optimizer_status` shows `"ok"` and segment count has stabilized at a low number, re-run your search benchmarks. Latency should be back near 20ms.

### If Latency Does Not Return to Baseline After Optimizer Finishes

**4. Enable scalar int8 quantization (if not already enabled).**

For 2M vectors at 768 dimensions, quantization provides a 4x compression on distance computation and keeps quantized vectors in RAM, reducing disk reads.

```bash
curl -X PUT http://localhost:6333/collections/{collection_name} \
  -H 'Content-Type: application/json' \
  -d '{
    "quantization_config": {
      "scalar": {
        "type": "int8",
        "always_ram": true
      }
    }
  }'
```

Note: this will trigger the optimizer again, so expect a temporary slowdown during rebuild.

Ref: [Scalar quantization](https://qdrant.tech/documentation/guides/quantization/#scalar-quantization)

**5. Tune `hnsw_ef` at query time.**

If you are not explicitly setting `hnsw_ef` in your search requests, it defaults to the collection-level `ef_construct` value, which is often 128 or higher. For search, an `ef` of 64-128 is typically sufficient and reduces latency.

```json
{
  "vector": [0.1, 0.2, ...],
  "limit": 10,
  "params": {
    "hnsw_ef": 64
  }
}
```

Ref: [Fine-tuning search parameters](https://qdrant.tech/documentation/guides/optimize/#fine-tuning-search-parameters)

### For Future Bulk Uploads

**6. Plan uploads during low-traffic windows.** The optimizer will consume CPU and I/O resources that compete with search serving. If you must upload during production hours, consider rate-limiting the upload or using smaller batch sizes.

**7. Set up monitoring on optimizer status and segment count.** Alert when segment count exceeds 20 per shard or when optimizer has been running for longer than expected. Use Qdrant's `/metrics` endpoint with Prometheus/Grafana.

Ref: [Monitoring setup](https://qdrant.tech/documentation/guides/monitoring/)

---

## What NOT to Do

- **Do not change config while the optimizer is running.** This will restart the optimization process and prolong the regression.
- **Do not increase segment count** thinking it will help. Fewer, larger segments are better for both latency and throughput once properly indexed.
- **Do not assume Qdrant is broken.** This is normal, expected behavior after a bulk upload. The optimizer needs time to rebuild indexes.
- **Do not set `exact: true`** as a workaround. This forces brute-force search and will be even slower at 2M vectors.

---

## Summary

The 10-15x latency regression from 20ms to 200-300ms after a weekend bulk upload is almost certainly caused by the optimizer still rebuilding HNSW indexes and merging segments. This is a well-known pattern in Qdrant. The fix is to wait for the optimizer to complete (check `optimizer_status`), then verify that search latency returns to baseline. No config changes should be necessary since your setup was performing well before the upload.

If latency does not fully recover after the optimizer finishes, consider enabling scalar int8 quantization with `always_ram: true` and tuning `hnsw_ef` at query time as secondary optimizations.
