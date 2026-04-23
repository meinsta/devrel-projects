# Qdrant Cluster Memory Diagnostic Report

**Cluster:** `94214c31-6930-4f9f-9f33-ec90c15a76c0.eu-west-2-0.aws.cloud.qdrant.io:6333`
**Qdrant Version:** 1.16.3
**Date:** 2026-03-03
**Cluster topology:** Single node (peer ID: 5322440586678173), consensus leader

---

## Summary

The cluster has 12 collections with 1,200 total vectors. Memory usage is elevated far beyond what the actual data size justifies. Several structural and configuration issues are compounding to cause this.

**Current memory (from `/metrics`):**
- Resident (RSS): 25.1 MB
- Active: 17.4 MB
- Retained (virtual): 113.1 MB
- Open mmaps: **573** (extremely high for 1,200 vectors)
- Major page faults: 5,242

---

## Collections Inventory

| Collection | Points | Vector Dim | Quantization | on_disk vectors | on_disk payload | Indexed Vectors | Payload Indexes |
|---|---|---|---|---|---|---|---|
| products-us | 500 | 768 | None | false | true | 0 | 5 (keyword, text, float) |
| embeddings-archive | 200 | 1536 | int8 (scalar) | false | true | 0 | 0 |
| products-en-gb | 50 | 768 | None | false | true | 0 | 0 |
| products-it-it | 50 | 768 | None | false | true | 0 | 0 |
| products-de-de | 50 | 768 | None | false | true | 0 | 0 |
| products-fr-fr | 50 | 768 | None | false | true | 0 | 0 |
| products-ko-kr | 50 | 768 | None | false | true | 0 | 0 |
| products-zh-cn | 50 | 768 | None | false | true | 0 | 0 |
| products-pt-br | 50 | 768 | None | false | true | 0 | 0 |
| products-nl-nl | 50 | 768 | None | false | true | 0 | 0 |
| products-ja-jp | 50 | 768 | None | false | true | 0 | 0 |
| products-es-es | 50 | 768 | None | false | true | 0 | 0 |

---

## Issues Found

### Issue 1: All vectors are loaded into RAM (no `on_disk` vector storage)

**Severity: High**

Every collection has `"on_disk": false` for vectors. This means all raw float32 vectors are memory-mapped and kept in RAM. For collections this small, this is not catastrophic in bytes, but combined with the HNSW graph also being in RAM (`hnsw_config.on_disk: false`), the full index structure for every collection occupies active memory pages.

The 573 open mmaps signal that Qdrant has memory-mapped files for all segments across all 12 collections (vectors, HNSW graphs, payload storage), and the OS has them resident.

**Fix:** For read-heavy workloads where latency can tolerate occasional disk access, enable `on_disk: true` for vector storage. Alternatively, enable `on_disk: true` on the HNSW config to offload the graph traversal index to disk.

```json
PATCH /collections/{name}
{
  "vectors": {
    "on_disk": true
  },
  "hnsw_config": {
    "on_disk": true
  }
}
```

---

### Issue 2: No quantization on 10 of 12 collections

**Severity: High**

Only `embeddings-archive` has quantization (`int8` scalar). All 10 `products-*` locale collections and `products-us` have `quantization_config: null`. This means vectors are stored as 32-bit floats.

For `products-us` (768-dim, 500 points): raw vector storage = 500 x 768 x 4 bytes = 1.5 MB in RAM.

For all products locale collections (768-dim, 50 points each, 10 collections): 10 x 50 x 768 x 4 = 1.5 MB total.

With int8 scalar quantization, memory drops 4x. With binary quantization (if model supports it), memory drops 32x.

**Observed inconsistency:** `embeddings-archive` has the larger 1536-dim vectors but was given quantization. The high-traffic `products-us` (500 points, 5 payload indexes, the most active collection by IO metrics) has no quantization at all. This is backwards.

**Fix:** Add scalar int8 quantization to all products collections:

```json
PATCH /collections/{name}
{
  "quantization_config": {
    "scalar": {
      "type": "int8",
      "always_ram": false
    }
  }
}
```

---

### Issue 3: `indexed_vectors_count: 0` across all collections despite points existing

**Severity: High**

Every collection reports `indexed_vectors_count: 0` even though points exist (50 to 500 per collection). This means the HNSW index has not been built for any collection. Qdrant falls back to full brute-force scan for every search query.

The `indexing_threshold` is set to `10000` (default) across all collections. Since no collection has more than 500 points, the optimizer never triggers HNSW construction. The vectors are loaded into RAM as raw flat storage but the HNSW graph is not built.

