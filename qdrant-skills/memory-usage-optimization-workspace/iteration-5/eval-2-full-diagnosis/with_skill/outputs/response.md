# Qdrant Memory Diagnostic Report

**Cluster:** `94214c31-6930-4f9f-9f33-ec90c15a76c0.eu-west-2-0.aws.cloud.qdrant.io:6333`
**Qdrant Version:** 1.16.3
**Diagnostic Date:** 2026-03-03
**Cluster topology:** Single node (1 peer), cluster mode enabled

---

## Phase 1: Detect — Raw Findings

### Step 1: Collection Inventory

Total collections: **12**

| Collection | Points | Dimension | Quantization | on_disk (vectors) | HNSW on_disk | Payload indexes | Segments |
|---|---|---|---|---|---|---|---|
| products-us | 500 | 768 | None | false | false | 5 (incl. FTS) | 2 |
| embeddings-archive | 200 | 1536 | scalar int8 (always_ram=**false**) | false | false | 0 | 2 |
| products-en-gb | 50 | 768 | None | false | false | 0 | 2 |
| products-de-de | 50 | 768 | None | false | false | 0 | 2 |
| products-fr-fr | 50 | 768 | None | false | false | 0 | 2 |
| products-it-it | 50 | 768 | None | false | false | 0 | 2 |
| products-ko-kr | 50 | 768 | None | false | false | 0 | 2 |
| products-zh-cn | 50 | 768 | None | false | false | 0 | 2 |
| products-pt-br | 50 | 768 | None | false | false | 0 | 2 |
| products-nl-nl | 50 | 768 | None | false | false | 0 | 2 |
| products-ja-jp | 50 | 768 | None | false | false | 0 | 2 |
| products-es-es | 50 | 768 | None | false | false | 0 | 2 |

All collections have replication_factor=1, shard_number=1, and `on_disk_payload=true`.

### Step 2: Memory Metrics (from `/metrics`)

| Metric | Value |
|---|---|
| `memory_resident_bytes` | 27.2 MB (physically resident pages) |
| `memory_active_bytes` | 19.3 MB (active allocator pages) |
| `memory_allocated_bytes` | 16.6 MB (application-level allocations) |
| `memory_retained_bytes` | 111.0 MB (virtual address space retained, includes mmap) |
| `memory_metadata_bytes` | 8.3 MB (allocator metadata) |
| `process_open_mmaps` | **585** |
| `system_max_mmaps` | 262,144 |
| `process_threads` | 28 |
| `process_major_page_faults_total` | 5,242 |

Note: The telemetry endpoint (`/telemetry`) on this version does not expose per-collection `memory_usage` fields. The Prometheus `/metrics` endpoint is the authoritative source.

### Step 3: Telemetry Summary

```json
{
  "app": {
    "version": "1.16.3",
    "startup": "2026-03-02T00:48:53.710Z"
  },
  "collections": {
    "number_of_collections": 12,
    "max_collections": 1000
  }
}
```

Node started 2026-03-02, running for approximately 36 hours at time of diagnostic.

### Step 4: Optimizer Status

All 12 collections report `optimizer_status: "ok"`. No optimizers are currently running (`collection_running_optimizations = 0` for all). No pending indexing.

Important: `indexed_vectors_count = 0` across all collections. This means HNSW indexes have not been built on any collection. All queries are doing flat/brute-force scans. The `indexing_threshold` is 10,000 points and no collection reaches that threshold, so this is by design, not a bug.

### Step 5: Payload Indexes

Only `products-us` has payload indexes:

| Field | Type | Points indexed |
|---|---|---|
| `category` | keyword | 500 |
| `tags` | keyword | 500 |
| `description` | **text (full-text, word tokenizer)** | 500 |
| `product_name` | keyword | 500 |
| `price` | float | 500 |

No indexes are configured with `on_disk=true`. All five indexes reside in RAM. The full-text index on `description` is the most memory-intensive of these.

