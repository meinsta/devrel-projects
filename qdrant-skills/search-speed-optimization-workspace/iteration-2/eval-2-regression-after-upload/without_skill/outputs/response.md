# Diagnosing 10-15x Search Latency Regression After Bulk Upload (Qdrant 1.12)

## TL;DR

A 10-15x latency regression (20ms to 200-300ms) immediately following a large data upload, with no config changes, is a textbook post-upload optimization problem. The most likely cause is that the optimizer is still running: merging segments, rebuilding HNSW indexes, and consolidating data from the upload. The second most likely cause is OS page cache eviction from the upload I/O pressure, forcing search to hit cold SSD reads on mmap'd data.

Do NOT change any configuration while the optimizer is running. That restarts the optimization process and prolongs the regression.

---

## Step 1: Check Optimizer Status (Most Likely Cause)

The single most important diagnostic step is checking whether the optimizer is still working.

### What to check

```bash
# Check collection status
curl -s http://localhost:6333/collections/{collection_name} | jq '.result.status, .result.optimizer_status'
```

- **Green** status: optimizer is idle, optimization is complete.
- **Yellow** status: optimizer is actively running (indexing, merging segments). This is your most likely state.
- **Red** status: an optimization operation failed. Check Qdrant logs immediately.

If available (v1.17+), also check the detailed optimization progress:

```bash
curl -s http://localhost:6333/collections/{collection_name}/optimizations | jq .
```

### Why this causes the regression

When you upload a large batch of data, Qdrant creates many new small segments to hold the incoming points. Each search query fans out to ALL segments in parallel. If you went from, say, 4 well-merged segments to 40+ small unmerged segments after the upload, each query is now doing 10x more segment-level work. Additionally, the new segments likely have NOT built HNSW indexes yet (they're below the `indexing_threshold_kb` individually, or the indexing optimizer hasn't gotten to them yet), so Qdrant falls back to brute-force scan on those segments.

### What to do

**Wait.** The merge optimizer will combine small segments (it picks the three smallest and merges them iteratively). After merging, the indexing optimizer builds HNSW on segments that exceed `indexing_threshold_kb` (default 20 MB). For 2M vectors at 768 dimensions, the HNSW rebuild on merged segments can take significant time, depending on CPU count and `max_indexing_threads`.

Monitor progress by checking `indexed_vectors_count` vs `points_count`:

```bash
curl -s http://localhost:6333/collections/{collection_name} | jq '.result.vectors_count, .result.indexed_vectors_count'
```

If `indexed_vectors_count` is significantly less than the total vector count, HNSW hasn't been built on all data yet. Search on unindexed segments uses brute-force, which explains 200-300ms for your dataset size.

---

## Step 2: Check Segment Count

```bash
curl -s http://localhost:6333/collections/{collection_name} | jq '.result.segments_count'
```

A healthy collection of this size should have a relatively small number of segments (roughly equal to `default_segment_number`, which defaults to the number of CPUs). If you see dozens or hundreds of segments, the merge optimizer is still working through the backlog. The merge optimizer processes segments three at a time, so consolidating many small segments takes multiple rounds.

---

## Step 3: Check for Page Cache Eviction (Second Most Likely Cause)

Even if the optimizer has finished, the bulk upload may have evicted your HNSW index and vector data from the OS page cache. Qdrant uses mmap for vector storage and the HNSW graph by default. These files are not pinned in RAM; they rely on the OS page cache. A large upload generates heavy disk I/O that competes for cache space, pushing out the previously cached search-hot data.

### Symptoms

- Optimizer shows Green/complete.
- First queries after the upload are slow (200-300ms), but latency gradually improves over minutes/hours as the page cache warms back up from search traffic.
- Disk I/O is elevated during the slow period (check with `iostat` or similar).

### What to do

If this is the cause, latency will recover on its own as search traffic re-warms the cache. You can accelerate this by:

1. Running a warmup query batch (search with random vectors to force page cache population).
2. If you have enough RAM, ensure no other processes are competing for memory on the Qdrant nodes.

For 2M vectors at 768 dimensions (float32): raw vector data is approximately 2M * 768 * 4 bytes = ~5.7 GB. The HNSW graph adds roughly 1-2 GB depending on `m` parameter (default 16). You need sufficient RAM beyond Qdrant's process memory for the OS to cache this effectively.

