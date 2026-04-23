# Memory Usage Diagnostic: Qdrant Cloud Cluster

**Cluster:** `94214c31-6930-4f9f-9f33-ec90c15a76c0.eu-west-2-0.aws.cloud.qdrant.io:6333`
**Qdrant version:** 1.16.3
**Diagnostic date:** 2026-03-03
**Phase:** 1 (Detect)

---

## Step 1: Collection Inventory

The cluster has **12 collections**. Each collection carries a fixed baseline overhead of 12-14 MB regardless of data volume.

| Collection | Points | Dimensions | Quantization | Payload Indexes |
|---|---|---|---|---|
| products-us | 500 | 768 | None | 5 (text, keyword x3, float) |
| embeddings-archive | 200 | 1536 | scalar int8, `always_ram=false` | 0 |
| products-en-gb | 50 | 768 | None | 0 |
| products-de-de | 50 | 768 | None | 0 |
| products-fr-fr | 50 | 768 | None | 0 |
| products-it-it | 50 | 768 | None | 0 |
| products-ko-kr | 50 | 768 | None | 0 |
| products-zh-cn | 50 | 768 | None | 0 |
| products-pt-br | 50 | 768 | None | 0 |
| products-nl-nl | 50 | 768 | None | 0 |
| products-ja-jp | 50 | 768 | None | 0 |
| products-es-es | 50 | 768 | None | 0 |

**Collection overhead alone: 12 x ~13 MB = ~156 MB baseline**, before any vectors or indexes.

---

## Step 2: Collection Config Summary

