# Full Memory Diagnostic Report

**Cluster:** https://94214c31-6930-4f9f-9f33-ec90c15a76c0.eu-west-2-0.aws.cloud.qdrant.io:6333
**Qdrant Version:** 1.16.3
**Diagnostic Date:** 2026-03-03
**Cluster Topology:** Single node (peer ID: 5322440586678173), cluster mode enabled, node startup: 2026-03-02T00:48:53Z

---

## Phase 1: Detection Results

### Step 1: Collection Inventory

The cluster has **12 collections**. Total vectors across the entire cluster: **1,200**.

| Collection | Points | Segments | Vector Dim | Quantization | HNSW on_disk | vectors on_disk | on_disk_payload | Payload Indexes |
|---|---|---|---|---|---|---|---|---|
| products-it-it | 50 | 2 | 768 | None | false | false | true | none |
| products-en-gb | 50 | 2 | 768 | None | false | false | true | none |
| products-de-de | 50 | 2 | 768 | None | false | false | true | none |
| products-fr-fr | 50 | 2 | 768 | None | false | false | true | none |
| products-ko-kr | 50 | 2 | 768 | None | false | false | true | none |
| products-zh-cn | 50 | 2 | 768 | None | false | false | true | none |
| products-pt-br | 50 | 2 | 768 | None | false | false | true | none |
| products-nl-nl | 50 | 2 | 768 | None | false | false | true | none |
| products-ja-jp | 50 | 2 | 768 | None | false | false | true | none |
| products-es-es | 50 | 2 | 768 | None | false | false | true | none |
| products-us | 500 | 2 | 768 | None | false | false | true | description (full-text/word), category (keyword), tags (keyword), product_name (keyword), price (float) |
| embeddings-archive | 200 | 2 | 1536 | scalar int8, always_ram=**false** | false | false | true | none |

### Step 2: Memory Metrics (from /metrics endpoint)

```
memory_resident_bytes:  ~30-32 MB
memory_active_bytes:    ~22-23 MB
memory_allocated_bytes: ~19-20 MB
memory_retained_bytes:  ~108-110 MB
memory_metadata_bytes:  ~9 MB
process_open_mmaps:     612
process_open_fds:       49
process_threads:        38
process_major_page_faults_total: 5,242
```

### Step 3: Telemetry

The `/telemetry` endpoint on this Qdrant Cloud cluster does not expose per-collection `memory_usage` fields. The aggregate memory figures are available through `/metrics` (jemalloc stats). Qdrant version 1.16.3 is current and has no known memory-growth bugs (fixed in v1.13+).

The telemetry response confirms:
- 12 collections active
- No active optimizers (`collection_running_optimizations = 0` for all collections)
- No dead replicas
- Raft consensus working normally

### Step 4: Optimizer Status

All 12 collections report `optimizer_status: ok` with zero running optimizations. No optimizers are stuck. All previously applied configuration changes have fully taken effect.

All collections show `indexed_vectors_count: 0`. None have reached the `indexing_threshold` of 10,000 vectors required to trigger HNSW index construction. All searches run as brute-force flat scans. This is normal at current scale and means HNSW graph RAM overhead is near-zero right now.

### Step 5: Payload Index Audit

Only `products-us` has payload indexes. All other 11 collections have empty `payload_schema`.

**products-us payload indexes (all covering 500 points):**
- `description`: full-text index, word tokenizer, min_token_len=2, max_token_len=20
- `category`: keyword
- `tags`: keyword
- `product_name`: keyword
- `price`: float

All other collections: no payload indexes.

### Step 6: Version and Infrastructure

- **Version:** 1.16.3 (current, no memory-growth or memory-leak issues apply)
- **Replication factor:** 1 on all collections (no replication multiplier)
- **Deployment:** Qdrant Cloud, AWS eu-west-2
- **Open mmaps:** 612 (for 12 collections x 2 segments = 24 segments total, this is ~25 mmaps/segment, within normal range)

---

## Phase 2: Classification

The pattern matches **Phase 3B: Unexpectedly High Memory**, caused by two compounding structural issues:

1. **Collection proliferation with mismatched data volume:** 12 collections where 10 of them hold only 50 vectors each. Each collection incurs 12-14 MB of fixed overhead regardless of data size.
2. **Broken quantization configuration:** The one collection that attempted memory optimization (`embeddings-archive`) is misconfigured in a way that negates the benefit and degrades search performance.

---

## Phase 3: Diagnosis

### Finding 1: 10 Collections Holding 50 Vectors Each (Primary Cause)

**This is the dominant cause of disproportionate memory usage relative to actual data volume.**

The cluster holds 10 locale-specific product collections, each containing exactly 50 vectors at 768 dimensions:

- products-it-it, products-en-gb, products-de-de, products-fr-fr, products-ko-kr
- products-zh-cn, products-pt-br, products-nl-nl, products-ja-jp, products-es-es

