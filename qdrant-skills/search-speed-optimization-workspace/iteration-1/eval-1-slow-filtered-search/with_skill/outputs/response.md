# Diagnostic Report: Slow Filtered Search on `products-us` Collection

## Symptom

Filtered search on the `products-us` collection using the `category` field takes roughly 10x longer than unfiltered search.

## Triage Route

This matches the skill's Phase 3C: "Filtered search is slow." The skill states this is the most common SA complaint after memory, and the root cause is almost always missing payload indexes.

## Phase 1: Evidence Gathered

### Cluster and Version

- Qdrant version: **1.16.3**
- Single-node cluster (1 peer, 1 shard, replication factor 1)
- Optimizer status: **ok** (not actively rebuilding)

### Collection Configuration

| Parameter | Value |
|---|---|
| Vector dimensions | 768 |
| Distance metric | Cosine |
| Points count | 500 |
| Indexed vectors count | **0** |
| Segments count | 7 |
| HNSW m | 16 |
| HNSW ef_construct | 100 |
| HNSW on_disk | false |
| Indexing threshold | 10,000 |
| Vectors on_disk | false |
| on_disk_payload | **true** |
| Quantization | None |

### Payload Schema (Indexed Fields)

| Field | Index Type | Points |
|---|---|---|
| category | keyword | 500 |
| tags | keyword | 500 |
| product_name | keyword | 500 |
| price | float | 500 |
| description | text (word tokenizer) | 500 |

**Fields NOT indexed:** `full_text_content`, `locale`

### Category Distribution (Filter Selectivity)

| Category | Count | Percentage |
|---|---|---|
| electronics | 129 | 25.8% |
| clothing | 127 | 25.4% |
| books | 123 | 24.6% |
| food | 121 | 24.2% |

Only 4 unique categories. Each category contains roughly 25% of points, so filter selectivity is moderate (not excessively restrictive).

### Strict Mode

Strict mode is **enabled** with `unindexed_filtering_retrieve: false` and `unindexed_filtering_update: false`. This means Qdrant will block unindexed filtering operations when strict mode catches them.

## Phase 2: Classification

This is a **Phase 3C** issue: Filtered search much slower than unfiltered (filter penalty).

## Phase 3C: Diagnosis

Walking through the Phase 3C checklist:

### 1. Is the filtered field indexed?

**Yes, but with a critical caveat.** The `category` field does appear in `payload_schema` as a `keyword` index. However, there are two compounding problems:

**Problem A: `indexed_vectors_count` is 0.** The HNSW vector index has not been built at all. The `indexing_threshold` is set to 10,000 but the collection only has 500 points. When the point count is below `indexing_threshold`, Qdrant skips building the HNSW graph entirely and performs brute-force (plain) search on all segments. This means every search (filtered or unfiltered) does a linear scan, but filtered search is worse because it must also evaluate the filter condition on every point.

**Problem B: `on_disk_payload` is `true`.** With payloads stored on disk rather than in RAM, every filter evaluation during the brute-force scan requires a disk read to load the payload and check the `category` value. For unfiltered search, only vector distance computation happens (vectors are in RAM since `on_disk: false`). For filtered search, each candidate requires an additional disk I/O to read the payload. This is the multiplier that makes filtered search roughly 10x slower.

**Problem C: 7 segments for 500 points.** Having 7 segments for just 500 points means roughly 71 points per segment. This fragmentation adds per-segment overhead and means more scattered disk reads for payload evaluation.

### 2. High-cardinality field?

No. Only 4 categories. `is_tenant` is not needed here.

### 3. Filter too restrictive?

No. Each category covers ~25% of points. The filter is not restrictive enough to cause HNSW fallback issues. But since HNSW is not built at all (see Problem A), this point is moot.

### 4. Multiple filter conditions?

Not reported. The user is filtering on a single field (`category`).

### 5. On-disk payload without indexes?

**This is a contributing factor.** `on_disk_payload: true` means payload data lives on disk. While the `category` field has a keyword index (which should allow indexed filtering without touching the raw payload), the fact that HNSW is not built means the search falls back to plain segment scanning. During plain scanning with filters, the payload index helps narrow candidates, but the lack of HNSW means there is no graph traversal to benefit from the filterable index links.

## Root Cause Summary

The slow filtered search is caused by **three compounding issues**:

1. **No HNSW index built** because `indexing_threshold` (10,000) is far above the actual point count (500). All searches are brute-force scans across 7 segments.
2. **`on_disk_payload: true`** forces every filter evaluation to read from disk, adding I/O latency that compounds across the brute-force scan.
3. **7 segments** for 500 points creates unnecessary fragmentation and scattered I/O patterns.