However, the segments are still fully mmap'd into the process. You are paying the RAM cost of having vectors resident without getting the benefit of ANN indexing. At current scale this may not appear as a problem, but when collections grow past 10,000 points, search will degrade suddenly.

**Fix:** Lower `indexing_threshold` to a value appropriate for the current collection sizes, or accept that collections this small will use flat search (which is fine at 50-500 points and actually saves HNSW graph memory):

```json
PATCH /collections/{name}
{
  "optimizer_config": {
    "indexing_threshold": 500
  }
}
```

Or, leave it high (10000) if these collections are expected to grow and accept flat scan for now. Do not lower the threshold without understanding the trade-off: building HNSW on 50 points consumes more RAM than flat search.

---

### Issue 4: Bloated payload in `products-us` (large description and full_text_content fields)

**Severity: High**

Inspecting sampled points from `products-us`, each point carries:

- `description`: a string of ~2500 `A` characters (appears to be synthetic/test data padding)
- `full_text_content`: ~200 repetitions of "Lorem ipsum" (approximately 4,000 characters per point)
- `tags`: 20 tags per point (`tag_0` through `tag_19`)

At 500 points, the payload alone is enormous:
- `description`: ~2,500 bytes x 500 = 1.25 MB raw
- `full_text_content`: ~4,000 bytes x 500 = 2.0 MB raw
- `tags` array (20 entries x ~7 bytes): ~70 bytes x 500 = 35 KB

Total estimated payload for `products-us`: approximately 3.3 MB stored on disk (on_disk_payload: true), but the payload index structures for the 5 indexed fields (`product_name`, `description`, `category`, `price`, `tags`) must be built in RAM.

The `payload_index_io_write` metric shows 101,887 bytes written to payload indexes and 138,790 bytes written to payload storage for `products-us` alone, orders of magnitude more than any other collection. The text index on `description` (a 2,500-character field of repeated characters) is pathological for an inverted index: a word tokenizer on `"AAAA...AAAA"` will index the whole string as a single giant token, consuming index memory with zero search utility.

**Fix:**
1. Do not index the `description` field with a full-text index if its content is not searchable text. Remove the text index or store it as a non-indexed payload field.
2. If `full_text_content` is not being searched with Qdrant's full-text search, do not store it in Qdrant payload. Move it to an external store (Postgres, S3) and retrieve by ID.
3. Reduce `tags` array from 20 items to the actual tags used in filtering.

---

### Issue 5: Collection proliferation - 10 locale-specific collections with identical schema

**Severity: Medium**

There are 10 locale-specific `products-{locale}` collections (en-gb, it-it, de-de, fr-fr, ko-kr, zh-cn, pt-br, nl-nl, ja-jp, es-es), each with only 50 points and identical configurations. Each collection instantiates its own:

- Separate mmap'd segment files
- Separate WAL (32 MB capacity each = 320 MB WAL capacity allocated across locale collections)
- Separate HNSW config overhead
- Separate optimizer state

This is 10 x the per-collection fixed overhead for 500 total points that could fit in a single collection with a `locale` payload filter.

Each locale collection has `on_disk_payload: true` but the payload schema is empty (no indexes defined), meaning the `locale` field stored in payload is not indexed. If queries filter by locale, those filters run as full payload scans.

The WAL configuration deserves attention: `wal_capacity_mb: 32` and `wal_retain_closed: 1` means each collection retains up to 32 MB of WAL on disk even when segments are flushed. Across 12 collections this is up to 384 MB of WAL capacity on disk.

**Fix:** Consolidate locale-specific collections into a single `products` collection with a `locale` keyword payload field, and add a payload index on `locale` for efficient filtering:

```json
PUT /collections/products/index
{
  "field_name": "locale",
  "field_schema": "keyword"
}
```

This reduces per-collection overhead from 12 sets to 1 and eliminates the mmap fragmentation from 12 separate segment groups.

---

### Issue 6: `embeddings-archive` - quantization configured with `always_ram: false` but no `on_disk` vectors

**Severity: Medium**

`embeddings-archive` has scalar int8 quantization with `always_ram: false`. This is correct in intent: quantized vectors can be swapped to disk and original float32 vectors used only for rescoring. However, the collection also has `on_disk: false` for the base vectors. This means:

- The original 1536-dim float32 vectors are in RAM (200 x 1536 x 4 = 1.17 MB)
- The int8 quantized vectors are eligible to be on disk, but since HNSW is not built (indexed_vectors_count: 0), no ANN search happens, and quantization provides zero benefit

