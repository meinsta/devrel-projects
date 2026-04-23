# Diagnostic Report: Slow Filtered Search on `products-us` Collection

## Cluster Details

- **Cluster URL**: `https://41933e38-7320-4675-b795-ffa6a7ed86d3.us-west-2-0.aws.cloud.qdrant.io:6333`
- **Collection**: `products-us`
- **Points**: 500
- **Vector size**: 768 dimensions (Cosine distance)
- **Segments**: 7
- **Indexed vectors**: 0 (out of 500)

## Root Cause: No HNSW Vector Index (All Searches are Brute-Force)

The primary issue is that **`indexed_vectors_count` is 0**. This means no HNSW graph has been built for this collection. Every search, filtered or unfiltered, is performing a brute-force linear scan across all vectors.

### Why the HNSW index was never built

The `indexing_threshold` in the optimizer config is set to **10,000**, which is the default. Qdrant only builds an HNSW index when the number of points in a segment exceeds this threshold. With only 500 points spread across 7 segments (~71 points per segment on average), no segment comes close to the 10,000-point threshold. The optimizer has run **0 optimizations** (confirmed via telemetry: `total_optimized_points: 0`, `count: 0`).

This means:
- **Unfiltered search**: brute-force scan of all 500 vectors
- **Filtered search**: brute-force scan of all 500 vectors, then apply the category filter (or filter first, then score the subset)

### Why filtered search is disproportionately slower

Without an HNSW graph, Qdrant falls back to a plain linear scan for vector scoring. When a filter is applied on a collection without an HNSW index, the engine must:

1. Evaluate the payload filter against every point (even with a payload index, it still needs to build a candidate bitmap)
2. Score the filtered subset of vectors using brute-force distance computation
3. There is additional overhead from combining filter evaluation with vector scoring in a non-indexed context

With an HNSW index, filtered search is efficient because Qdrant can traverse the graph and check filter conditions at each node, pruning large portions of the search space. Without the graph, there is no structure to prune against, so the filter adds pure overhead on top of the already-linear scan.

Additionally, the 7 segments add overhead. Each segment must be searched independently and results merged. With an optimized collection, the optimizer would merge these into fewer, larger segments with HNSW indexes.

## Additional Observations

### 1. Payload indexes exist but are underutilized

The collection has payload indexes on the right fields:
- `category`: keyword index (500 points)
- `tags`: keyword index (500 points)
- `price`: float index (500 points)
- `product_name`: keyword index (500 points)
- `description`: text index (word tokenizer)

These payload indexes are correctly configured. The `category` field does have a keyword index, so the filter evaluation itself is not the bottleneck. The problem is the lack of a vector index (HNSW) to combine with it.

### 2. Strict mode is enabled and working correctly

```json
"strict_mode_config": {
  "enabled": true,
  "unindexed_filtering_retrieve": false,
  "unindexed_filtering_update": false
}
```

Filtering on a non-indexed field (e.g., `locale`) is correctly rejected with an error. This confirms the payload index for `category` is present and being used. The issue is purely on the vector index side.

### 3. Category distribution is balanced

- electronics: 129 points (25.8%)
- books: 123 points (24.6%)
- food: 121 points (24.2%)
- clothing: 127 points (25.4%)

No category is extremely rare or dominant, so filter selectivity is not an unusual factor here.

### 4. Large payloads per point (~4.6 KB each)

Each point carries a substantial payload:
- `description`: ~2,000 chars of repeated 'A' characters
- `full_text_content`: ~2,400 chars of repeated "Lorem ipsum" text
- `tags`: 20 tags per point

With `on_disk_payload: true`, payloads are stored on disk rather than in RAM. This is fine for storage, but when the engine needs to evaluate filters by reading payload data from disk (for non-indexed fields), it would be slow. For indexed fields like `category`, the payload index avoids this disk read, which is good.

### 5. No quantization configured

The collection has `quantization_config: null`. For 500 points at 768 dimensions, the total vector data is ~1.5 MB (`vectors_size_bytes: 1536000`), which fits easily in memory. Quantization would not meaningfully help at this scale but would be relevant if the collection grows.

## Solution: Lower the Indexing Threshold

The fix is to lower `indexing_threshold` so that the optimizer builds HNSW indexes for the existing segments:

```bash
curl -X PATCH \
  -H "api-key: <your-api-key>" \
  -H "Content-Type: application/json" \
  "https://41933e38-7320-4675-b795-ffa6a7ed86d3.us-west-2-0.aws.cloud.qdrant.io:6333/collections/products-us" \
  -d '{
    "optimizer_config": {
      "indexing_threshold": 100
    }
  }'
```

Setting `indexing_threshold` to 100 (or even 0 to force immediate indexing) will trigger the optimizer to:
1. Merge the 7 small segments into fewer, larger segments
2. Build HNSW graphs on those segments
3. Enable efficient graph-based filtered search

After this change, wait for the optimizer to complete (check `optimizer_status` and `indexed_vectors_count`). Once `indexed_vectors_count` equals 500, filtered searches will use HNSW graph traversal with inline filter checks, which is dramatically faster than brute-force.

## Summary

| Finding | Details |
|---|---|
| **Root cause** | `indexing_threshold` (10,000) is higher than the point count (500), so no HNSW index was built |
| **Indexed vectors** | 0 out of 500 |
| **Segments** | 7 unoptimized segments (no merging has occurred) |
| **Optimizer runs** | 0 total optimizations |
| **Payload index** | `category` keyword index exists and works correctly |
| **Fix** | Lower `indexing_threshold` to 100 or less to trigger HNSW index construction |
| **Expected improvement** | Filtered search should become comparable in speed to unfiltered search once the HNSW graph is built |
