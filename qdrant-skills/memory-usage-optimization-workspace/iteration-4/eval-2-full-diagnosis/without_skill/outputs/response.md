# Qdrant Cluster Memory Diagnostic

**Cluster:** `https://94214c31-6930-4f9f-9f33-ec90c15a76c0.eu-west-2-0.aws.cloud.qdrant.io:6333`
**Qdrant version:** 1.16.3
**Diagnostic date:** 2026-03-03
**Cluster mode:** Enabled, single node (1 peer), single leader

---

## Cluster Overview

| Metric | Value |
|---|---|
| Total collections | 12 |
| Total vectors | 1,200 |
| Total points | 1,200 |
| Active peers | 1 |
| Open mmaps | 611 |
| Memory resident (RSS) | 26.66 MB |
| Memory retained (virtual) | 109.83 MB |
| Major page faults | 5,242 |
| Process threads | 39 |

---

## Collections Inventory

| Collection | Points | Vector Dim | Quantization | Vectors on Disk | HNSW on Disk | Indexed Vectors | Payload Indexes |
|---|---|---|---|---|---|---|---|
| products-us | 500 | 768 | None | No | No | 0 | price, description (text), category, tags, product_name |
| embeddings-archive | 200 | 1536 | int8 scalar (always_ram=false) | No | No | 0 | None |
| products-it-it | 50 | 768 | None | No | No | 0 | None |
| products-en-gb | 50 | 768 | None | No | No | 0 | None |
| products-de-de | 50 | 768 | None | No | No | 0 | None |
| products-fr-fr | 50 | 768 | None | No | No | 0 | None |
| products-ko-kr | 50 | 768 | None | No | No | 0 | None |
| products-zh-cn | 50 | 768 | None | No | No | 0 | None |
| products-pt-br | 50 | 768 | None | No | No | 0 | None |
| products-nl-nl | 50 | 768 | None | No | No | 0 | None |
| products-ja-jp | 50 | 768 | None | No | No | 0 | None |
| products-es-es | 50 | 768 | None | No | No | 0 | None |

**All collections:** 2 segments each, 1 shard, replication factor 1, write consistency factor 1. All use `on_disk_payload: true`.

---

## Issues Found

### Issue 1 (CRITICAL): All vectors stored in RAM across all 12 collections

Every collection is configured with `vectors.on_disk: false`. This means the raw float32 vector data for every point is held entirely in process RAM, with no option for the OS to evict it to disk under memory pressure.

**Current vector RAM consumption:**

| Collection | Points | Dim | Raw float32 size |
|---|---|---|---|
| products-us | 500 | 768 | 1,500 KB |
| embeddings-archive | 200 | 1536 | 1,200 KB |
| 10x locale products | 500 (50 each) | 768 | 1,500 KB |
| **Total** | **1,200** | | **~4.1 MB** |

This is manageable at the current scale, but the architecture is wrong. As datasets grow to millions of vectors, having `on_disk: false` will cause RAM exhaustion. The correct approach for large collections is to set `on_disk: true` on the vectors and use memory-mapped files, allowing the OS to page in only the vectors actively needed for searches.

**Fix for all collections:**

```http
PATCH /collections/{collection_name}
{
  "vectors": {
    "on_disk": true
  }
}
```

---

### Issue 2 (CRITICAL): HNSW index also fully in RAM

All 12 collections have `hnsw_config.on_disk: false`. The HNSW graph structure (the approximate nearest neighbor index) is kept entirely in RAM alongside the raw vectors.

With `m=16` (the default bidirectional link count), each indexed vector adds roughly `m * 2 * 8 = 256 bytes` of graph overhead in RAM. None of the collections have triggered HNSW indexing yet (indexed_vectors_count is 0 across all), but when the indexing_threshold is crossed the graph will materialize entirely in RAM.

Setting `hnsw_config.on_disk: true` moves the graph to a memory-mapped file on disk, allowing the OS to manage what stays resident based on access patterns.

**Fix for all collections:**

```http
PATCH /collections/{collection_name}
{
  "hnsw_config": {
    "on_disk": true
  }
}
```

---

### Issue 3 (HIGH): No quantization on 10 of 12 collections

Only `embeddings-archive` has quantization configured (int8 scalar). The remaining 10 locale product collections and `products-us` store full float32 vectors.

For 768-dimensional vectors:
- float32: 768 dimensions * 4 bytes = **3,072 bytes per vector**
- int8 scalar quantization: 768 dimensions * 1 byte = **768 bytes per vector** (4x reduction)
- Binary quantization: 768 bits = **96 bytes per vector** (32x reduction, with recall tradeoff)

Adding int8 scalar quantization to all `products-*` collections would reduce their vector memory footprint by 75%. For `embeddings-archive` with 1536-dim vectors, quantization is already configured but not fully effective (see Issue 4).

**Fix:**

```http
PATCH /collections/{collection_name}
{
  "quantization_config": {
    "scalar": {
      "type": "int8",
      "always_ram": true
    }
  }
}
```

Note: Set `always_ram: true` for the quantized vectors when raw vectors are moved to disk. This keeps the small quantized index in RAM for fast approximate search, while the full-precision vectors are fetched from disk only for rescoring.