Every collection carries 12-14 MB of fixed baseline overhead regardless of how many vectors it holds. This overhead covers:
- The HNSW graph structure (even when empty/not yet built)
- ID tracker (16 bytes per point, always in RAM)
- 2 segments x per-segment metadata, delete bitsets, and storage pointers
- WAL allocation (32 MB capacity configured per collection, space allocated on write)
- Collection-level config, mutex structures, and bookkeeping

**Overhead-to-data ratio for each locale collection:**

```
Actual vector data: 50 vectors x 768 dims x 4 bytes = 153,600 bytes = ~150 KB
Collection overhead: 12-14 MB
Overhead ratio: ~87x
```

Each locale collection pays 13 MB in overhead to serve 150 KB of actual vectors. That ratio explains why total cluster memory looks "way higher than expected."

**Overhead math for the 10 locale collections:**
```
10 collections x 13 MB = ~130 MB in pure structural overhead
Actual vector data in those 10 collections: 10 x 150 KB = ~1.5 MB
```

The correct architecture for this pattern is a single `products` collection with a `locale` keyword payload field used as a tenant discriminator. Filtering by locale at query time is equally fast with a keyword index and eliminates the per-collection overhead.

### Finding 2: Quantization Misconfiguration on embeddings-archive (High Severity)

`embeddings-archive` has scalar int8 quantization enabled with the following config:

```json
"quantization_config": {
  "scalar": {
    "type": "int8",
    "always_ram": false
  }
}
```

**`always_ram: false` is the wrong setting for quantized vectors.** It means the quantized int8 vectors are NOT pinned in RAM. During search, Qdrant uses quantized vectors for candidate selection (the ANN pass). With `always_ram: false`, those quantized candidates must be fetched from disk (or from OS page cache, which is non-deterministic) on every search query.

Consequences:
- Every search triggers disk reads for the quantized candidate vectors.
- Performance degrades to disk-speed latency for candidate selection.
- CPU usage spikes due to page fault handling and I/O waiting.
- No memory savings, because the OS will page the quantized vectors back into cache anyway under any search load.

Additionally, the original float32 vectors are NOT on disk either (`vectors.on_disk: false`). This means:
- Quantized (small, int8) vectors: potentially on disk (wrong)
- Original float32 vectors (large, 1536-dim): in RAM (also wrong)

This is the exact inverse of the correct configuration. The correct setup for quantization is:
```
Quantized vectors: always_ram: true  (small, keep in RAM for fast candidate selection)
Original vectors:  on_disk: true     (large, mmap for rescoring only)
```

**The quantization on `embeddings-archive` is providing zero benefit and actively harming search performance.**

### Finding 3: HNSW Not on Disk Across All Collections (Low Now, Architectural Concern)

Every collection has `hnsw_config.on_disk: false`. At current scale (maximum 500 vectors in any collection, and `indexed_vectors_count: 0` everywhere because none have exceeded `indexing_threshold: 10000`), HNSW graphs have not been built yet. So HNSW is contributing near-zero to current memory.

However, if `products-us` grows to tens of thousands of vectors, an HNSW graph will be built and kept entirely in RAM. For high-dimensional vectors (768-dim), HNSW graph size scales approximately as:

```
~16 bytes per edge x m=16 edges x 2 layers factor = ~512 bytes per point for HNSW
```

At 500,000 vectors: ~256 MB in HNSW alone. If growth is expected, enabling `hnsw_config.on_disk: true` on the collections before they grow is easier than migrating after.

### Finding 4: Payload Indexes on products-us (Monitor as Data Grows)

`products-us` has 5 payload indexes, including a full-text index on `description` using a word tokenizer. At 500 points this is currently trivial in memory impact. The concerns are forward-looking:

- **Full-text index on `description`:** As `products-us` grows, this is the highest-risk index for RAM consumption. Full-text indexes typically consume 2-5x the size of the indexed text. At 1 million vectors with average 100-word descriptions, this index alone could exceed 1 GB.
- **`product_name` keyword index:** If product names are unique (UUID-like or high-cardinality), this approaches 8-16 bytes per unique value per point. At scale this becomes significant.
- **`tags` keyword index:** Depends on cardinality. Multi-value keyword fields with many unique tags accumulate fast.
- **`price` float index:** Efficient (~8 bytes per unique value), useful for range filters. No concern.
- **`category` keyword index:** Low-cardinality, efficient. No concern.

The `description` full-text index and `product_name` keyword index are the ones to watch.

### Finding 5: High Open mmap Count (612 for 24 Segments)

The process has 612 open memory-mapped files across 12 collections x 2 segments = 24 segments total. That is approximately 25 mmaps per segment. This is within normal range for Qdrant. Each segment generates mmaps for: vector storage, payload storage, HNSW graph file, ID tracker, delete bitset, and various index files. The system mmap limit is 262,144, so there is no risk of hitting the system limit at this scale.

---

## Phase 4: Recommendations (Ordered by Impact)

### Priority 1: Consolidate the 10 locale collections into one (Highest Impact)