The combination means: unfiltered search does a fast in-memory vector scan (vectors are in RAM), while filtered search does the same scan PLUS disk-based payload reads for filter evaluation on every candidate. The disk I/O overhead is the 10x penalty.

## Phase 4: Recommendations

Listed in order of impact:

### Priority 1: Lower `indexing_threshold` to build HNSW

Set `indexing_threshold` to a value below your point count so the HNSW graph gets built. With only 500 points, set it to 100 or even 0:

```bash
curl -X PATCH "https://41933e38-7320-4675-b795-ffa6a7ed86d3.us-west-2-0.aws.cloud.qdrant.io:6333/collections/products-us" \
  -H "api-key: <your-api-key>" \
  -H "Content-Type: application/json" \
  -d '{
    "optimizers_config": {
      "indexing_threshold": 100
    }
  }'
```

This triggers the optimizer to build the HNSW graph. Once built, filtered search uses the filterable HNSW index with the existing `category` keyword index, avoiding brute-force scans entirely. Monitor `optimizer_status` and `indexed_vectors_count` until it reaches 500.

Reference: [Optimizer docs](https://qdrant.tech/documentation/concepts/optimizer/)

### Priority 2: Move payloads to RAM (disable `on_disk_payload`)

Since the dataset is small (500 points), there is no reason to keep payloads on disk:

```bash
curl -X PATCH "https://41933e38-7320-4675-b795-ffa6a7ed86d3.us-west-2-0.aws.cloud.qdrant.io:6333/collections/products-us" \
  -H "api-key: <your-api-key>" \
  -H "Content-Type: application/json" \
  -d '{
    "params": {
      "on_disk_payload": false
    }
  }'
```

This eliminates disk I/O for payload reads during filter evaluation. For small collections, RAM is more than sufficient.

Reference: [On-disk payload index docs](https://qdrant.tech/documentation/concepts/indexing/#on-disk-payload-index)

### Priority 3: Reduce segment fragmentation

After applying the above changes, the optimizer should automatically merge segments. If the segment count remains high, you can set `default_segment_number` explicitly:

```bash
curl -X PATCH "https://41933e38-7320-4675-b795-ffa6a7ed86d3.us-west-2-0.aws.cloud.qdrant.io:6333/collections/products-us" \
  -H "api-key: <your-api-key>" \
  -H "Content-Type: application/json" \
  -d '{
    "optimizers_config": {
      "default_segment_number": 2
    }
  }'
```

Fewer segments mean less per-segment overhead and more efficient search.

Reference: [Merge optimizer docs](https://qdrant.tech/documentation/concepts/optimizer/#merge-optimizer)

### Priority 4 (optional): Consider removing bloated payload fields

Each point has a `description` field filled with ~2KB of "A" characters and a `full_text_content` field with ~5KB of "Lorem ipsum" text. These bloated payloads increase disk I/O costs when `on_disk_payload` is true. If these fields are not needed for search results, consider either:
- Not storing them in the payload (store externally)
- Not returning them in search results (use `with_payload` selectively, which you may already be doing)

### Priority 5 (not needed now, but for scale): Enable quantization

With only 500 points and 768 dimensions, the full vector data is about 1.5 MB, so quantization is not necessary. But if the collection grows significantly, enable scalar int8 quantization with `always_ram: true`:

```bash
curl -X PATCH "https://41933e38-7320-4675-b795-ffa6a7ed86d3.us-west-2-0.aws.cloud.qdrant.io:6333/collections/products-us" \
  -H "api-key: <your-api-key>" \
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

Reference: [Scalar quantization docs](https://qdrant.tech/documentation/guides/quantization/#scalar-quantization)

## Expected Outcome

After applying Priority 1 and 2:
- HNSW graph will be built, enabling graph-based filtered search using the existing `category` keyword index
- Payload reads will happen from RAM, eliminating disk I/O penalty
- Filtered search latency should drop to near-parity with unfiltered search (both sub-millisecond for 500 points)

## Monitoring Checklist

After applying changes:
1. Check `optimizer_status` is `ok` (not actively optimizing): `GET /collections/products-us`
2. Verify `indexed_vectors_count` equals `points_count` (500)
3. Verify segment count has decreased (target: 2)
4. Re-run both filtered and unfiltered searches to confirm latency parity
5. Monitor with `/metrics` endpoint if Prometheus/Grafana is set up

## What NOT to Do

- Do not set `hnsw_ef` extremely high thinking it will help filtered search (the problem is that HNSW is not built, not that ef is too low)
- Do not create payload indexes on `full_text_content` or `locale` unless you filter on those fields
- Do not use `exact: true` as a workaround (the collection is already doing brute-force; this does not help)
- Do not add replicas for a 500-point collection (the bottleneck is configuration, not capacity)