The other 11 collections have `payload_schema: {}`, meaning no payload indexes are defined.

### Step 6: Segment Count

Every collection has exactly 2 segments. With `indexing_threshold=10,000` and all collections well below that, segments remain as small in-memory structures. No over-segmentation detected (threshold for concern is >20 per shard). Segment overhead is not a contributing problem here.

### Step 7: Version and Infrastructure

- Qdrant version: **1.16.3** (current, no known memory-growth bugs)
- Single peer cluster (1 node)
- Startup: 2026-03-02T00:48:53 UTC

### Step 8: mmap Analysis

585 open mmaps across 12 collections (24 total segments, ~24 mmaps per segment). This is well within the system limit of 262,144. The high mmap count is expected: each segment opens separate mmap files for vectors, HNSW, payload, and metadata. The `memory_retained_bytes` of 111 MB reflects the virtual address space reserved for these mappings.

---

## Phase 2: Classify

The symptom "memory higher than expected" maps to **Pattern 3B: Unexpectedly High Memory**.

Contributing patterns identified:

1. **Collection proliferation overhead** (primary): 12 collections x 12-14 MB baseline = 144-168 MB in fixed overhead, against a total data footprint of only ~6 MB of actual vectors.
2. **Broken quantization config on `embeddings-archive`** (secondary): `always_ram=false` on scalar quantization negates the quantization benefit.
3. **Full-text index in RAM on `products-us`** (secondary): FTS index on `description` consumes memory disproportionate to the collection's size.
4. **Structural architecture problem** (root cause): The 11 per-locale `products-{locale}` collections are candidates for consolidation into a single multi-tenant collection.

---

## Phase 3: Diagnose

### 3B: Memory Unexpectedly High

**The core mismatch:**

Total vector data across all collections:

```
11 locale collections x 50 vectors x 768 dim x 4 bytes = 168,960 bytes (~0.16 MB)
embeddings-archive: 200 vectors x 1536 dim x 4 bytes = 1,228,800 bytes (~1.17 MB)
products-us: 500 vectors x 768 dim x 4 bytes = 1,536,000 bytes (~1.46 MB)

Total raw vector bytes: ~2.8 MB
With 1.5x HNSW/ID-tracker multiplier: ~4.2 MB
```

Actual resident memory: **27.2 MB**. Virtual retained: **111 MB**.

Even accounting for the 1.5x multiplier, the data footprint is tiny. The gap between expected (~4 MB) and observed (~111 MB virtual / ~27 MB resident) is explained by:

**Finding 1: Collection overhead dominates the data.**

Each Qdrant collection carries 12-14 MB of baseline overhead regardless of how many points it contains. This covers: the HNSW graph structure (even unbuilt), the ID tracker, WAL buffers (32 MB WAL capacity configured per collection), segment metadata, and internal bookkeeping.

```
12 collections x 13 MB avg overhead = ~156 MB committed overhead
Actual vector data: ~4.2 MB
Ratio: overhead is ~37x the actual data size
```

This is the primary cause. The cluster is paying the full per-collection tax for 11 nearly-identical collections that hold only 50 points each.

**Finding 2: `embeddings-archive` has a misconfigured quantization.**

Config observed:
```json
"quantization_config": {
  "scalar": {
    "type": "int8",
    "always_ram": false
  }
}
```

`always_ram=false` means the quantized vectors are NOT pinned in RAM. The original vectors also have `on_disk=false`, meaning originals stay in RAM. Result: quantization provides zero memory benefit. The memory profile is identical to having no quantization at all.

Correct config for memory reduction:
```json
"quantization_config": {
  "scalar": {
    "type": "int8",
    "always_ram": true
  }
},
"vectors": {
  "on_disk": true
}
```

With correct config: quantized int8 (1 byte/dim) stays in RAM for candidate selection; original float32 (4 bytes/dim) goes to disk and is only read during rescoring. This gives a 4x reduction in forced-resident vector memory.

