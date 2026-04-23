# Search Latency Diagnostic: products-us Collection

## Cluster Details

- **Qdrant version:** 1.16.3
- **Cluster URL:** `https://41933e38-7320-4675-b795-ffa6a7ed86d3.us-west-2-0.aws.cloud.qdrant.io:6333`
- **Collection:** `products-us`
- **Points count:** 500
- **Vector dimension:** 768 (Cosine distance)
- **Segments count:** 7
- **Indexed vectors count:** 0
- **Optimizer status:** ok (not currently running)
- **Quantization:** None
- **On-disk payload:** true

## Phase 1: Detection Summary

| Check | Finding |
|---|---|
| Collection config | 768-dim Cosine vectors, no quantization, HNSW m=16, ef_construct=100 |
| Payload indexes | 5 fields indexed: description (text), category (keyword), price (float), product_name (keyword), tags (keyword) |
| Optimizer status | ok, no active optimizations |
| Indexed vectors | **0 out of 500** (critical finding) |
| Segments | **7 segments for 500 points** (too many) |
| On-disk payload | true, with very large payloads (~2KB+ description fields per point, plus ~2KB full_text_content) |
| Quantization | None configured |

## Phase 2: Classification

**Primary symptom:** Single query latency too high (Phase 3A).

## Phase 3: Diagnosis

### Root Causes Identified (ordered by impact)

#### 1. CRITICAL: HNSW Index Is Not Built (indexed_vectors_count = 0)

This is the primary root cause. The collection has `indexing_threshold: 10000` but only 500 points. Since the point count (500) is below the indexing threshold (10,000), Qdrant never builds the HNSW graph index. All searches are performed as **brute-force scans** across all 7 segments.

With 500 points, brute-force is actually fast (sub-millisecond internally), so the 500ms the customer is reporting is very likely dominated by network transfer time and payload serialization, not the search algorithm itself.

Evidence from testing:
- Qdrant internal search time WITH payload: **~0.4ms**
- Qdrant internal search time WITHOUT payload: **~0.2ms**
- Full HTTP round-trip WITH payload (10 results): **~250ms** (47KB response)
- Full HTTP round-trip WITHOUT payload: **~190ms** (0.5KB response)
- Full HTTP round-trip with selected small fields: **~170ms** (1.3KB response)

The ~190ms baseline is pure network latency from the client to Qdrant Cloud (us-west-2). The additional ~60-80ms with full payload is payload serialization and transfer of ~47KB of data (huge description and full_text_content fields).

#### 2. Massive Payload Sizes Inflate Response Transfer Time

Each point carries extremely large payload fields:
- `description`: ~2,000 characters of repeated "A" characters
- `full_text_content`: ~2,500+ characters of repeated "Lorem ipsum" text
- `tags`: array of 20 tag strings

When returning 10 results with `with_payload: true`, the response body is ~47KB. This adds meaningful transfer time on top of network latency.

#### 3. Seven Segments for 500 Points (Over-segmented)

The collection has 7 segments for just 500 points (~71 points per segment). This is excessive. Each segment adds per-segment overhead to every query. For 500 points this overhead is minor in absolute terms, but it is unnecessary.

The `default_segment_number: 0` (auto) combined with the data likely being inserted in small batches created these segments, and because the total points are below the `indexing_threshold` of 10,000, the optimizer's merge behavior does not aggressively consolidate them.

#### 4. No Quantization Configured

While not critical at 500 points (brute-force on 500 vectors is trivially fast), the absence of quantization means every distance calculation reads full float32 vectors. At scale this would matter; at 500 points it does not explain the reported 500ms.

### Where the 500ms Is Actually Coming From

If the customer is measuring 500ms end-to-end, the breakdown is approximately:

| Component | Estimated Time |
|---|---|
| Network round-trip (client to us-west-2 Qdrant Cloud) | ~150-200ms |
| TLS handshake (if not using keep-alive connections) | ~40-80ms |
| Payload serialization + transfer (47KB) | ~60-80ms |
| Qdrant internal search time | ~0.4ms |
| **Total** | **~250-360ms** |

If the customer is connecting from a distant region, not reusing connections, or retrieving full payloads, 500ms is entirely explained by network and payload overhead, not by Qdrant search performance.

## Phase 4: Recommendations (Ordered by Impact)

### 1. Stop returning full payloads in search queries

The biggest actionable win. The `description` and `full_text_content` fields are massive and probably not needed in the search response. Use `with_payload` to select only the fields needed:

```json
{
  "vector": [...],
  "limit": 10,
  "with_payload": {
    "include": ["product_name", "category", "price"]
  }
}
```

This reduces the response from ~47KB to ~1.3KB and cuts ~60-80ms from response time.

Alternatively, use `with_payload: false` and fetch payloads separately for only the top results you actually display.

### 2. Lower the indexing threshold to build the HNSW index

The `indexing_threshold` is 10,000 but you only have 500 points. The HNSW index is never built. While brute-force on 500 points is fast, building the index is good practice and will matter as the collection grows:

```bash
curl -X PATCH \
  "https://41933e38-7320-4675-b795-ffa6a7ed86d3.us-west-2-0.aws.cloud.qdrant.io:6333/collections/products-us" \
  -H "api-key: <your-api-key>" \
  -H "Content-Type: application/json" \
  -d '{
    "optimizer_config": {
      "indexing_threshold": 100
    }
  }'
```

This will trigger the optimizer to build the HNSW index and also merge the 7 segments into fewer segments. After this completes, `indexed_vectors_count` should become 500 and `segments_count` should decrease.

### 3. Use persistent connections (HTTP keep-alive)

If the customer's application creates a new connection per request, TLS handshake adds ~40-80ms each time. Ensure the HTTP client reuses connections. All Qdrant client libraries (Python, JS, Rust, Go) use connection pooling by default; this mainly applies if they are using raw HTTP/curl.

### 4. Check client-to-cluster geographic proximity

The cluster is in `us-west-2`. If the client application runs in a different region (e.g., Europe or Asia), network latency alone could be 100-300ms. Deploy the application in the same AWS region as the Qdrant Cloud cluster, or use a closer Qdrant Cloud region.

### 5. Enable scalar quantization (for future scale)

Not critical at 500 points, but recommended to set up now:

```bash
curl -X PUT \
  "https://41933e38-7320-4675-b795-ffa6a7ed86d3.us-west-2-0.aws.cloud.qdrant.io:6333/collections/products-us" \
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

This gives 4x compression and faster distance computation. With `always_ram: true`, quantized vectors stay in RAM for fast access.

## Summary

The reported 500ms latency is **not caused by slow search within Qdrant**. Qdrant's internal search time is ~0.4ms. The 500ms is dominated by:

1. **Network latency** between the client and us-west-2 Qdrant Cloud (~150-200ms)
2. **TLS handshake overhead** if connections are not reused (~40-80ms)
3. **Large payload transfer** of ~47KB per query due to massive description and full_text_content fields (~60-80ms)

The quickest fix is to stop returning the large payload fields in search results and ensure the application reuses HTTP connections. Lowering the indexing threshold is also recommended to build the HNSW index and consolidate segments, which will matter as data grows.
