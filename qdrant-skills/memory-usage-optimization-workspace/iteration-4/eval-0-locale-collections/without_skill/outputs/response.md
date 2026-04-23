# Qdrant Cluster Memory Diagnostic Report

**Cluster:** `https://94214c31-6930-4f9f-9f33-ec90c15a76c0.eu-west-2-0.aws.cloud.qdrant.io:6333`
**Qdrant version:** 1.16.3
**Total collections:** 12
**Analysis date:** 2026-03-03

---

## Cluster Overview

Single-node deployment (Qdrant Cloud, eu-west-2). The cluster holds 12 collections split into two categories: product catalogs for various locales and an embeddings archive.

```
Collections discovered:
  products-us        (500 points, 768-dim, 2 segments)
  products-en-gb     ( 50 points, 768-dim, 2 segments)
  products-de-de     ( 50 points, 768-dim, 2 segments)
  products-fr-fr     ( 50 points, 768-dim, 2 segments)
  products-es-es     ( 50 points, 768-dim, 2 segments)
  products-it-it     ( 50 points, 768-dim, 2 segments)
  products-ko-kr     ( 50 points, 768-dim, 2 segments)
  products-zh-cn     ( 50 points, 768-dim, 2 segments)
  products-pt-br     ( 50 points, 768-dim, 2 segments)
  products-nl-nl     ( 50 points, 768-dim, 2 segments)
  products-ja-jp     ( 50 points, 768-dim, 2 segments)
  embeddings-archive (200 points, 1536-dim, 2 segments)

Total points: 1,200
```

---

## Raw Configuration Summary

| Collection | Points | Vector Dim | vectors.on_disk | hnsw.on_disk | Quantization | indexed_vectors | on_disk_payload |
|---|---|---|---|---|---|---|---|
| products-us | 500 | 768 | false | false | none | 0 | true |
| products-en-gb | 50 | 768 | false | false | none | 0 | true |
| products-de-de | 50 | 768 | false | false | none | 0 | true |
| products-fr-fr | 50 | 768 | false | false | none | 0 | true |
| products-es-es | 50 | 768 | false | false | none | 0 | true |
| products-it-it | 50 | 768 | false | false | none | 0 | true |
| products-ko-kr | 50 | 768 | false | false | none | 0 | true |
| products-zh-cn | 50 | 768 | false | false | none | 0 | true |
| products-pt-br | 50 | 768 | false | false | none | 0 | true |
| products-nl-nl | 50 | 768 | false | false | none | 0 | true |
| products-ja-jp | 50 | 768 | false | false | none | 0 | true |
| embeddings-archive | 200 | 1536 | false | false | scalar int8, always_ram=false | 0 | true |

---

## Problems Identified

### Problem 1: One Collection Per Locale (Highest Impact)

The cluster runs **11 separate per-locale product collections** (`products-it-it`, `products-en-gb`, `products-de-de`, etc.), each containing only 50 points. This is the primary architectural problem driving excess memory.

**Why this causes high memory:**

Each Qdrant collection carries a fixed RAM overhead regardless of how many points it holds:
- At minimum 2 segments allocated per collection (confirmed in the data above)
- Each segment loads its own metadata structures, WAL state, and index bookkeeping
- Per-collection optimizer threads, flush timers, and WAL buffers (32 MB WAL capacity configured per collection)
- HNSW index structures are allocated per collection even when not yet built

With 11 locale collections at 50 points each, you pay full per-collection RAM overhead 11 times for data that could live in one collection filtered by the `locale` field.

**The locale field already exists.** Inspecting actual point payloads confirms both `products-us` and the locale collections already carry a `locale` field:

Sample from `products-it-it`:
```json
{"id": 0, "payload": {"product_name": "Product 0", "locale": "it-IT"}}
```

Sample from `products-us`:
```json
{
  "id": 0,
  "payload": {
    "product_name": "Product 0",
    "locale": "en-US",
    "category": "electronics",
    "price": 407.35,
    "tags": ["tag_0", ..., "tag_19"],
    "description": "AAAA...",
    "full_text_content": "Lorem ipsum..."
  }
}
```

The data model already supports a unified collection. The locale collections were simply created redundantly one per locale rather than consolidated.

---

### Problem 2: All Vectors Loaded Into RAM (`on_disk=false`)

Every collection has `vectors.on_disk=false` and `optimizer_config.memmap_threshold=null`. This forces Qdrant to load all vector data into process heap memory rather than using memory-mapped files (mmap).

**Vector RAM breakdown (float32 = 4 bytes/dim):**

```
768-dim vector:  768 * 4 = 3,072 bytes per vector
1536-dim vector: 1536 * 4 = 6,144 bytes per vector

products-us   (500 pts, 768-dim):         500 * 3072 = 1,536,000 bytes = 1.46 MB
embeddings-archive (200 pts, 1536-dim):   200 * 6144 = 1,228,800 bytes = 1.17 MB
11 locale collections (50 pts x 11):      550 * 3072 = 1,689,600 bytes = 1.61 MB

Total vector RAM (raw float32): ~4.25 MB
```