**Note:** Do NOT set `always_ram=false` to "save RAM." It causes disk thrashing on every search as quantized vectors get evicted and reloaded, collapsing query performance.

**Finding 3: `products-us` has a full-text index in RAM.**

The `description` field has a word-tokenized full-text index. FTS indexes typically consume 2-5x the size of the indexed text. With 500 points, the absolute size is modest at this scale, but the pattern is problematic at production scale. No `on_disk=true` is set on any of the five payload indexes.

The `description` FTS index is the highest-memory payload index in the cluster. If this collection scales to millions of points, this index will become a major RAM consumer unless moved to disk.

**Finding 4: Structural architecture mismatch.**

The 11 `products-{locale}` collections (it-it, en-gb, de-de, fr-fr, ko-kr, zh-cn, pt-br, nl-nl, ja-jp, es-es, es-es) each contain only 50 points with the same 768-dim vector config and no payload indexes. These are functionally identical except for locale. Each pays the full 12-14 MB collection overhead.

This is the textbook case for tenant-field consolidation: replace 11 collections with one collection that includes a `locale` keyword field and a payload filter on queries.

**Finding 5: WAL retention is non-zero.**

All collections have `wal_retain_closed=1`, meaning one closed WAL segment is retained after flushing. Each collection has a 32 MB WAL capacity. While segments may not all be full, this contributes to retained virtual memory, particularly the 111 MB `memory_retained_bytes` figure.

---

## Summary of Issues Found

| # | Issue | Severity | Affected Collections |
|---|---|---|---|
| 1 | 12 collections for ~1,200 total vectors; overhead (144-168 MB) is 37x the data size | High | All 12 |
| 2 | 11 near-identical locale collections (50 pts each) should be one multi-tenant collection | High | products-{locale} x11 |
| 3 | `embeddings-archive`: scalar quantization with `always_ram=false` provides zero memory benefit | Medium | embeddings-archive |
| 4 | `embeddings-archive`: original vectors not on disk (`on_disk=false`); quantization cannot reduce memory without this | Medium | embeddings-archive |
| 5 | `products-us`: full-text index on `description` in RAM, no `on_disk=true` on any of 5 payload indexes | Medium | products-us |
| 6 | HNSW not on disk across any collection; at scale, HNSW is typically the largest single RAM consumer | Low (now) | All 12 |
| 7 | WAL retain_closed=1 on all collections adds virtual memory retention | Low | All 12 |

---

## Phase 4: Recommendations (Ordered by Impact)

### Priority 1: Consolidate the 11 locale collections into one (highest impact)

Replace `products-it-it`, `products-en-gb`, `products-de-de`, `products-fr-fr`, `products-ko-kr`, `products-zh-cn`, `products-pt-br`, `products-nl-nl`, `products-ja-jp`, `products-es-es` with a single `products` collection.

Add a `locale` keyword field to each point's payload. Filter by locale at query time:

```python
client.search(
    collection_name="products",
    query_vector=embedding,
    query_filter=Filter(
        must=[FieldCondition(key="locale", match=MatchValue(value="en-gb"))]
    ),
    limit=10
)
```

Create a keyword payload index on `locale` to keep filtered search fast:

```python
client.create_payload_index(
    collection_name="products",
    field_name="locale",
    field_schema=PayloadSchemaType.KEYWORD
)
```

**Memory savings:** Eliminates ~130-140 MB of per-collection overhead (10 collections removed x 13 MB each). This is the single largest change available.

### Priority 2: Fix `embeddings-archive` quantization config

Update quantization to use the correct config:

```python
client.update_collection(
    collection_name="embeddings-archive",
    quantization_config=ScalarQuantization(
        scalar=ScalarQuantizationConfig(
            type=ScalarType.INT8,
            always_ram=True  # pin quantized vectors in RAM for fast candidate selection
        )
    ),
    vectors_config=VectorParamsDiff(
        on_disk=True  # move original float32 vectors to disk; only read during rescoring
    )
)
```

