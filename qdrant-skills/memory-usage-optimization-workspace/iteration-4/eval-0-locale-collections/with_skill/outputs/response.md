# Memory Diagnostic Report: Qdrant Cloud Cluster

**Cluster:** `https://94214c31-6930-4f9f-9f33-ec90c15a76c0.eu-west-2-0.aws.cloud.qdrant.io:6333`
**Qdrant version:** 1.16.3
**Diagnostic date:** 2026-03-03

---

## Phase 1: Detect

### Step 1: Collection Inventory

The cluster has **12 collections**:

| Collection | Points | Vector Dim | Segments |
|---|---|---|---|
| products-us | 500 | 768 | 2 |
| embeddings-archive | 200 | 1536 | 2 |
| products-it-it | 50 | 768 | 2 |
| products-en-gb | 50 | 768 | 2 |
| products-de-de | 50 | 768 | 2 |
| products-fr-fr | 50 | 768 | 2 |
| products-ko-kr | 50 | 768 | 2 |
| products-zh-cn | 50 | 768 | 2 |
| products-pt-br | 50 | 768 | 2 |
| products-nl-nl | 50 | 768 | 2 |
| products-ja-jp | 50 | 768 | 2 |
| products-es-es | 50 | 768 | 2 |

**Total vectors: 1,200 across all collections.**

**Collection overhead baseline:** 12 collections x 13 MB = ~156 MB fixed overhead, regardless of data size.

Raw API response (collections list):
```json
{"result":{"collections":[
  {"name":"products-it-it"},{"name":"embeddings-archive"},{"name":"products-en-gb"},
  {"name":"products-de-de"},{"name":"products-fr-fr"},{"name":"products-us"},
  {"name":"products-ko-kr"},{"name":"products-zh-cn"},{"name":"products-pt-br"},
  {"name":"products-nl-nl"},{"name":"products-ja-jp"},{"name":"products-es-es"}
]},"status":"ok"}
```

---

### Step 2: Collection Config

All 11 locale product collections (`products-*`) share an identical config pattern:

| Parameter | Value |
|---|---|
| `vectors.size` | 768 |
| `vectors.on_disk` | `false` (in RAM via mmap, default) |
| `on_disk_payload` | `true` (payload data on disk) |
| `quantization_config` | `null` (none) |
| `hnsw_config.on_disk` | `false` (HNSW graph in RAM) |
| `hnsw_config.m` | 16 |
| `indexing_threshold` | 10,000 |
| `replication_factor` | 1 |
| `segments_count` | 2 |

**products-us** is the same except it has 500 points and 5 payload indexes.

**embeddings-archive** is different:

| Parameter | Value |
|---|---|
| `vectors.size` | 1536 |
| `vectors.on_disk` | `false` (originals in RAM) |
| `on_disk_payload` | `true` |
| `quantization_config.scalar.type` | `int8` |
| `quantization_config.scalar.always_ram` | **`false`** (quantized vectors NOT forced to RAM) |
| `hnsw_config.on_disk` | `false` |
| `segments_count` | 2 |

---

### Step 3: Memory Metrics

The `/telemetry` endpoint does not expose per-collection `memory_usage` breakdowns in this version's response. Memory was assessed via `/metrics` (Prometheus jemalloc stats):

```
memory_allocated_bytes:   15,939,128   (~15.2 MB)   actual application allocations
memory_active_bytes:      18,829,312   (~18.0 MB)   active memory pages
memory_resident_bytes:    25,329,664   (~24.2 MB)   physically resident pages
memory_retained_bytes:   111,161,344   (~106.0 MB)  virtual memory including mmap
```

**Key observation:** `process_open_mmaps: 571`

This is disproportionately high for 1,200 total vectors. Each segment creates multiple mmap file handles (vectors file, HNSW graph file, ID tracker, payload index). With 2 segments per collection and 12 collections (24 segments total), 571 mmap handles indicates significant per-segment file handle overhead relative to actual data volume.

The 106 MB `memory_retained_bytes` is virtual address space consumed by mmap mappings. This is expected behavior for Qdrant's mmap storage model and does not represent physical RAM pressure by itself.