The quantization overhead adds the quantized copy alongside the float32 originals, consuming additional storage with no query performance gain at current scale.

**Fix:** Either build the HNSW index (lower `indexing_threshold` to below 200), or remove quantization until the collection is large enough that ANN indexing is triggered. Setting `always_ram: false` with unbuilt HNSW is a no-op that adds configuration complexity.

---

### Issue 7: HNSW `m: 16` on tiny collections

**Severity: Low**

All collections use `m: 16` (the default). For collections with 50 points, an HNSW graph with m=16 means each node has up to 32 connections (2*m at level 0). At 50 points, the full graph is smaller than the HNSW overhead itself. If the indexing_threshold were ever lowered, building HNSW on 50 points with m=16 would waste memory relative to flat search.

Since HNSW is not currently built (see Issue 3), this is latent. But if collection sizes remain small (under ~1,000 points), consider either leaving `indexing_threshold` high to keep flat search, or using `m: 0` equivalent to disable HNSW.

---

### Issue 8: No payload indexes on locale collections

**Severity: Low**

The 10 locale-specific `products-{locale}` collections have empty `payload_schema` (no indexed fields). If any application queries these collections with payload filters (e.g., filtering by product category, price range, tags), those filters execute as unindexed full payload scans.

Compare to `products-us` which has 5 payload indexes (product_name, description, category, price, tags). The locale collections appear to be incomplete copies of the US product data with only `product_name` and `locale` in their payload, suggesting they were provisioned as stubs.

---

## Memory Usage Breakdown

### Actual vector data size (theoretical minimum):

| Collection | Points | Dim | Float32 MB | int8 MB |
|---|---|---|---|---|
| products-us | 500 | 768 | 1.46 | 0.37 |
| embeddings-archive | 200 | 1536 | 1.17 | 0.29 |
| 10 locale products | 500 total | 768 | 1.46 | 0.37 |
| **Total** | **1200** | | **4.09 MB** | **1.02 MB** |

### Why actual RSS (25 MB) is 6x the theoretical minimum:

1. Per-collection fixed overhead (WAL state, optimizer state, segment metadata): ~12 collections x ~0.5 MB = ~6 MB
2. 573 open mmaps from segment files (each mmap has overhead in kernel page tables)
3. Payload storage for `products-us` with bloated description/full_text_content fields (~3.3 MB)
4. In-memory payload indexes for `products-us` (5 indexes on 500 points)
5. jemalloc allocator metadata: 8.2 MB (shown in metrics as `memory_metadata_bytes`)
6. HNSW config structures allocated even for unbuilt indexes

---

## Prioritized Recommendations

1. **Consolidate locale collections into one** with a `locale` keyword field and payload index. Eliminates 10x per-collection fixed RAM overhead and reduces mmap count from 573 to approximately 50.

2. **Enable `on_disk: true` for vectors** on all collections. At 1,200 total vectors, RAM is not needed for these workloads. Vectors will be demand-paged from disk when searched.

3. **Add scalar int8 quantization to `products-us`** (the largest and most active collection). This halves vector RAM for the biggest collection and enables faster ANN once the HNSW index is built.

4. **Remove or truncate the `description` and `full_text_content` payload fields** from `products-us` points, or stop indexing `description` as a text field. The current content is padded test data that bloats payload storage and inverted index structures.

5. **Remove `tags` bloat**: 20 tags per point with generic names (`tag_0` through `tag_19`) has no real filtering utility. Reduce to actual meaningful tags.

6. **Reconsider quantization on `embeddings-archive`**: with only 200 points and no HNSW index built, the int8 quantization adds a second copy of vector data with no search benefit. Either lower `indexing_threshold` to 200 to actually use quantization during ANN search, or remove it until the collection grows.

7. **Lower WAL retention**: `wal_retain_closed: 1` retains one closed WAL segment per collection. With 12 collections at 32 MB capacity each, peak WAL footprint on disk can reach 384 MB. Consider reducing `wal_capacity_mb` to 8 MB for small collections.

---

## Raw Config Reference (products-us, the most problematic collection)

```json
{
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
    "on_disk": false
  },
  "optimizer_config": {
    "indexing_threshold": 10000,
    "memmap_threshold": null
  },
  "quantization_config": null,
  "payload_schema": {
    "product_name": {"data_type": "keyword"},
    "description": {"data_type": "text", "params": {"tokenizer": "word"}},
    "category": {"data_type": "keyword"},
    "price": {"data_type": "float"},
    "tags": {"data_type": "keyword"}
  }
}
```

Every single one of the bolded config values above is contributing to elevated memory usage.
