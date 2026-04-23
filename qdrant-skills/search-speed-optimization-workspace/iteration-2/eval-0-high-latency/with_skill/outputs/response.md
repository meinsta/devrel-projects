# Search Latency Diagnostic: products-us Collection

## Summary

The reported ~500ms search latency on `products-us` is NOT caused by Qdrant's search engine being slow. Qdrant's internal search time is consistently under 0.5ms (~0.2ms). The root causes are a combination of: (1) no HNSW index is built (brute-force scan on every query), (2) 7 unmerged segments forcing fan-out, (3) large payloads stored on disk causing I/O on retrieval, and (4) no quantization configured. The 500ms the user is seeing is almost certainly the end-to-end time including network round-trip from their application, which accounts for ~120-200ms per request from our test location. If the application is far from the us-west-2 cluster, or the client is not reusing connections, that alone explains most of the perceived latency.

That said, the collection configuration has several real problems that will become critical as data grows beyond the current 500 points.

## Cluster Details

- Qdrant version: 1.16.3
- Region: us-west-2 (AWS)
- Collection: `products-us`
- Vector dimension: 768 (Cosine distance)
- Points: 500
- Segments: 7
- Indexed vectors: **0** (no HNSW index built)
- Optimizer status: ok (not currently running)

## Root Cause Analysis

### Issue 1: Zero Indexed Vectors (No HNSW Index)

**This is the primary configuration problem.** The `indexed_vectors_count` is 0, meaning no HNSW graph has been built. Every search is a brute-force linear scan across all segments.

**Why it happened:** The `indexing_threshold` is set to 10,000, and the collection only has 500 points. Qdrant will not build an HNSW index until a segment exceeds this threshold. With only 500 points spread across 7 segments (~71 points per segment), no segment comes close to triggering index construction.

**Impact today:** Minimal for 500 points. Brute-force on 500 vectors takes ~0.2ms, which is fast. But this is a ticking time bomb: as data grows toward thousands of points, search latency will increase linearly instead of logarithmically.

**Fix:** Lower the indexing threshold so HNSW gets built:

```bash
curl -X PATCH "https://41933e38-7320-4675-b795-ffa6a7ed86d3.us-west-2-0.aws.cloud.qdrant.io:6333/collections/products-us" \
  -H "api-key: <your-api-key>" \
  -H "Content-Type: application/json" \
  -d '{"optimizer_config": {"indexing_threshold": 100}}'
```

This will trigger the optimizer to build HNSW indexes on existing segments. Wait for `optimizer_status` to return to `ok` before testing.

### Issue 2: 7 Unmerged Segments (Segment Proliferation)

The collection has 7 segments for only 500 points. This means every search fans out to all 7 segments, adding per-segment overhead. This is a classic pattern after multiple small batch uploads where the merge optimizer has not consolidated segments.

**Fix:** This should resolve automatically once the indexing threshold is lowered and the optimizer runs. If it does not, you can also set `default_segment_number` explicitly:

```bash
curl -X PATCH "https://41933e38-7320-4675-b795-ffa6a7ed86d3.us-west-2-0.aws.cloud.qdrant.io:6333/collections/products-us" \
  -H "api-key: <your-api-key>" \
  -H "Content-Type: application/json" \
  -d '{"optimizer_config": {"default_segment_number": 2}}'
```

### Issue 3: No Quantization Configured

`quantization_config` is `null`. For 768-dimensional vectors, each float32 vector consumes 3,072 bytes. With scalar int8 quantization, that drops to 768 bytes (4x compression), and distance computation becomes faster because it operates on int8 values.

**Fix:** Enable scalar quantization with `always_ram: true`:

