# Diagnosing Search Latency Regression After Bulk Upload (20ms to 200-300ms)

## Summary

A 10-15x latency regression after a bulk data upload, with no config changes, almost certainly points to one (or a combination) of these root causes:

1. **The optimizer is still running** (rebuilding segments and HNSW indexes after the upload)
2. **Unmerged small segments** from the bulk upload are forcing search to fan out across many segments
3. **OS page cache eviction** caused by the upload's I/O pressure, forcing HNSW and vector reads to go to disk

Below is the full diagnostic reasoning and recommended actions.

## Most Likely Cause: Optimizer Still Running / Unmerged Segments

When you perform a large bulk upload to Qdrant, the data initially lands in many small, unindexed segments. The optimizer then kicks in asynchronously to:

1. **Merge small segments** into larger ones (merge optimizer)
2. **Build HNSW indexes** on segments that exceed the `indexing_threshold_kb` (default: 20 MB)

Until this process completes, search suffers in two ways:

- **Fan-out penalty**: Each search query must traverse every segment. If your upload created dozens or hundreds of small segments, the per-segment overhead multiplies. Instead of searching 2-4 well-indexed segments, you might be searching 50+ segments, many of which use brute-force (no HNSW index) because they are below the indexing threshold individually.

- **Brute-force on unindexed segments**: Small segments that have not yet been merged above the indexing threshold use linear scan instead of HNSW graph traversal. With 768-dimension float32 vectors, brute-force distance calculations are expensive.

### How to confirm

Check the optimizer status via the REST API:

```
GET /collections/{collection_name}
```

Look at two fields:
- `optimizer_status`: If this shows anything other than `"ok"`, the optimizer is still working. Search will be degraded until it finishes.
- `segments_count`: If this is significantly higher than your `default_segment_number` (default: typically 2-4), segments have not yet been merged.

You can also check optimization progress (Qdrant v1.17+):

```
GET /collections/{collection_name}/optimizations
```

### What to do

**If the optimizer is still running**: Wait for it to finish. This is the most common resolution. Depending on the volume uploaded (at 2M vectors with 768 dimensions, your dataset is roughly 6 GB of raw vector data), HNSW rebuild and segment merging can take anywhere from minutes to hours depending on CPU cores and disk speed.

**If the optimizer appears idle but segment count is still high**: The optimizer may need a nudge. You can trigger re-optimization by updating a collection parameter (this forces the optimizer to re-evaluate):

```
PATCH /collections/{collection_name}
{
    "optimizers_config": {
        "indexing_threshold": 20000
    }
}
```

(Setting the value to what it already is can still trigger the optimizer to re-run.)

## Second Most Likely Cause: OS Page Cache Eviction

Qdrant memory-maps its HNSW graph and vector data by default. The OS page cache keeps frequently accessed pages in RAM for fast access. Before the upload, your working set (the HNSW graph and vector data for the original dataset) was likely fully cached in RAM, enabling the 20ms latency.

A large bulk upload generates massive I/O (writing new segments, WAL entries, merging). This I/O pressure can evict cached pages from the OS page cache. After the upload, when search queries resume, they now hit cold pages that must be read from disk (even SSD reads are 10-100x slower than RAM).

### How to confirm

- If search latency gradually improves over the first few hundred queries after the upload finishes, this confirms cache warming is occurring.
- Check system memory: if the upload consumed a lot of RAM for write buffers and new segment construction, the cache would have shrunk.

### What to do

- **Let the cache warm up naturally**: Run a representative set of queries. Latency should gradually return to baseline as pages are cached.
- **If you have enough RAM**: The cache will repopulate on its own. No action needed beyond patience.
- **If RAM is tight**: Consider whether you need to add more RAM to your nodes. The rule of thumb is that data memory (HNSW + ID tracker + payload indexes) should stay below 70-80% of available RAM, leaving the rest for page cache.

## Third Possibility: HNSW Graph Quality Degraded

If the optimizer has finished but latency is still elevated, consider that the HNSW graph may have been rebuilt with suboptimal structure. This can happen if:

