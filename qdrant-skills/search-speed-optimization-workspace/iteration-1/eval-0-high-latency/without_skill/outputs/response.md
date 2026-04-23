# Diagnostic Report: High Search Latency on `products-us` Collection

## Executive Summary

The `products-us` collection is experiencing elevated search latency due to **multiple compounding issues**. The primary root cause is that **zero vectors are indexed in the HNSW graph**, meaning every search is performing a full brute-force scan instead of an approximate nearest neighbor (ANN) lookup. Secondary issues include excessive segment fragmentation, bloated payloads, and on-disk payload storage adding I/O overhead.

## Cluster and Collection Details

| Property | Value |
|---|---|
| Points count | 500 |
| **Indexed vectors count** | **0 (CRITICAL)** |
| Segments count | 7 |
| Vector dimension | 768 |
| Distance metric | Cosine |
| Quantization | None |
| On-disk payload | true |
| HNSW m | 16 |
| HNSW ef_construct | 100 |

## Issue #1 (PRIMARY): No HNSW Index Built (0 Indexed Vectors)

**Finding:** `indexed_vectors_count: 0` while `points_count: 500`.

**Root cause:** The `indexing_threshold` is set to `10000`, which means the HNSW index is only built when a segment reaches 10,000 vectors. With only 500 points in the collection, no segment ever reaches this threshold, so **the optimizer never builds an HNSW index**. Every single search query performs a full brute-force linear scan across all segments.

**Impact:** For 500 points with 768-dimensional vectors, a brute-force scan is not catastrophically slow (the Qdrant internal time is ~0.5ms), but this architecture does not scale. More importantly, the 7 fragmented segments compound this problem because the engine must scan each segment independently and merge results.

**Fix:** Lower the `indexing_threshold` to a value below the number of points in the collection:

```bash
curl -X PATCH "https://<cluster>/collections/products-us" \
  -H "Content-Type: application/json" \
  -d '{
    "optimizer_config": {
      "indexing_threshold": 100
    }
  }'
```

This will trigger the optimizer to build the HNSW index for segments with 100+ vectors, which should cover the data in this collection.

## Issue #2: Excessive Segment Fragmentation (7 Segments for 500 Points)

**Finding:** The collection has 7 segments for just 500 points (roughly 71 points per segment).

**Root cause:** Data was likely inserted in many small batches without allowing the optimizer to merge segments. The `default_segment_number: 0` setting means Qdrant uses its default segmentation logic. Combined with the high `indexing_threshold`, the optimizer has no incentive to merge these small segments into larger, indexable ones.

**Impact:** Each search must scan all 7 segments independently, merge results, and handle the overhead of 7 separate data structures. For a 500-point collection, a single segment would be optimal.

**Fix:** Lowering the `indexing_threshold` (as described above) will cause the optimizer to merge small segments into larger ones that exceed the threshold. The optimizer should consolidate these 7 segments down to 1-2 segments automatically after the threshold change.

## Issue #3: Large Payloads with On-Disk Storage

**Finding:** Each point carries approximately 4.7 KB of payload data, including:
- `description`: 2,000 bytes of padded text (appears to be filler "AAA..." content)
- `full_text_content`: 2,400 bytes of lorem ipsum text
- `tags`: array of 20 tags
- Plus `product_name`, `category`, `locale`, `price`

Combined with `on_disk_payload: true`, every search result requires disk I/O to fetch the payload.

**Impact:** When returning 10 results with full payloads, the response carries ~47 KB of payload data. The disk reads for on-disk payload add latency. Our tests show:
- Search with full payload: ~0.5-0.9ms internal, ~190ms HTTP round-trip
- Search without payload: ~0.25ms internal, ~135ms HTTP round-trip
- Search with selective payload (name, category, price only): ~0.45ms internal, ~130ms HTTP round-trip

The ~60ms HTTP round-trip difference between full-payload and no-payload queries is partly network transfer overhead (47 KB vs minimal response) and partly disk I/O.

**Fix options:**
1. Use selective payload retrieval in queries: `"with_payload": {"include": ["product_name", "category", "price"]}` to avoid transferring large text fields unnecessarily.
2. If the `description` and `full_text_content` fields are not needed for filtering, consider whether they need to be stored in Qdrant at all, or if they can be fetched from a separate data store.
3. For a 500-point collection, consider setting `on_disk_payload: false` to keep payloads in memory for faster retrieval.

