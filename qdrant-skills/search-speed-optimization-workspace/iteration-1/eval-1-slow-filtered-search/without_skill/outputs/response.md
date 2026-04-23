# Diagnostic Report: Slow Filtered Search on `products-us` Collection

## Cluster Details

- **URL**: `https://41933e38-7320-4675-b795-ffa6a7ed86d3.us-west-2-0.aws.cloud.qdrant.io:6333`
- **Collection**: `products-us`
- **Points count**: 500
- **Vector size**: 768 (Cosine distance)
- **Segments**: 7
- **Indexed vectors**: 0

## Root Cause: No HNSW Vector Index Built

The primary issue is that **zero vectors are indexed** in the HNSW graph. The collection has 500 points, but the `indexing_threshold` is set to 10,000. Since the point count (500) is below this threshold, Qdrant's optimizer never builds an HNSW index. Every search, both filtered and unfiltered, falls back to brute-force linear scan.

### Why filtered search is disproportionately slow

When there is no HNSW index, Qdrant cannot use its optimized filtered search strategies. With an HNSW index in place, Qdrant can:

1. **Pre-filter** candidates using the payload index before traversing the HNSW graph (for highly selective filters).
2. **Post-filter** during HNSW traversal by checking the payload condition as it explores graph neighbors.
3. Dynamically choose the best strategy based on filter selectivity.

Without the HNSW index, all searches are brute-force scans across all 7 segments. The category filter has roughly 25% selectivity (about 125 out of 500 points per category), meaning Qdrant must scan all vectors, check the filter condition on each one, and then rank. The additional filter evaluation overhead on every single vector during a full scan explains the 10x slowdown compared to an unfiltered brute-force scan, which only needs to compute distances without any payload lookups.

The `on_disk_payload: true` setting makes this worse. Since payloads are stored on disk, every filter check during the brute-force scan requires a disk read for the payload data, adding I/O latency on top of the computation.

## Additional Issues Found

### 1. Excessive Segment Fragmentation

The collection has **7 segments** for only 500 points. This is far more than necessary. Each segment is searched independently and results are merged. More segments means more overhead per query, especially for filtered searches where each segment must independently evaluate the filter condition.

### 2. Bloated Payload Data

The `description` field contains 2,000 characters of padding (all 'A' characters) per point. Combined with `on_disk_payload: true`, this creates unnecessary storage overhead. A full-text index (`text` type with `word` tokenizer) is also built on this field, which is wasteful given the field contains no meaningful tokens.

### 3. `full_scan_threshold` Set to 10,000

The `full_scan_threshold` in the HNSW config is 10,000. This parameter determines when Qdrant falls back from HNSW traversal to a full scan based on the estimated number of results after filtering. Since there is no HNSW index at all, this parameter is currently irrelevant, but it should be tuned once the index is built.

## Collection Configuration Summary

```
Vector Config:
  size: 768
  distance: Cosine
  on_disk: false

HNSW Config:
  m: 16
  ef_construct: 100
  full_scan_threshold: 10000

Optimizer Config:
  indexing_threshold: 10000  <-- ROOT CAUSE
  deleted_threshold: 0.2
  vacuum_min_vector_number: 1000

Payload Indexes:
  category:     keyword (500 points)
  tags:         keyword (500 points)
  product_name: keyword (500 points)
  price:        float   (500 points)
  description:  text    (500 points)

Strict Mode:
  enabled: true
  unindexed_filtering_retrieve: false
  unindexed_filtering_update: false
```

## Recommended Fixes

### Fix 1: Lower the Indexing Threshold (Primary Fix)

Lower `indexing_threshold` to 100 (or even 0) so the optimizer builds the HNSW index for the 500 points:

```bash
curl -X PATCH "{QDRANT_URL}/collections/products-us" \
  -H "api-key: {API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "optimizer_config": {
      "indexing_threshold": 100
    }
  }'
```

After this change, the optimizer will automatically build the HNSW index. Once the index exists, filtered searches can use the payload indexes (which are already created for `category`) in combination with the HNSW graph for efficient pre-filtering or post-filtering.

### Fix 2: Reduce Segment Count

Force segment consolidation by setting a lower `default_segment_number`:

```bash
curl -X PATCH "{QDRANT_URL}/collections/products-us" \
  -H "api-key: {API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "optimizer_config": {
      "default_segment_number": 2
    }
  }'
```

Alternatively, set `max_segment_size` to a value that would consolidate all points into fewer segments. Fewer segments means less per-query overhead.

### Fix 3: Clean Up Description Field

If the description field's text index is not being used for full-text search queries, delete it to reduce memory and storage overhead:

```bash
curl -X DELETE "{QDRANT_URL}/collections/products-us/index/description" \
  -H "api-key: {API_KEY}"
```

### Fix 4: Consider `on_disk_payload` Setting

With only 500 points, storing payloads in memory (`on_disk_payload: false`) would eliminate disk I/O during filter evaluation. This is especially impactful for filtered searches that must evaluate payload conditions on many candidate vectors:

This would need to be set when recreating the collection, as `on_disk_payload` cannot be changed after creation.

## Summary

The filtered search slowdown is caused by the absence of an HNSW vector index. The `indexing_threshold` (10,000) is higher than the point count (500), so Qdrant never builds the index. All searches run as brute-force scans. Filtered brute-force scans are significantly slower than unfiltered ones because each candidate requires a payload lookup (hitting disk due to `on_disk_payload: true`) in addition to the vector distance computation. Lowering `indexing_threshold` to trigger HNSW index construction is the primary fix. The payload index on `category` already exists, so once the HNSW index is built, Qdrant can use its optimized filtered search strategies and performance should improve dramatically.