- Segments were merged in a way that produced larger-than-expected segments
- The HNSW graph was built while the optimizer was under resource pressure

### How to confirm

Compare the number of segments and their sizes before and after the upload. Check `hnsw_config` parameters (`m`, `ef_construct`) to ensure they are reasonable (defaults: `m=16`, `ef_construct=100`).

### What to do

If the graph quality is suspect, you can force a rebuild by temporarily changing a collection parameter and changing it back:

```
PATCH /collections/{collection_name}
{
    "hnsw_config": {
        "ef_construct": 100
    }
}
```

## Diagnostic Checklist

Run these checks in order:

| Step | Check | Command | What to look for |
|------|-------|---------|-----------------|
| 1 | Optimizer status | `GET /collections/{name}` | `optimizer_status` should be `"ok"` |
| 2 | Segment count | Same response as above | `segments_count` should be low (2-8, not 50+) |
| 3 | HNSW config | Same response, `hnsw_config` field | `m=16`, `ef_construct=100` are reasonable defaults |
| 4 | System memory | `free -h` or equivalent | Check available RAM vs total dataset size |
| 5 | Disk I/O | `iostat` or equivalent | Check if disk is still under heavy I/O from optimizer |
| 6 | Gradual improvement test | Run 100 queries sequentially | If latency drops from 300ms to 50ms over those queries, it is cache warming |

## Recommended Actions (in priority order)

1. **Check optimizer status first.** If it is still running, wait. This alone explains the 10-15x regression and resolves itself.

2. **Check segment count.** If it is high (20+), the optimizer needs more time to merge, or needs to be triggered.

3. **Monitor cache warming.** After the optimizer finishes, run a burst of queries. If latency drops back toward 20ms, the issue was cache eviction and is self-resolving.

4. **If latency persists after optimizer completes and cache warms**: Check search parameters. Ensure `hnsw_ef` at query time is not set too high. For 2M vectors at 768 dimensions, `hnsw_ef=128` should yield good recall with low latency.

5. **Consider enabling scalar quantization** if not already enabled. With 2M vectors at 768 dimensions, scalar int8 quantization with `always_ram=true` would compress your vectors from ~6 GB to ~1.5 GB, keeping quantized vectors in RAM for faster distance computation:

```
PUT /collections/{collection_name}
{
    "quantization_config": {
        "scalar": {
            "type": "int8",
            "always_ram": true
        }
    }
}
```

## What NOT to Do

- **Do not restart Qdrant while the optimizer is running.** This can corrupt segments and make the problem worse.
- **Do not immediately add hardware.** The regression is almost certainly transient, caused by the post-upload optimization process.
- **Do not lower `hnsw_ef` or `ef_construct` reactively.** The latency is not caused by HNSW parameters being too high. It is caused by the optimizer not having finished rebuilding indexes.
- **Do not re-upload the data.** This would restart the entire optimization cycle.

## Expected Timeline to Resolution

- **Optimizer completion**: For 2M vectors at 768 dimensions on SSD, expect 15-60 minutes for full segment merge and HNSW rebuild, depending on CPU cores and whether `max_indexing_threads` is configured.
- **Cache warming**: After optimizer completes, expect 5-15 minutes of gradual improvement as the OS page cache repopulates with the new segment data.
- **Full recovery**: Search latency should return to the 20ms range (or close to it) once both processes complete.

## Long-term Prevention

For future bulk uploads, consider this workflow to minimize search disruption:

1. **Before uploading**: Set `indexing_threshold_kb` to a very high value (e.g., 100000000) to prevent the optimizer from building HNSW during the upload.
2. **Upload data** in batches of 64-256 points with 2-4 parallel streams.
3. **After upload completes**: Restore `indexing_threshold_kb` to the default (20000). This lets the optimizer merge all segments first, then build HNSW once on the merged segments, rather than repeatedly building and discarding indexes on intermediate segments.

This approach significantly reduces total optimization time and minimizes the window of degraded search performance.