## Issue #4: Unindexed Payload Fields

**Finding:** The `locale` and `full_text_content` fields are stored but not indexed. The `description` field has a text index, and `category`, `tags`, `product_name`, and `price` all have indexes.

**Impact:** If searches filter by `locale` (which is likely for a locale-specific collection like `products-us`), those filters would require a full scan since there is no index on the `locale` field. However, the `strict_mode_config` has `unindexed_filtering_retrieve: false` and `unindexed_filtering_update: false`, meaning the cluster would actually **reject** queries that attempt to filter on unindexed fields.

**Fix:** If the `locale` field is used for filtering, create a payload index:

```bash
curl -X PUT "https://<cluster>/collections/products-us/index" \
  -H "Content-Type: application/json" \
  -d '{
    "field_name": "locale",
    "field_schema": "keyword"
  }'
```

## Issue #5: No Quantization

**Finding:** `quantization_config: null`. The 768-dimensional float32 vectors consume 3,072 bytes each (768 x 4 bytes). For 500 points, this is ~1.5 MB, which fits in memory, but quantization would still speed up distance calculations.

**Fix:** Enable scalar quantization to reduce memory footprint and speed up distance comparisons:

```bash
curl -X PUT "https://<cluster>/collections/products-us" \
  -H "Content-Type: application/json" \
  -d '{
    "quantization_config": {
      "scalar": {
        "type": "int8",
        "quantile": 0.99,
        "always_ram": true
      }
    }
  }'
```

## Latency Breakdown

Based on the diagnostic measurements:

| Component | Estimated Time |
|---|---|
| Network round-trip (client to us-west-2) | ~120-130ms |
| Qdrant internal search (brute-force, no HNSW) | ~0.5ms |
| Payload disk I/O + serialization (full payload) | ~0.3-0.4ms |
| Response transfer (47 KB payload) | ~30-60ms |
| **Total observed (full payload)** | **~190-200ms** |

**Note on the 500ms claim:** The observed internal Qdrant search time is well under 1ms, and the total HTTP round-trip is ~190ms. If queries are consistently hitting 500ms, the extra latency may be coming from:
- Application-level overhead (SDK initialization, connection pooling issues)
- Client-side processing
- Concurrent load causing queueing
- Filtered queries hitting unindexed fields (which would be rejected by strict mode, potentially causing retries)
- Network congestion between the application and the cluster

## Recommended Action Plan (Priority Order)

1. **Lower `indexing_threshold` to 100** to trigger HNSW index construction and segment merging. This is the single most impactful change.
2. **Use selective payload retrieval** in queries to avoid transferring large text fields.
3. **Add a payload index on `locale`** if it is used for filtering.
4. **Enable scalar quantization** (`int8`) for faster distance calculations and lower memory usage.
5. **Consider setting `on_disk_payload: false`** for this small collection to avoid disk I/O for payload retrieval.
6. **Investigate the bloated payload fields** (`description` filled with "AAA...", `full_text_content` with lorem ipsum). These may be test data artifacts that should be cleaned up.

## Raw Diagnostic Data

### Collection Configuration
```json
{
  "status": "green",
  "optimizer_status": "ok",
  "indexed_vectors_count": 0,
  "points_count": 500,
  "segments_count": 7,
  "config": {
    "params": {
      "vectors": {"size": 768, "distance": "Cosine", "on_disk": false},
      "shard_number": 1,
      "replication_factor": 1,
      "on_disk_payload": true
    },
    "hnsw_config": {
      "m": 16,
      "ef_construct": 100,
      "full_scan_threshold": 10000,
      "max_indexing_threads": 0,
      "on_disk": false
    },
    "optimizer_config": {
      "indexing_threshold": 10000,
      "deleted_threshold": 0.2,
      "vacuum_min_vector_number": 1000,
      "flush_interval_sec": 5
    },
    "quantization_config": null
  }
}
```

### Indexed Payload Fields
- `category`: keyword (500 points)
- `tags`: keyword (500 points)
- `product_name`: keyword (500 points)
- `price`: float (500 points)
- `description`: text with word tokenizer (500 points)

### Unindexed Payload Fields
- `locale`: present in data, no index
- `full_text_content`: present in data, no index