---

## Step 4: Verify Data Growth Isn't the Issue

HNSW search time scales logarithmically with dataset size. Going from, say, 1.5M to 2M vectors should add maybe 10-15% to search time, not 10-15x. So data volume growth alone cannot explain this regression. However, if the upload was much larger than expected (e.g., doubling the collection from 1M to 2M), the combined effect of more data plus the above factors could compound.

Check the actual point count:

```bash
curl -s http://localhost:6333/collections/{collection_name}/points/count -X POST -H 'Content-Type: application/json' -d '{"exact": true}'
```

---

## Step 5: Check for Concurrent Optimizer Resource Contention

While the optimizer is merging segments and building HNSW, it competes with search for CPU and I/O. HNSW construction is CPU-bound. Segment merging is I/O-bound. On an SSD-backed cluster, I/O contention from merging should be moderate, but CPU contention from HNSW builds can directly slow search. If you have limited CPU cores, the optimizer may be consuming most of them.

You can check `max_indexing_threads` in your config. By default, Qdrant uses half the available CPUs for indexing. If you want search to take priority during this recovery window, you could temporarily reduce this, but be aware that doing so will make the optimizer take longer to finish.

---

## Summary of Most Probable Causes (Ranked by Likelihood)

| Rank | Cause | How to confirm | Expected recovery |
|------|-------|---------------|-------------------|
| 1 | Optimizer still running (segment merge + HNSW rebuild) | `optimizer_status` is Yellow, `indexed_vectors_count` < `points_count` | Wait for optimizer to complete (minutes to hours depending on cluster size) |
| 2 | Too many unmerged segments from upload | `segments_count` much higher than expected | Wait for merge optimizer to consolidate |
| 3 | OS page cache eviction from upload I/O | Green optimizer status but high disk I/O during search, latency improves over time | Run warmup queries, or wait for organic cache re-warming |
| 4 | CPU contention between optimizer and search | High CPU utilization, optimizer running | Wait for optimizer, or reduce `max_indexing_threads` temporarily |

---

## What NOT to Do

- **Do not change collection parameters while the optimizer is running.** Updating `hnsw_config`, `optimizer_config`, or `quantization_config` triggers a re-optimization, restarting the process and extending the downtime.
- **Do not kill or restart Qdrant while the optimizer is running.** This can corrupt segments and make things worse.
- **Do not increase segment count** thinking it will help search. Fewer segments is better for throughput; more segments is only useful for latency in already-optimized collections.
- **Do not panic and add quantization or change HNSW parameters** as a quick fix. The regression is transient and will resolve once the optimizer finishes.

---

## Preventive Measures for Future Bulk Uploads

For your next bulk upload, consider this workflow to minimize search disruption:

1. **Before upload:** Set `indexing_threshold_kb` to a very high value (e.g., `200000000`) to disable HNSW indexing during upload. This prevents the optimizer from trying to build indexes on every small batch.
2. **Create payload indexes before uploading** if you use filtered search. Payload indexes must exist before HNSW builds so that filterable vector index links are created.
3. **Upload data** in batches of 64-256 points with 2-4 parallel streams.
4. **After upload completes:** Restore `indexing_threshold_kb` to the default (20000) or your preferred value. This triggers a single, efficient optimization pass instead of dozens of incremental ones.
5. **Monitor** `optimizer_status` until it returns to Green, then validate search latency.

---

## References

- [Qdrant Optimizer documentation](https://qdrant.tech/documentation/concepts/optimizer/)
- [Optimize Performance guide](https://qdrant.tech/documentation/guides/optimize/)
- [Optimizing Memory for Bulk Uploads](https://qdrant.tech/articles/indexing-optimization/)
- [Bulk Upload Vectors tutorial](https://qdrant.tech/documentation/tutorials-develop/bulk-upload/)
- [Collections API](https://qdrant.tech/documentation/concepts/collections/)
- [Storage and mmap documentation](https://qdrant.tech/documentation/concepts/storage/)
- [Capacity Planning guide](https://qdrant.tech/documentation/guides/capacity-planning/)