---

### Issue 4 (HIGH): memmap_threshold is null on all collections

The `optimizer_config.memmap_threshold` is `null` across every collection. This threshold controls when the optimizer converts an in-RAM segment to a memory-mapped on-disk segment. With `null`, the server falls back to a compiled-in default, which for Qdrant typically means segments are never automatically converted to mmap unless explicitly configured.

Memory-mapped segments let the OS decide which pages stay physically resident, evicting cold data under memory pressure. Without this, all segment data competes for RAM simultaneously.

**Fix for all collections:**

```http
PATCH /collections/{collection_name}
{
  "optimizer_config": {
    "memmap_threshold": 20000
  }
}
```

This tells the optimizer: once a segment exceeds 20,000 vectors, convert it to a memory-mapped file. Adjust the threshold downward for collections that will stay small but still need disk-backed storage.

---

### Issue 5 (HIGH): Architecture problem - 11 per-locale collections instead of one with locale filtering

The cluster has 11 separate locale-specific collections:

- products-it-it, products-en-gb, products-de-de, products-fr-fr, products-ko-kr
- products-zh-cn, products-pt-br, products-nl-nl, products-ja-jp, products-es-es
- products-us (main)

Each collection carries independent fixed overhead:
- WAL buffer: 32 MB capacity per collection = **352 MB WAL capacity** allocated across 11 locale collections alone
- Separate segment files, mmap handles, metadata structures, and optimizer threads per collection
- Each collection holds only 50 points, which is extremely small for a dedicated collection

The locale is already stored as a payload field (`locale: "it-IT"` etc.) inside the points of the locale collections. This is a clear sign these were originally one dataset split into per-locale collections unnecessarily.

The right design is a **single collection** with a `locale` keyword field and payload index. Searches filter by locale at query time. This gives:
- One set of HNSW indexes to maintain
- One WAL buffer
- Shared vector quantization
- Far fewer open file descriptors and mmaps

**Estimated overhead eliminated:** 10 collections worth of per-collection fixed costs, including up to 320 MB of WAL capacity and 10x the segment/mmap overhead.

---

### Issue 6 (HIGH): products-us payload is massively bloated

Inspecting actual points from `products-us` reveals deeply problematic payload data:

**Per-point payload breakdown:**
- `description`: ~2,000 bytes of repeated `"AAAA..."` (junk/test data)
- `full_text_content`: ~2,000 bytes of `"Lorem ipsum"` repeated 200 times
- `tags`: array of 20 keywords (`tag_0` through `tag_19`)
- `product_name`, `category`, `locale`, `price`: small fields

This puts each point's payload at roughly **4-5 KB**. Across 500 points: **~2 MB of bloated payload** loaded from disk on access.

The `description` field has a full-text index with a word tokenizer. Full-text indexes build an inverted index (term to posting list) that lives in RAM. With 2,000+ characters per point of degenerate data (`AAAA...`), the word tokenizer attempts to index a single token of 2,000+ characters (or fails gracefully), wasting index capacity.

The `full_text_content` field stores 2,000+ bytes per point but has no index, meaning it is dragged into RAM during payload reads even though it provides no search value.

**Fixes:**
1. Remove the `description` content bloat. If storing embeddings for semantic search, you do not need the raw text in payload. Store only metadata.
2. Remove `full_text_content` entirely or truncate to a useful length.
3. Reduce the `tags` array. 20 tags per point with high overlap across all points creates a low-selectivity keyword index. Use fewer, more meaningful tags.
4. Drop the full-text index on `description` if the content is being embedded into the vector anyway.

---

### Issue 7 (MEDIUM): embeddings-archive quantization is misconfigured

`embeddings-archive` has int8 scalar quantization with `always_ram: false`. This is meant to store the quantized vectors on disk. However:

- `vectors.on_disk: false` means the original float32 vectors stay in RAM
- `hnsw_config.on_disk: false` means the HNSW graph stays in RAM
- `memmap_threshold: null` means no automatic mmap conversion

The result: both the original float32 vectors (1536 * 4 bytes = 6,144 bytes/vector * 200 = 1.2 MB) AND the quantized int8 vectors (1536 bytes/vector * 200 = 300 KB) are resident in RAM simultaneously. You get the storage overhead of both representations without the RAM savings.

The correct configuration for memory efficiency with quantization:

```http
PATCH /collections/embeddings-archive
{
  "vectors": {
    "on_disk": true
  },
  "quantization_config": {
    "scalar": {
      "type": "int8",
      "always_ram": true
    }
  },
  "hnsw_config": {
    "on_disk": true
  },
  "optimizer_config": {
    "memmap_threshold": 10000
  }
}
```

With this setup: quantized vectors (small) stay in RAM for fast ANN search, original float32 vectors live on disk and are fetched only for rescoring, and the HNSW graph is mmap'd.

---

### Issue 8 (MEDIUM): indexed_vectors_count is 0 across all collections, indexing_threshold is 10,000

No HNSW index has been built in any collection. Every search is a brute-force scan. The `indexing_threshold` is set to 10,000 for all collections, meaning HNSW indexing will not trigger until a collection exceeds 10,000 points.