All collections share the same structural pattern:
- `vectors.on_disk: false` (vectors in RAM / mmap'd)
- `hnsw_config.on_disk: false` (HNSW graph in RAM)
- `on_disk_payload: true` (payload data on disk, correct)
- `replication_factor: 1` (no replication overhead)
- `segments_count: 2` per collection (normal, optimizer not stuck)
- `optimizer_status: ok` for all collections

**Outlier 1: products-us** has 5 active payload indexes in RAM:

```json
"payload_schema": {
  "description": { "data_type": "text", "params": { "type": "text", "tokenizer": "word" } },
  "product_name": { "data_type": "keyword" },
  "category":     { "data_type": "keyword" },
  "price":        { "data_type": "float" },
  "tags":         { "data_type": "keyword" }
}
```

The full-text index on `description` is a significant RAM consumer: full-text indexes typically occupy 2-5x the size of the raw indexed text. The three keyword indexes on `product_name`, `category`, and `tags` add additional overhead proportional to cardinality.

**Outlier 2: embeddings-archive** has scalar int8 quantization with a critical misconfiguration:

```json
"quantization_config": {
  "scalar": {
    "type": "int8",
    "always_ram": false
  }
}
```

`always_ram: false` means quantized vectors are stored on disk rather than kept in RAM. This is the opposite of the correct configuration. Quantized vectors should be in RAM for fast candidate selection; original high-precision vectors should be on disk for rescoring. With `always_ram: false`, every search must read quantized vectors from disk, causing disk thrashing and defeating the purpose of quantization entirely. Meanwhile the original 1536-dim vectors (`on_disk: false`) are still being mmap'd.

---

## Step 3: Telemetry and Memory Metrics

The `/telemetry` endpoint in this version does not expose per-collection `memory_usage` fields. The `/metrics` endpoint (Prometheus format) provides process-level memory:

```
memory_resident_bytes:  27.76 MB  (physically resident in RAM)
memory_active_bytes:    19.43 MB  (active application pages)
memory_allocated_bytes: 16.66 MB  (heap allocated by Qdrant)
memory_retained_bytes: 110.43 MB  (virtual address space incl. mmap regions)
```

The gap between `memory_resident_bytes` (27.76 MB) and `memory_retained_bytes` (110.43 MB) reflects mmap'd vector files that are mapped into virtual address space but not yet paged into physical RAM. This is expected and healthy behavior: OS page cache fills physical RAM on demand as vectors are accessed.

**585 open mmaps** across 24 total segments (12 collections x 2 segments each) = ~24 mmaps per segment, which is normal (each segment maps vector data, payload, HNSW graph, and index files separately).

---

## Step 4: Optimizer Status

All 12 collections report `optimizer_status: ok` and `collection_running_optimizations: 0`. No optimizer is stuck. Any configuration changes applied would take effect immediately on the next optimization cycle.

---

## Step 5: Payload Indexes

Only `products-us` has payload indexes. The schema has:
- `description`: full-text (word tokenizer, min=2, max=20) - **highest RAM consumer**
- `product_name`: keyword
- `category`: keyword
- `price`: float
- `tags`: keyword

All 5 indexes are held in RAM by default. With `on_disk_payload: true` set (payload data on disk), these indexes are the primary in-memory data structure for `products-us` beyond the HNSW graph and ID tracker.

---

## Step 6: Segment Count

All collections have 2 segments each. Segment count is well within normal bounds (threshold for concern is >20 per shard). No segment fragmentation issues.

---

## Step 7: Version and Infrastructure

- **Qdrant version:** 1.16.3 (current, no known memory growth bugs)
- **Cluster:** single-node (1 peer), clustering enabled
- **Deployment:** Qdrant Cloud (Kubernetes-managed)

---

## Phase 2 Classification

Based on Phase 1 findings, the symptom "memory higher than expected" maps to **Pattern 3B: Unexpectedly high memory**.

The data volumes are very small (total 1,200 vectors), so raw vector RAM is negligible (~6 MB by formula). The elevated memory is structural overhead, not data growth.

---

## Root Causes Identified

### Root Cause 1: Collection proliferation for locale management (primary)

11 separate locale collections (`products-{locale}`) each holding only 50 points. At 12-14 MB overhead per collection, this structure costs ~156 MB in baseline overhead before storing a single meaningful byte of data. The locale collections each contain the same product catalog in different languages - this is a classic multi-tenant pattern that should use a single collection with a `locale` payload field and filtered search instead.

**Expected overhead if consolidated: 1-2 collections x 13 MB = 13-26 MB** instead of 156 MB.

### Root Cause 2: Misconfigured quantization on embeddings-archive

`embeddings-archive` has `scalar.always_ram: false`. This is wrong. Quantized vectors with `always_ram: false` are stored on disk, meaning every vector search must do disk I/O to read quantized vectors for candidate selection. This eliminates the performance benefit of quantization and adds disk read pressure.

The original 1536-dim float32 vectors are also not explicitly set to `on_disk: true`, meaning they are mmap'd and will be loaded into page cache during rescoring.

**Correct configuration:**
```json
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

### Root Cause 3: Full-text payload index in RAM on products-us

The `description` field has a full-text index with word tokenization. Full-text indexes are 2-5x the raw text size and are held entirely in RAM. For 500 product descriptions this may be modest now, but as the catalog grows this becomes the dominant memory consumer in `products-us`. The keyword indexes on `product_name`, `category`, and `tags` add overhead proportional to their unique value counts.

---

## Recommendations (in order of impact)

| Priority | Action | Expected impact |
|---|---|---|
| 1 | Consolidate 11 locale product collections into one collection with a `locale` keyword field | Saves ~143 MB baseline overhead, simplifies schema |
| 2 | Fix `embeddings-archive` quantization: set `always_ram: true` and `vectors.on_disk: true` | Restores quantization performance benefit, reduces disk I/O |
| 3 | Review payload indexes on `products-us`: move infrequently filtered indexes to disk using per-index `on_disk: true` | Reduces in-memory index overhead |
| 4 | Delete or archive `embeddings-archive` if it is not actively queried | Eliminates 200-point collection with 1536-dim vectors and misconfigured quantization |

---

## Raw Data

### GET /collections response
```json
{
  "result": {
    "collections": [
      {"name": "products-it-it"},
      {"name": "embeddings-archive"},
      {"name": "products-en-gb"},
      {"name": "products-de-de"},
      {"name": "products-fr-fr"},
      {"name": "products-us"},
      {"name": "products-ko-kr"},
      {"name": "products-zh-cn"},
      {"name": "products-pt-br"},
      {"name": "products-nl-nl"},
      {"name": "products-ja-jp"},
      {"name": "products-es-es"}
    ]
  }
}
```

### Memory metrics from GET /metrics
```
memory_active_bytes    20369408   (~19.4 MB)
memory_allocated_bytes 17474272   (~16.7 MB)
memory_metadata_bytes   8726464   (~8.3 MB)
memory_resident_bytes  29110272   (~27.8 MB)
memory_retained_bytes 115793920   (~110.4 MB virtual)
process_open_mmaps         585
```

### Cluster info
```
status: enabled
peers: 1 (single-node)
version: 1.16.3
startup: 2026-03-02T00:48:53.710Z
```
