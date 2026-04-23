# Diagnosis: Search Latency Regression After Bulk Upload

## Summary

A 10-15x latency regression (20ms to 200-300ms) immediately following a large data upload is a classic post-upload pattern. The most likely cause is that the HNSW optimizer has not yet finished processing the newly uploaded data, leaving many small unmerged segments that degrade search performance. This is expected behavior, not a bug or misconfiguration.

## Root Cause Analysis (in order of likelihood)

### 1. Optimizer Still Running After Upload (Most Likely)

When you do a bulk upload, Qdrant writes data into many small segments. The optimizer then needs to:

- Merge those small segments into larger ones
- Build HNSW indexes on the merged segments

Until this process completes, every search query fans out across all those small unmerged segments instead of a few large, well-indexed ones. This alone easily explains a 10-15x latency increase.

**What to check:** Query the collection info endpoint and look at `optimizer_status`. If it shows anything other than `ok` (e.g., `indexing` or shows active optimization tasks), this is your answer.

```bash
# Check optimizer status
curl -s http://localhost:6333/collections/YOUR_COLLECTION | jq '.result.optimizer_status'
```

**What to do:** Wait. Do NOT change any configuration while the optimizer is running. Changing config parameters (like segment count or HNSW settings) while optimization is in progress will restart the optimization process from scratch, prolonging the regression further. Once the optimizer finishes and reports `ok`, latency should return to the ~20ms range.

For a collection with 2M vectors at 768 dimensions, HNSW index building can take anywhere from minutes to hours depending on your hardware and the volume of new data uploaded.

### 2. Unmerged Segments from Bulk Upload

This is closely related to cause #1 but worth calling out separately. If you uploaded data rapidly (e.g., large batch inserts), Qdrant may have created dozens or even hundreds of small segments. The merge optimizer consolidates these over time, but until it does, search performance suffers because:

- Each query must search every segment independently
- Small segments lack optimized HNSW graphs
- The overhead of coordinating across many segments adds up

**What to check:** Look at the segment count in the collection info:

```bash
curl -s http://localhost:6333/collections/YOUR_COLLECTION | jq '.result.segments_count'
```

If this number is significantly higher than your `default_segment_number` (typically 2-4), segments are still being merged.

### 3. OS Page Cache Eviction

A large bulk upload writes a lot of data to disk. On an SSD-backed system, this can evict previously cached HNSW graph data and vector data from the OS page cache. After eviction, search queries hit cold disk reads instead of serving from memory, which is dramatically slower.

**What to check:** This is harder to confirm directly, but if the optimizer has already finished (status is `ok`) and latency is still elevated but gradually improving over time as queries warm the cache, this is the cause.

**What to do:** Run a few hundred warm-up queries. The page cache will repopulate as data is read from disk, and latency will gradually return to normal. You can also monitor disk I/O during queries. If you see significant read I/O during search, the cache is cold.

### 4. Data Volume Growth (Unlikely to Be Primary Cause)

HNSW search scales logarithmically with dataset size. Going from, say, 1.5M to 2M vectors would not explain a 10x regression on its own. However, if the upload significantly increased the dataset (e.g., doubled it), the combination of more data plus the above factors compounds the problem.

This is NOT your primary cause, but it may contribute a small amount of additional latency even after the optimizer finishes.

## Recommended Action Plan

1. **Check optimizer status immediately.** This is the single most important diagnostic step. If it is not `ok`, stop here and wait.

2. **Do not change any configuration.** Resist the urge to tune `hnsw_ef`, segment counts, or other parameters while the optimizer is running. This will make things worse.

3. **Monitor over time.** Check optimizer status periodically (every 10-15 minutes). Once it reports `ok`, run a latency test.

4. **If latency is still elevated after optimizer completes,** run warm-up queries to repopulate the page cache. A few hundred queries should be sufficient for 2M vectors.

5. **If latency remains high after optimizer is done and cache is warm,** then investigate further:
   - Confirm `hnsw_ef` at query time is reasonable (64-128 is typical; the default inherits from `ef_construct` which may be higher)
   - Consider enabling scalar int8 quantization with `always_ram=true` for a 4x memory reduction and faster distance computation
   - Check segment count is reasonable (should be close to `default_segment_number`)

## For Future Uploads

To minimize this disruption on future bulk uploads:

- Use the batch upsert API with reasonably sized batches (100-500 points per request)
- If possible, upload during low-traffic periods
- After upload completes, monitor `optimizer_status` before expecting production-level latency
- Consider setting up a monitoring alert on optimizer status so you know when indexing finishes

## References

- [Optimizer monitoring](https://qdrant.tech/documentation/concepts/optimizer/#optimization-monitoring)
- [Merge optimizer](https://qdrant.tech/documentation/concepts/optimizer/#merge-optimizer)
- [Fine-tuning search parameters](https://qdrant.tech/documentation/guides/optimize/#fine-tuning-search-parameters)
- [Scalar quantization](https://qdrant.tech/documentation/guides/quantization/#scalar-quantization)