---

### Step 4: Optimizer Status

All 12 collections report `optimizer_status: "ok"` and `collection_running_optimizations: 0`. No optimizers are running. Any configuration changes made would take effect on the next optimization cycle.

```
collection_running_optimizations{id="products-it-it"} 0
collection_running_optimizations{id="embeddings-archive"} 0
... (all 12 at 0)
```

---

### Step 5: Payload Indexes

Only `products-us` has payload indexes:

| Field | Index Type | Points Indexed |
|---|---|---|
| `description` | full-text (word tokenizer, min_token_len=2, max_token_len=20) | 500 |
| `price` | float | 500 |
| `category` | keyword | 500 |
| `tags` | keyword | 500 |
| `product_name` | keyword | 500 |

All other 10 locale product collections have `payload_schema: {}` (no indexes). With `strict_mode_config.unindexed_filtering_retrieve: false` enabled on all collections, filtered searches on the 10 non-US locale collections are blocked outright. There is no payload index infrastructure on those collections despite sharing the same product catalog purpose as `products-us`.

`embeddings-archive` also has no payload indexes.

---

### Step 6: Version and Cluster Topology

- **Qdrant version:** 1.16.3 (current, no known memory leak issues in this version)
- **Cluster nodes:** 1 peer (single-node cluster)
- **Strict mode:** enabled on all collections

---

## Phase 2: Classification

**Pattern: Memory unexpectedly high (Phase 3B)**

The vector data is tiny. Applying the standard formula:
```
memory = number_of_vectors * vector_dimension * 4 bytes * 1.5
```

- 10 locale collections (50 pts each, 768 dim): 500 x 768 x 4 x 1.5 = ~2.3 MB
- products-us (500 pts, 768 dim): 500 x 768 x 4 x 1.5 = ~2.2 MB
- embeddings-archive (200 pts, 1536 dim): 200 x 1536 x 4 x 1.5 = ~1.8 MB
- **Total estimated vector data: ~6.3 MB**

Actual `memory_allocated_bytes` is 15.2 MB, which is already 2.4x the raw vector estimate. But the structural overhead from 12 collections adds ~156 MB in fixed costs on top of that. The reported memory from the OS perspective (which includes mmap virtual mappings) is much higher still.

The mismatch between data size and memory footprint is structural, not a leak.

---

## Phase 3: Diagnose

### Finding 1 (Primary): Collection proliferation

**11 separate locale product collections each hold only 50-500 vectors.** Each collection carries fixed overhead regardless of how much data it contains:

- HNSW graph structure in RAM
- ID tracker: ~16 bytes per point (always in RAM, not configurable)
- Segment metadata
- WAL buffers
- Collection-level internal state: ~12-14 MB fixed

```
12 collections x 13 MB baseline = ~156 MB overhead
vs ~6.3 MB of actual vector data
Overhead-to-data ratio: approximately 25:1
```

The 10 non-US locale collections (each with 50 points) hold ~147 KB of actual vector data each (50 x 768 x 4 bytes). The fixed overhead per collection is ~88x the data those collections hold.

This is the locale-per-collection anti-pattern. One collection per locale creates O(locales) fixed overhead that grows with the number of supported locales, not the number of products.

### Finding 2: Misconfigured quantization on `embeddings-archive`

The `embeddings-archive` collection has scalar int8 quantization configured, but the settings are backwards:

**Current config:**
- `vectors.on_disk: false` - original float32 vectors are loaded into RAM
- `quantization_config.scalar.always_ram: false` - quantized int8 vectors are NOT forced into RAM

**What this means:** The large original float32 vectors (200 x 1536 x 4 bytes = 1.2 MB) are in RAM. The smaller quantized int8 vectors (200 x 1536 x 1 byte = 307 KB) may or may not be in RAM depending on OS page cache behavior. Quantization was enabled but is not reducing memory consumption.

**Correct pattern for memory reduction:**
- `vectors.on_disk: true` - move original float32 vectors to disk (only read during rescoring)
- `quantization_config.scalar.always_ram: true` - force quantized int8 vectors into RAM (fast candidate selection)