```bash
curl -X PUT "https://41933e38-7320-4675-b795-ffa6a7ed86d3.us-west-2-0.aws.cloud.qdrant.io:6333/collections/products-us" \
  -H "api-key: <your-api-key>" \
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

Note: This uses the collection update endpoint (PUT). After enabling quantization, you should also set `rescore: true` in your search `params` to maintain accuracy:

```json
{
  "vector": [...],
  "limit": 10,
  "params": {
    "quantization": {
      "rescore": true
    }
  }
}
```

### Issue 4: Large Payloads on Disk with on_disk_payload: true

The collection has `on_disk_payload: true`, meaning payload retrieval requires disk I/O. Each point carries substantial payload data:
- `description`: ~2,000 characters of repeated 'A' characters
- `full_text_content`: ~2,400 characters of repeated "Lorem ipsum"
- `tags`: array of 20 tag strings
- Plus `product_name`, `category`, `locale`, `price`

When `with_payload: true` is set in search requests (the default), Qdrant must read all of this from disk for each result. For 10 results, that is ~47KB of payload data read from disk.

**Recommendation:** If the application does not need all fields on every search, use `with_payload` selectively:

```json
{
  "vector": [...],
  "limit": 10,
  "with_payload": {
    "include": ["product_name", "category", "price"]
  }
}
```

Alternatively, if the dataset is small enough to fit in RAM, set `on_disk_payload: false`:

```bash
curl -X PATCH "https://41933e38-7320-4675-b795-ffa6a7ed86d3.us-west-2-0.aws.cloud.qdrant.io:6333/collections/products-us" \
  -H "api-key: <your-api-key>" \
  -H "Content-Type: application/json" \
  -d '{"params": {"on_disk_payload": false}}'
```

### Issue 5: Network Latency (The Likely Dominant Factor for 500ms)

Testing from our location, each HTTPS request to the cluster takes 120-200ms total, of which:
- TCP connect: ~40ms
- TLS handshake: ~40-60ms additional
- Server processing (TTFB minus connect): ~40ms
- Qdrant internal search: <0.5ms

If the application establishes a new TLS connection per request (no connection pooling), the 500ms figure is easily explained: ~200ms network + TLS overhead per request, plus application-side serialization/deserialization overhead, plus any middleware or retry logic.

**Recommendations:**
1. Ensure the application uses HTTP keep-alive / connection pooling. Most Qdrant client libraries do this by default, but verify.
2. Deploy the application in the same AWS region (us-west-2) as the Qdrant cluster. Cross-region or cross-cloud requests add 50-150ms of network latency.
3. If using the REST API directly (not a client library), switch to gRPC, which has lower per-request overhead and supports connection multiplexing.

## Payload Index Review

The collection has payload indexes on: `price` (float), `tags` (keyword), `product_name` (keyword), `description` (text with word tokenizer), `category` (keyword). This is comprehensive for filtered search. The `locale` field does NOT have an index, so if you filter by locale, that will cause a full scan.

Note: since HNSW is not built yet, the filterable HNSW subgraph links do not exist. After lowering `indexing_threshold` and triggering HNSW construction, filtered HNSW search will become available.

## Recommended Action Plan (in order)

1. **Lower indexing threshold** to trigger HNSW index construction (immediate fix for scalability)
2. **Wait for optimizer to finish** (check `optimizer_status` until it returns to `ok`)
3. **Enable scalar int8 quantization** with `always_ram: true`
4. **Verify application connection pooling** and same-region deployment
5. **Use selective payload retrieval** in search requests (only request fields you need)
6. **Add payload index on `locale`** if you filter by locale
7. **Consider setting `on_disk_payload: false`** since 500 points is tiny and fits easily in RAM

## What NOT to Change

- Do not increase `hnsw_ef` above 128 for this use case. The default (inheriting from `ef_construct: 100`) is reasonable.
- Do not add more segments. The current 7 is already too many; let the optimizer merge them.
- Do not change anything while the optimizer is actively running after step 1. Making config changes during optimization restarts the process.
- Do not put HNSW on disk. The dataset is small and latency-sensitive.

## Verification

After applying fixes, verify with:

```bash
# Check that HNSW index was built
curl -s -H "api-key: <your-api-key>" \
  "https://41933e38-7320-4675-b795-ffa6a7ed86d3.us-west-2-0.aws.cloud.qdrant.io:6333/collections/products-us" \
  | python3 -c "import sys, json; d=json.load(sys.stdin)['result']; print(f'indexed: {d[\"indexed_vectors_count\"]}, segments: {d[\"segments_count\"]}, optimizer: {d[\"optimizer_status\"]}')"

# Expected: indexed: 500, segments: 1-2, optimizer: ok
```