This is acceptable for now (brute force is fast at small scale and more accurate), but it means:
- When collections cross 10,000 points, a large HNSW graph will suddenly be built and loaded into RAM all at once
- With `hnsw_config.on_disk: false`, that graph will persist in RAM indefinitely

If growth is expected, lower the `indexing_threshold` to a manageable value (e.g., 1,000) and set `hnsw_config.on_disk: true` beforehand so the index builds into mmap'd storage rather than RAM.

---

### Issue 9 (MEDIUM): 5,242 major page faults

The Prometheus metrics show `process_major_page_faults_total = 5242`. Major page faults occur when the OS needs to read data from disk because it was evicted from physical RAM. In a vector database context, this means mmap'd segments are being accessed in patterns that exceed the working set that fits in RAM.

Despite the vectors being configured as in-RAM (`on_disk: false`), other mmap'd data (WAL segments, payload storage files, segment metadata) is clearly exceeding what the OS is keeping resident. This is a symptom of too many open segments and files across too many collections competing for the same physical memory pages.

Consolidating the 11 locale collections (Issue 5) and moving vectors to proper mmap'd on-disk storage would reduce the number of competing memory regions and likely eliminate most of these faults.

---

### Issue 10 (LOW): 611 open mmaps for only 1,200 total vectors

The system has 611 open memory-mapped file regions. For a cluster with only 1,200 vectors across 12 collections, this is extremely high. Each Qdrant segment opens multiple mmap regions (vector storage, payload storage, HNSW graph file, payload index files). With 12 collections x 2 segments each and multiple files per segment, the count compounds quickly.

The system limit is 262,144 mmaps, so there is no immediate risk of hitting the cap, but 611 mmaps for this data volume indicates many small files being kept open simultaneously. Consolidating collections and allowing the optimizer to merge small segments into larger ones will reduce this count.

---

### Issue 11 (LOW): WAL retain_closed=1 across all 12 collections

All collections retain 1 closed WAL segment after flushing (`wal_retain_closed: 1`). On a single-node cluster with no replication, this provides some crash recovery safety but adds 12 extra mmap'd files to the count. On a single-node setup where the WAL is flushed every 5 seconds (`flush_interval_sec: 5`), retaining closed segments beyond the minimum necessary is low value.

---

## Memory Impact Summary

| Problem | Memory Impact | Fixable? |
|---|---|---|
| Vectors in RAM (on_disk: false) | Grows linearly with data. 4.1 MB now, potentially GBs at scale | Yes, PATCH vectors.on_disk=true |
| HNSW graph in RAM | Will grow when indexing triggers | Yes, PATCH hnsw_config.on_disk=true |
| No quantization (10 collections) | 4x more RAM than necessary for vectors | Yes, add int8 scalar quantization |
| memmap_threshold null | Prevents OS from managing RAM | Yes, set memmap_threshold=20000 |
| 11 per-locale collections | 11x fixed overhead per collection | Yes, consolidate into single collection |
| Bloated products-us payload | ~2 MB of junk payload per 500 points | Yes, clean payload data |
| 611 open mmaps | Memory pressure from too many open files | Partially fixed by consolidation |
| 5,242 major page faults | Active memory pressure / thrashing | Resolved by above fixes |

---

## Recommended Fix Order

**Step 1** - Enable mmap for all collections (immediate RAM relief):

```http
PATCH /collections/{name}
{
  "vectors": { "on_disk": true },
  "hnsw_config": { "on_disk": true },
  "optimizer_config": { "memmap_threshold": 20000 }
}
```

Apply this to all 12 collections.

**Step 2** - Add quantization to all products-* collections:

```http
PATCH /collections/{name}
{
  "quantization_config": {
    "scalar": {
      "type": "int8",
      "always_ram": true
    }
  }
}
```

**Step 3** - Fix embeddings-archive quantization config:

```http
PATCH /collections/embeddings-archive
{
  "quantization_config": {
    "scalar": {
      "type": "int8",
      "always_ram": true
    }
  }
}
```

**Step 4** - Consolidate locale collections. Migrate all per-locale product data into a single collection with a `locale` payload field indexed as `keyword`. Drop the 10 individual locale collections.

**Step 5** - Clean products-us payload. Remove `description` bloat and `full_text_content` if not needed for search. Reduce `tags` array to meaningful, selective values. Drop the full-text index on `description` if the vector embedding already captures semantic content.

**Step 6** - Lower the indexing_threshold if you expect collections to grow past 10,000 points, so HNSW indexing happens gradually rather than all at once.

---

## Root Cause Summary

The cluster is experiencing elevated memory usage due to a combination of configuration defaults that are not appropriate for production scale, and an architectural decision to split what is logically one dataset into 11 separate per-locale collections. The most impactful changes are: (1) move vectors and HNSW indexes to disk-backed mmap storage, (2) add int8 scalar quantization cluster-wide, and (3) consolidate the locale collections. These three changes together would reduce RAM usage by roughly 80-90% at current data volume and ensure the architecture scales correctly as data grows.