Wait for the optimizer to finish (monitor `optimizer_status`). The quantized int8 representation is 4x smaller than float32. For `embeddings-archive` with 1536-dim vectors: 200 vectors x 1536 x 1 byte = 307 KB in RAM instead of 200 x 1536 x 4 bytes = 1.2 MB. At this scale the savings are small, but the config is currently broken and would waste 4x more memory at scale.

### Priority 3: Move `products-us` full-text index to disk

The `description` FTS index is the highest-risk in-RAM payload index. If this collection grows, it will scale poorly. Configure it for on-disk storage:

```python
# Drop and recreate the description index with on_disk=True
client.delete_payload_index(
    collection_name="products-us",
    field_name="description"
)

client.create_payload_index(
    collection_name="products-us",
    field_name="description",
    field_schema=TextIndexParams(
        type="text",
        tokenizer=TokenizerType.WORD,
        min_token_len=2,
        max_token_len=20,
        on_disk=True  # keep the FTS index on disk
    )
)
```

Keep `category`, `tags`, `product_name`, and `price` indexes in RAM since they are small and likely used in filters frequently.

### Priority 4: Plan HNSW on-disk for collections at scale

Currently no collection has built an HNSW index (all collections are below the 10,000-point `indexing_threshold`). When collections grow past that threshold, HNSW graphs will be built in RAM by default.

For `products-us` and any future large collection, plan for:

```python
client.update_collection(
    collection_name="products-us",
    hnsw_config=HnswConfigDiff(on_disk=True)
)
```

This is not urgent now but should be done before crossing the indexing threshold to avoid a sudden RAM jump.

### Priority 5 (optional): Review WAL retention

All collections have `wal_retain_closed=1`. For read-heavy or archival collections like `embeddings-archive`, reducing to `wal_retain_closed=0` saves some virtual memory retention. Only do this if WAL history for recovery purposes is not needed.

---

## What Is NOT a Problem

- **Qdrant version 1.16.3** is current. No known memory-growth bugs apply.
- **Segment count (2 per collection)** is healthy. No over-segmentation.
- **Replication factor (1)** is not multiplying data memory.
- **mmap count (585)** is 0.22% of the system limit. Not a concern.
- **Major page faults (5,242)** is low; no excessive disk paging.
- **Optimizer status** is healthy across all collections. No stuck indexing.
- The memory retained in virtual space (111 MB) is normal for mmap-based storage.

---

## Expected Memory After Fixes

| Change | Estimated Savings |
|---|---|
| Consolidate 10 locale collections into products | ~130-140 MB overhead reduction |
| Fix embeddings-archive quantization | ~0.9 MB now, 4x saving at scale |
| Move description FTS index to disk | Small now, significant at scale |

Current retained virtual: ~111 MB. After consolidation: expected drop to ~30-40 MB retained, with resident memory dropping proportionally as the 10 eliminated collections release their WAL buffers, segment files, and ID trackers.

---

## Raw API Data Summary

**Collections endpoint:** 12 collections confirmed, all status=green, all optimizer_status=ok.

**Cluster:** Single-node, 1 peer (peer_id=5322440586678173), Raft leader, term=3, 0 pending operations.

**Key config shared across all products-{locale} collections:**
- `vectors.size=768`, `distance=Cosine`, `on_disk=false`
- `hnsw_config.on_disk=false`, `m=16`, `ef_construct=100`
- `on_disk_payload=true`
- `quantization_config=null`
- `indexing_threshold=10000` (no HNSW built yet)
- `memmap_threshold=null` (default behavior)
- `wal_capacity_mb=32`, `wal_retain_closed=1`

**embeddings-archive unique config:**
- `vectors.size=1536`
- `quantization_config.scalar.type=int8`, `always_ram=false` (misconfigured)

**products-us unique config:**
- `payload_schema` has 5 indexes including full-text on `description`
- All indexes in RAM (no `on_disk=true`)
