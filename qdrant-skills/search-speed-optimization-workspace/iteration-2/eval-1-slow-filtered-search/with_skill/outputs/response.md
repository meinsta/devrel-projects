# Diagnostic Report: Slow Filtered Search on `products-us`

## Cluster Details

- **Qdrant version**: 1.16.3
- **Cluster**: Single node (1 peer, 1 shard, no replicas)
- **Collection**: `products-us`
- **Points**: 500
- **Vector dimensions**: 768 (Cosine distance)
- **Segments**: 7

## Root Cause: No HNSW Index Built (indexed_vectors_count = 0)

The primary problem is that **no HNSW index exists on this collection**. The `indexed_vectors_count` is 0.

This happens because of the `indexing_threshold` setting. The collection has 500 points, but the optimizer's `indexing_threshold` is set to 10,000. Qdrant only builds an HNSW graph when the number of points in a segment exceeds this threshold. Since 500 < 10,000, Qdrant skips HNSW construction entirely and performs **brute-force linear scan** for every search.

Without an HNSW graph, the payload index on the `category` field cannot do what it's designed to do. Filtered HNSW works by traversing graph links and pruning nodes that don't match the filter. With no graph, there are no links to traverse, and the payload index provides minimal benefit.

```
Current state:
  indexed_vectors_count: 0
  points_count: 500
  indexing_threshold: 10000   <-- 500 < 10000, so no HNSW built
```

## Contributing Factors

### 1. Segment Fragmentation (7 segments for 500 points)

The collection has 7 segments for only 500 points (~71 points per segment). Every search query fans out to all 7 segments in parallel. At this small data size the overhead is negligible, but this fragmentation is a sign that data was inserted in many small batches without waiting for the optimizer to merge segments.

### 2. Payload Stored on Disk (`on_disk_payload: true`)

The `on_disk_payload` setting is `true`, meaning all payload data lives on disk rather than in RAM. When Qdrant evaluates a filter condition (e.g., `category = "electronics"`), it needs to read the payload index from disk. For small datasets this adds unnecessary I/O. For filtered search specifically, this can add latency since filter evaluation happens on every candidate point.

### 3. Category Field Has a Payload Index but No `is_tenant` Flag

The `category` field does have a keyword payload index (confirmed in `payload_schema`). However, it lacks the `is_tenant` parameter. With only 4 distinct values (electronics: 25.8%, clothing: 25.4%, books: 24.6%, food: 24.2%), this is a classic tenant-style field. Setting `is_tenant: true` tells Qdrant to structure the HNSW graph with separate entry points per tenant value, which dramatically speeds up filtered search for low-cardinality fields.

### 4. No Quantization

No scalar or product quantization is configured. While not the primary issue for filtered search slowness, enabling scalar int8 quantization with `always_ram: true` would reduce memory footprint by 4x and speed up distance computations.

### 5. Excessive Payload Indexes

All 5 payload fields are indexed: `product_name`, `category`, `tags`, `description` (full-text), and `price`. If only `category` is used in filters, the other indexes waste memory. The `description` field has a full-text index, which is particularly expensive.

## What the User Is Likely Experiencing

At 500 points, the actual search times are sub-millisecond for both filtered and unfiltered queries (measured at ~0.25ms each). If the user is seeing 10x slower filtered search, one of these scenarios is likely:

1. **The real dataset is larger than what's currently in the collection**, and the problem was observed before data was trimmed or recreated.
2. **The latency is dominated by network round-trip and payload retrieval**, not the vector search itself. With `on_disk_payload: true`, returning large payloads (each point has ~2KB of padding text in the `description` and `full_text_content` fields) involves disk reads.
3. **The 10x difference was observed during data upload**, when the optimizer was actively running and creating/merging segments.

## Fix: Step by Step

### Step 1: Lower the indexing threshold to trigger HNSW construction

```bash
curl -X PATCH \
  'https://41933e38-7320-4675-b795-ffa6a7ed86d3.us-west-2-0.aws.cloud.qdrant.io:6333/collections/products-us' \
  -H 'api-key: <your-api-key>' \
  -H 'Content-Type: application/json' \
  -d '{
    "optimizer_config": {
      "indexing_threshold": 100
    }
  }'
```

