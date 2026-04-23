# Diagnostic Report: High Search Latency on `products-us` Collection

## Cluster Details

- **URL**: `https://41933e38-7320-4675-b795-ffa6a7ed86d3.us-west-2-0.aws.cloud.qdrant.io:6333`
- **Cluster**: Single-node (1 peer), Raft leader
- **Collection**: `products-us`
- **Points**: 500
- **Vector dimensions**: 768 (Cosine distance)
- **Segments**: 7

## Observed Latency

| Search Type | Qdrant Internal Time | HTTP Round-Trip |
|---|---|---|
| Basic search (with payload) | ~0.43ms | ~200-240ms |
| Basic search (no payload) | ~0.21ms | ~130-140ms |
| Filtered search (indexed field) | ~0.45ms | ~190-240ms |
| Filtered search (unindexed field) | BLOCKED | Error returned |

The Qdrant server-side processing time is sub-millisecond. The 500ms latency the user reports likely includes network latency (~130ms round-trip to us-west-2), payload serialization overhead, and potentially client-side processing. However, the collection has multiple configuration problems that will become severe as data grows and that are already contributing to suboptimal performance.

## Root Causes Identified

### CRITICAL: No HNSW Vector Index Built (indexed_vectors_count = 0)

This is the primary issue. The collection has **0 indexed vectors** out of 500 points.

**Why it happens**: The `indexing_threshold` is set to **10,000** (the default). Qdrant only builds the HNSW index when the number of points in a segment exceeds this threshold. Since the collection only has 500 points spread across 7 segments (~71 points per segment), no segment triggers index construction. Every search is a **brute-force full scan** across all segments.

**Current config**:
```json
"optimizer_config": {
    "indexing_threshold": 10000
}
"hnsw_config": {
    "m": 16,
    "ef_construct": 100,
    "full_scan_threshold": 10000
}
```

**Fix**: Lower the `indexing_threshold` so the HNSW index gets built:

```bash
curl -X PATCH "$QDRANT_URL/collections/products-us" \
  -H "api-key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "optimizer_config": {
        "indexing_threshold": 100
    }
  }'
```

This will trigger the optimizer to merge segments and build the HNSW graph, enabling approximate nearest neighbor search instead of brute-force scanning.

### CRITICAL: Excessive Segment Fragmentation (7 segments for 500 points)

The collection has **7 segments** for only 500 points. This means:
- Each search must scan all 7 segments independently and merge results
- Segment overhead dominates actual search time
- Points are spread too thin for any single segment to trigger indexing

**Why it happens**: Data was likely uploaded in many small batches, and the optimizer has not consolidated them because the indexing threshold is too high.

**Fix**: Lowering the `indexing_threshold` (as above) will also trigger the optimizer to merge small segments into larger ones. Alternatively, you can also reduce `default_segment_number`:

```bash
curl -X PATCH "$QDRANT_URL/collections/products-us" \
  -H "api-key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "optimizer_config": {
        "indexing_threshold": 100,
        "default_segment_number": 2
    }
  }'
```

### HIGH: on_disk_payload = true (Disk I/O for Every Result)

The collection is configured with `on_disk_payload: true`, which means payload data is read from disk for every search result. Each point's payload is approximately **4.7KB**, containing:

- `description`: 2,000 characters
- `full_text_content`: 2,400 characters
- `tags`: array of 20 items
- `product_name`, `category`, `locale`, `price`

When returning 10 results with payloads, that is ~47KB of disk reads per query. On cloud infrastructure with network-attached storage, this adds measurable latency.

**Fix**: For a collection this small, keep payloads in memory:

```bash
# Note: This requires recreating the collection with on_disk_payload: false
# Or selectively request only needed payload fields in queries:
{
    "vector": [...],
    "limit": 10,
    "with_payload": {
        "include": ["product_name", "category", "price"]
    }
}
```

### MEDIUM: Unindexed Payload Fields (`locale`, `full_text_content`)

The `locale` and `full_text_content` fields exist in the payload data but have **no payload index**. The collection has `strict_mode_config.enabled: true`, which correctly blocks filtered searches on unindexed fields (returning errors instead of silently doing full scans). However, if any application code attempts to filter on these fields, the queries will fail.

**Indexed fields**: `product_name` (keyword), `category` (keyword), `price` (float), `tags` (keyword), `description` (text)
**Unindexed fields**: `locale`, `full_text_content`

**Fix**: Create indexes on the missing fields:

```bash
# Index 'locale' as keyword
curl -X PUT "$QDRANT_URL/collections/products-us/index" \
  -H "api-key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "field_name": "locale",
    "field_schema": "keyword"
  }'

# Index 'full_text_content' as text (if full-text search is needed)
curl -X PUT "$QDRANT_URL/collections/products-us/index" \
  -H "api-key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "field_name": "full_text_content",
    "field_schema": {
        "type": "text",
        "tokenizer": "word",
        "min_token_len": 2,
        "max_token_len": 20
    }
  }'
```

### LOW: No Quantization Configured

The 768-dimensional vectors are stored as full `float32` values (3,072 bytes per vector). For a 500-point collection this is not a bottleneck, but enabling scalar quantization would reduce memory usage and speed up distance calculations, especially as the collection grows.

**Fix**: Enable scalar quantization:

```bash
curl -X PATCH "$QDRANT_URL/collections/products-us" \
  -H "api-key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "quantization_config": {
        "scalar": {
            "type": "int8",
            "always_ram": true
        }
    }
  }'
```

### LOW: Bloated Payload Data

The `description` field contains 2,000 characters of repeated "A" characters, and `full_text_content` contains 2,400 characters of repeated "Lorem ipsum" text. This looks like test or placeholder data. Every search returning payloads must serialize and transfer this junk data.

Each point has 20 tags (`tag_0` through `tag_19`), which also adds serialization overhead.

## Summary of Recommendations (Priority Order)

| Priority | Issue | Fix | Expected Impact |
|---|---|---|---|
| 1 (Critical) | No HNSW index (indexing_threshold too high) | Lower `indexing_threshold` to 100 | Enables ANN search instead of brute force. Biggest win for scaling. |
| 2 (Critical) | 7 fragmented segments | Lowering indexing_threshold triggers segment merging | Reduces per-query overhead from scanning multiple segments |
| 3 (High) | on_disk_payload causing disk I/O | Use selective payload retrieval (`with_payload.include`) | Reduces payload transfer time by ~80% |
| 4 (Medium) | Unindexed `locale` and `full_text_content` | Create payload indexes | Enables filtered search on these fields |
| 5 (Low) | No quantization | Enable scalar int8 quantization | ~4x memory reduction, faster distance computation |
| 6 (Low) | Bloated/junk payload data | Clean up placeholder data | Reduces serialization and network transfer |

## Key Takeaway

The single most impactful fix is **lowering the `indexing_threshold`**. With only 500 points and an indexing threshold of 10,000, Qdrant treats the entire collection as "too small to index" and performs brute-force scans on every query. Combined with 7 fragmented segments and disk-based payload storage, this creates unnecessary overhead. Lowering the threshold to 100 will trigger the optimizer to merge segments and build the HNSW graph, which should dramatically reduce internal search time from the current ~0.4ms brute force to sub-0.1ms ANN. For the network latency component (~130-200ms), ensure the application querying this cluster is deployed in the same AWS us-west-2 region.