With `on_disk=true` and mmap, only the pages of vectors that are actively being searched remain in physical RAM. The OS page cache manages eviction automatically. This is especially important as the product catalog grows beyond the current 50-500 point scale.

---

### Problem 3: HNSW Graph Not on Disk

All collections have `hnsw_config.on_disk=false`. When HNSW graphs are built, they land entirely in heap RAM.

**Compounding issue:** `indexed_vectors_count=0` for every collection because `indexing_threshold=10000` (the default) but no collection has 10,000 points. This means:

- No HNSW graph has been built yet. All searches run as flat brute-force scans.
- This is acceptable at current data volumes but means the `on_disk=false` HNSW setting is a time-bomb: when data grows past 10,000 points, HNSW graphs will materialize entirely in RAM.
- For the 11 locale collections at 50 points each, HNSW will never trigger at this threshold. The setting is simply wrong for the data size.

---

### Problem 4: Bloated Payload in `products-us`

Inspecting actual points from `products-us` reveals two payload fields containing large synthetic filler data:

**`description` field:** approximately 2,000 characters of repeated `'A'` characters per point:
```
"AAAAAAAAAAAAAAAAAAAAAAAA..." (2000+ chars, every point)
```

**`full_text_content` field:** approximately 200 repetitions of "Lorem ipsum" per point:
```
"Lorem ipsum Lorem ipsum Lorem ipsum ..." (~2000 words, every point)
```

**`tags` field:** exactly 20 tags per point (`tag_0` through `tag_19`).

**Impact:**

- `products-us` has a full-text payload index on `description` (confirmed in `payload_schema`). An inverted token index is built from this content and resides in RAM. Processing 500 points of 2,000-character `AAAA` strings through a word tokenizer produces a garbage-but-RAM-consuming inverted index.
- Estimated raw payload per point: 12,000-16,000 bytes.
- For 500 points: 6-8 MB of raw payload data on disk.
- `on_disk_payload=true` is correctly set so payload bytes stay on disk, but the text index (inverted index structures) is in RAM regardless.

The `full_text_content` field is not indexed (absent from `payload_schema`) but still contributes disk I/O overhead during scans.

---

### Problem 5: Misconfigured Quantization on `embeddings-archive`

`embeddings-archive` has scalar int8 quantization configured with `always_ram=false`. However, the source vectors have `on_disk=false`, meaning the original float32 vectors are still in RAM.

The intended memory-efficient quantization pattern is the opposite:
- Source float32 vectors: `on_disk=true` (load via mmap only for rescoring)
- Quantized int8 vectors: `always_ram=true` (fast search directly from RAM at 4x smaller size)

The current configuration gives you the accuracy penalty of quantization (int8 rounding error during search) without the memory benefit (originals still occupy full float32 RAM). At 1536 dimensions this is especially costly:

```
Current:  200 pts * 1536 dims * 4 bytes = 1.17 MB in RAM (float32)
Intended: 200 pts * 1536 dims * 1 byte  = 0.29 MB in RAM (int8, always_ram=true)
Savings:  0.88 MB per 200 points - scales linearly with data
```

---

### Problem 6: No `memmap_threshold` Configured

All collections have `optimizer_config.memmap_threshold=null`. This disables the automatic segment-to-mmap promotion. Without this setting, all segments stay as in-memory structures regardless of how large they grow.

Setting `memmap_threshold` to a reasonable value (e.g., `1000`) causes Qdrant to automatically convert large segments to mmap files, letting the OS control physical RAM usage via demand paging.

---

### Problem 7: `indexing_threshold` Too High for Collection Sizes

The `indexing_threshold=10000` (default) means no HNSW graph is ever built for any current collection. While brute-force search is fine at these data sizes, the threshold should be tuned per collection:

- Locale collections (50 points): HNSW adds no value, threshold is irrelevant but should be documented.
- `products-us` (500 points): Brute-force is fine here, but HNSW would be beneficial around 1,000+ points.
- `embeddings-archive` (200 points): Same situation.

The correct approach is to lower `indexing_threshold` to 100-500 for collections expected to grow, so indexing kicks in early rather than all at once when a batch load crosses 10,000.

---

## Memory Estimate Comparison

| Scenario | Vector RAM | Notes |
|---|---|---|
| Current (float32, all in RAM) | ~4.25 MB | All 12 collections, no mmap |
| With `on_disk=true` for all vectors | OS-managed | Pages evicted when not in use |
| With int8 quantization, `always_ram=true` | ~1.06 MB | 4x reduction, quantized in RAM |
| After locale consolidation (1 collection) | Saves 10x collection overhead | Fewer segments, less bookkeeping RAM |
| Optimal (consolidation + on_disk + quantization) | Minimal | Only hot query pages in RAM |