This will cause Qdrant to build an HNSW index since 500 > 100. Wait for `optimizer_status` to return `"ok"` and `indexed_vectors_count` to become 500 before proceeding.

### Step 2: Recreate the category index with `is_tenant: true`

First delete the existing index, then recreate it:

```bash
# Delete
curl -X DELETE \
  'https://41933e38-7320-4675-b795-ffa6a7ed86d3.us-west-2-0.aws.cloud.qdrant.io:6333/collections/products-us/index/category' \
  -H 'api-key: <your-api-key>'

# Recreate with is_tenant
curl -X PUT \
  'https://41933e38-7320-4675-b795-ffa6a7ed86d3.us-west-2-0.aws.cloud.qdrant.io:6333/collections/products-us/index' \
  -H 'api-key: <your-api-key>' \
  -H 'Content-Type: application/json' \
  -d '{
    "field_name": "category",
    "field_schema": {
      "type": "keyword",
      "is_tenant": true
    }
  }'
```

The `is_tenant` flag (available since Qdrant v1.11) creates separate HNSW entry points per category value. Since you have only 4 categories each covering ~25% of data, this ensures the HNSW traversal starts from nodes within the target category, avoiding wasted graph hops.

### Step 3: Move payload to RAM (optional, recommended for this data size)

```bash
curl -X PATCH \
  'https://41933e38-7320-4675-b795-ffa6a7ed86d3.us-west-2-0.aws.cloud.qdrant.io:6333/collections/products-us' \
  -H 'api-key: <your-api-key>' \
  -H 'Content-Type: application/json' \
  -d '{
    "params": {
      "on_disk_payload": false
    }
  }'
```

### Step 4: Remove unnecessary payload indexes

If you only filter on `category`, remove the indexes on fields not used in filters:

```bash
for field in product_name tags description price; do
  curl -X DELETE \
    "https://41933e38-7320-4675-b795-ffa6a7ed86d3.us-west-2-0.aws.cloud.qdrant.io:6333/collections/products-us/index/$field" \
    -H 'api-key: <your-api-key>'
done
```

### Step 5: Trigger re-indexing to rebuild HNSW with filterable links

After creating the payload index with `is_tenant`, the HNSW graph needs to be rebuilt to incorporate the filterable links. If the HNSW was built before the payload index existed, the graph won't have filter-aware links. Force a re-index by updating a collection parameter:

```bash
curl -X PATCH \
  'https://41933e38-7320-4675-b795-ffa6a7ed86d3.us-west-2-0.aws.cloud.qdrant.io:6333/collections/products-us' \
  -H 'api-key: <your-api-key>' \
  -H 'Content-Type: application/json' \
  -d '{
    "hnsw_config": {
      "m": 16
    }
  }'
```

Then monitor until optimization completes:

```bash
# Poll until optimizer_status = "ok" and indexed_vectors_count = 500
curl -s \
  'https://41933e38-7320-4675-b795-ffa6a7ed86d3.us-west-2-0.aws.cloud.qdrant.io:6333/collections/products-us' \
  -H 'api-key: <your-api-key>' | python3 -m json.tool
```

## Summary Table

| Issue | Severity | Fix |
|-------|----------|-----|
| No HNSW index (indexed_vectors_count = 0) | **Critical** | Lower `indexing_threshold` to 100 |
| Category index missing `is_tenant` | **High** | Recreate with `is_tenant: true` |
| 7 segments for 500 points | Medium | Will auto-resolve after optimizer runs with lower threshold |
| `on_disk_payload: true` | Medium | Set to `false` for this data size |
| Unnecessary payload indexes on 4 other fields | Low | Delete indexes not used in filters |
| No quantization | Low | Not needed at 500 points, consider for scale |

## References

- [Payload index documentation](https://qdrant.tech/documentation/concepts/indexing/#payload-index)
- [Tenant index (is_tenant)](https://qdrant.tech/documentation/concepts/indexing/#tenant-index)
- [Filterable HNSW](https://qdrant.tech/documentation/concepts/indexing/#filterable-hnsw-index)
- [Optimizer configuration](https://qdrant.tech/documentation/concepts/optimizer/)
- [Search optimization guide](https://qdrant.tech/documentation/guides/optimize/)