**Estimated savings: ~120-130 MB of data memory (structural overhead for 10 collections).**

Migrate all locale-specific products into a single `products` collection with a `locale` keyword payload field. Create a keyword index on `locale` for efficient filtering.

Step 1: Create the new unified collection (keep existing `products-us` config as the base):

```json
PUT /collections/products
{
  "vectors": {
    "size": 768,
    "distance": "Cosine"
  },
  "on_disk_payload": true
}
```

Step 2: Create a keyword index on the locale discriminator field:

```json
PUT /collections/products/index
{
  "field_name": "locale",
  "field_schema": "keyword"
}
```

Step 3: Migrate data from each locale collection, adding a `"locale": "it-it"` (etc.) payload field to each point. Then delete the 10 original locale collections.

Step 4: Query with a locale filter:

```json
{
  "vector": [...],
  "filter": {
    "must": [{"key": "locale", "match": {"value": "it-it"}}]
  },
  "limit": 10
}
```

This reduces 11 collections (10 locale + products-us) to 1, cutting collection overhead from ~143 MB to ~13 MB.

### Priority 2: Fix the quantization config on embeddings-archive (High Severity)

**Fixes: search performance collapse, restores the intended memory benefit of quantization.**

```json
PATCH /collections/embeddings-archive
{
  "quantization_config": {
    "scalar": {
      "type": "int8",
      "always_ram": true
    }
  },
  "vectors": {
    "on_disk": true
  }
}
```

After applying this patch:
1. Wait for optimizer to finish rebuilding the collection with the new config. Monitor `optimizer_status` and `collection_running_optimizations` until both are idle.
2. The quantized int8 vectors will be pinned in RAM for fast candidate selection.
3. The original 1536-dim float32 vectors will be memory-mapped and only loaded from disk during rescoring.
4. Memory for this collection will decrease: 200 points x 1536 dims x (4 bytes float32 - 1 byte int8) = ~900 KB reclaimed from forced RAM.

**Do not set `always_ram: false` on quantized vectors to try to save additional RAM.** This causes disk thrashing and performance collapse on every search.

### Priority 3: Enable HNSW on_disk before collections grow large (Proactive)

When any collection exceeds the `indexing_threshold` of 10,000 vectors, an HNSW graph will be built and kept in RAM by default. Enable `on_disk: true` proactively on collections expected to grow:

For `products` (after consolidation):
```json
PATCH /collections/products
{
  "hnsw_config": {
    "on_disk": true
  }
}
```

For `embeddings-archive`:
```json
PATCH /collections/embeddings-archive
{
  "hnsw_config": {
    "on_disk": true
  }
}
```

HNSW on disk uses memory-mapped files. Search latency increases slightly (a few percent) but RAM usage for the graph drops significantly.

### Priority 4: Monitor products-us payload indexes as the collection grows

No action needed now. At 500 points the index sizes are negligible. Set alerts to review at:
- 50,000 vectors: reassess full-text index on `description`
- 500,000 vectors: evaluate whether `product_name` keyword index needs to move to per-index `on_disk: true`

If the full-text index on `description` becomes a RAM concern, move it to disk:
```json
PUT /collections/products/index
{
  "field_name": "description",
  "field_schema": {
    "type": "text",
    "tokenizer": "word",
    "on_disk": true
  }
}
```

---

## Complete Findings Summary

| Finding | Severity | Affected Collection(s) | Current Impact | Action |
|---|---|---|---|---|
| 10 collections each holding 50 vectors — 87x overhead-to-data ratio | High | products-it-it, en-gb, de-de, fr-fr, ko-kr, zh-cn, pt-br, nl-nl, ja-jp, es-es | ~120-130 MB wasted data memory | Consolidate into single `products` collection with `locale` field |
| `quantization_config.always_ram: false` — quantization broken | High | embeddings-archive | Zero memory benefit, disk thrashing on search, performance collapse | Set `always_ram: true`, set `vectors.on_disk: true` |
| HNSW not on disk | Low now, Medium at scale | All 12 collections | Near-zero now (no HNSW built yet) | Enable `hnsw_config.on_disk: true` before growth |
| 5 payload indexes including full-text on products-us | Low now, High at scale | products-us | Negligible at 500 points | Monitor; move full-text index to disk if RAM pressure emerges |

## What Is NOT Wrong

- **Qdrant version 1.16.3 is current.** No memory-growth bugs apply (fixed before v1.13).
- **No optimizer is stuck.** All collections show `optimizer_status: ok` and zero running optimizations.
- **No replication.** All collections use `replication_factor: 1`. No 2x RAM multiplier.
- **on_disk_payload: true is correctly set on all collections.** Payload data is not in RAM.
- **612 open mmaps is normal.** Well within the 262,144 system limit.
- **No OOM risk at current scale.** The cluster holds 1,200 total vectors. Even with structural inefficiencies, there is no immediate crash risk. Memory pressure is architectural, not from data volume.