Note: These figures cover raw vector bytes only. Per-collection bookkeeping RAM (segment metadata, WAL, optimizer state, open file descriptors) is harder to quantify without process-level `/proc/meminfo` access, but it is the dominant cost at current data volumes given how small the actual vector datasets are.

---

## Recommendations (Priority Order)

### 1. Consolidate locale collections into one `products` collection

Merge all `products-XX-XX` collections into a single collection. The `locale` field is already present in payloads.

**Step 1:** Create a keyword payload index on `locale` in the target collection:
```http
PUT /collections/products/index
{
  "field_name": "locale",
  "field_schema": "keyword"
}
```

**Step 2:** Migrate points from each locale collection (50 points each) into `products` with `upsert`.

**Step 3:** Delete the 11 separate locale collections.

**Query pattern after consolidation:**
```json
POST /collections/products/points/search
{
  "vector": [...],
  "filter": {
    "must": [{"key": "locale", "match": {"value": "it-IT"}}]
  },
  "limit": 10
}
```

Savings: 10 fewer collections, 20 fewer segments, 10x reduction in per-collection RAM overhead, simpler operations.

---

### 2. Enable on-disk vectors with `memmap_threshold`

For all collections, switch vectors to mmap mode:

```http
PATCH /collections/products-us
{
  "vectors": {"on_disk": true},
  "optimizers_config": {"memmap_threshold": 1000}
}
```

Apply this to all 12 collections. Vectors will be accessed via mmap; the OS page cache handles memory pressure automatically. For collections below the threshold (50 points), the effect is immediate.

---

### 3. Fix `embeddings-archive` quantization to the correct pattern

```http
PATCH /collections/embeddings-archive
{
  "vectors": {"on_disk": true},
  "quantization_config": {
    "scalar": {
      "type": "int8",
      "always_ram": true
    }
  }
}
```

Result: int8 quantized vectors (1,536 bytes each) serve all ANN searches from RAM. Original float32 vectors (6,144 bytes each) stay on disk and are only loaded for rescoring when `rescore=true` is requested.

---

### 4. Enable HNSW on disk for all collections

```http
PATCH /collections/products-us
{
  "hnsw_config": {"on_disk": true}
}
```

When HNSW graphs materialize (as data grows past `indexing_threshold`), they will be mmap-backed files rather than heap-allocated in-process RAM.

---

### 5. Lower `indexing_threshold` for growing collections

For collections that are expected to grow:
```http
PATCH /collections/products-us
{
  "optimizers_config": {"indexing_threshold": 200}
}
```

This ensures HNSW indexing starts earlier rather than waiting for a sudden 10,000-point threshold crossing.

For tiny collections that will stay small (the locale collections after consolidation, if kept separate), set `indexing_threshold` to a value above the collection size to explicitly keep brute-force behavior.

---

### 6. Clean up bloated payload in `products-us`

Remove the synthetic filler data that is inflating the text index and payload storage:

**Delete the text payload index on `description` if it was created for test data:**
```http
DELETE /collections/products-us/index/description
```

**Clear the filler fields from points** (replace with realistic content or remove):
```http
POST /collections/products-us/points/payload/delete
{
  "keys": ["full_text_content"],
  "filter": {"must": [{"key": "locale", "match": {"value": "en-US"}}]}
}
```

If `description` contains real product descriptions in production, keep the text index but ensure the content is realistic. The current 2,000-character `AAAA` strings are clearly synthetic.

---

## Summary

| Problem | Severity | Root Cause | Fix |
|---|---|---|---|
| 11 collections for locale variants | High | Architectural: one collection per locale | Merge into single `products` collection with locale filter |
| All vectors in RAM (`on_disk=false`) | High | Default config not overridden | Set `on_disk=true` + `memmap_threshold=1000` on all collections |
| HNSW will land in RAM when built | Medium | `hnsw_config.on_disk=false` on all collections | Set `hnsw_config.on_disk=true` |
| Wrong quantization config on `embeddings-archive` | Medium | Source vectors in RAM, quantized vectors not always in RAM | Set `vectors.on_disk=true` + `quantization.always_ram=true` |
| No `memmap_threshold` set | Medium | Default `null` disables auto mmap promotion | Set `memmap_threshold=1000` across all collections |
| Bloated synthetic payload with text index | Low | Test data left in production collection | Clean up `description` and `full_text_content` filler data |
| `indexing_threshold=10000` never triggers | Low | Default too high for current data volumes | Lower to 200-500 for collections expected to grow |

The highest-impact single change is **consolidating the 11 locale collections into one** (removes 10x fixed per-collection RAM overhead). The second most impactful change is **enabling `on_disk=true` for vectors** with a `memmap_threshold` (eliminates forced heap allocation of all vector data). The `embeddings-archive` quantization fix is a quick win that corrects a configuration inversion.