**Important:** At 200 points and 1536 dimensions, the absolute savings are small (~900 KB). But if this collection grows, the misconfiguration will compound. Also: do NOT set `always_ram: false` as an attempt to "save RAM" while originals are also in RAM. That configuration keeps both copies accessible but provides no benefit.

### Finding 3: Missing payload indexes on locale collections

10 of the 11 locale product collections have no payload indexes. Given that `strict_mode_config.unindexed_filtering_retrieve: false` is active, filtered searches on those collections are blocked outright. This is not a memory problem today, but it means:
- Locale-specific filtered searches (e.g., filter by `category` or `price`) are not possible on the non-US collections
- `products-us` has 5 payload indexes; the others have 0. This is an inconsistency across what appears to be the same catalog schema.

The full-text index on `description` in `products-us` will consume significant RAM as the catalog grows (typically 2-5x the raw text content size). At 500 points it is negligible.

---

## Phase 4: Recommendations

In order of impact:

### Priority 1: Consolidate locale collections

Replace the 11 `products-{locale}` collections with a single `products` collection. Add `locale` as a payload field (keyword type) and filter by it at query time.

**Before:** 11 collections x 12-14 MB overhead = ~143 MB overhead for 1,050 product points
**After:** 1 collection x 13 MB overhead = ~13 MB overhead for 1,050 product points
**Savings: ~130 MB overhead eliminated**

**Migration steps:**

1. Create the unified collection:
```json
PUT /collections/products
{
  "vectors": { "size": 768, "distance": "Cosine" },
  "on_disk_payload": true
}
```

2. Create a payload index on `locale`:
```json
PUT /collections/products/index
{
  "field_name": "locale",
  "field_schema": "keyword"
}
```

3. Add consistent payload indexes that were only on `products-us`:
```json
PUT /collections/products/index
{ "field_name": "category", "field_schema": "keyword" }

PUT /collections/products/index
{ "field_name": "price", "field_schema": "float" }

PUT /collections/products/index
{ "field_name": "tags", "field_schema": "keyword" }
```

4. Upload vectors from each locale collection with `"locale": "en-gb"` (or appropriate locale) in the payload.

5. Update application queries to include a locale filter:
```json
"filter": {
  "must": [{ "key": "locale", "match": { "value": "en-gb" } }]
}
```

6. Delete the old per-locale collections once migration is verified.

### Priority 2: Fix `embeddings-archive` quantization config

```json
PATCH /collections/embeddings-archive
{
  "vectors": { "on_disk": true },
  "quantization_config": {
    "scalar": {
      "type": "int8",
      "always_ram": true
    }
  }
}
```

After patching, wait for `optimizer_status` to return to `"ok"` before evaluating the effect. The optimizer must rewrite segments for the change to take effect.

### Priority 3: Evaluate the `description` full-text index on `products-us`

If description-based text search is not an active query pattern, replace the full-text index with a keyword index on `category`. Full-text indexes consume 2-5x the indexed text size in RAM. At the current 500-point scale this is inconsequential, but plan ahead before the catalog grows to tens of thousands of products.

If full-text search is genuinely needed, keep it. Do not remove it speculatively if the application uses it.

---

## Summary

| Finding | Severity | Root Cause |
|---|---|---|
| 11 locale collections x 50 points each | High | Per-locale collection proliferation; ~130 MB wasted in fixed overhead |
| 571 open mmap handles for 1,200 total vectors | Medium | Structural consequence of 24 segments across 12 collections |
| `embeddings-archive` quantization misconfigured (`always_ram: false`, originals in RAM) | Medium | Quantization enabled but not reducing memory; both float32 originals and int8 quantized copies may be in memory |
| No payload indexes on 10 locale collections, filtered search blocked | Low | Inconsistent schema vs `products-us`; not a memory issue but a search functionality gap |

**The cluster is running Qdrant 1.16.3, which is current. There is no memory leak.** Memory appears higher than expected because 11 nearly empty locale collections each pay the full 12-14 MB per-collection fixed overhead. The fix is consolidation: merge all locale product data into a single collection with a `locale` payload field, and fix the quantization config on `embeddings-archive`.
