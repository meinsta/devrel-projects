# Qdrant Cluster Memory Diagnostic Report

**Cluster:** https://94214c31-6930-4f9f-9f33-ec90c15a76c0.eu-west-2-0.aws.cloud.qdrant.io:6333
**Qdrant version:** 1.16.3
**Date:** 2026-03-03

---

## Cluster Overview

| Metric | Value |
|--------|-------|
| Total collections | 12 |
| Total vectors | 1,200 |
| Memory active | 19.7 MB |
| Memory resident | 28.4 MB |
| Memory retained (virtual) | 116.5 MB |

---

## Collections Inventory

| Collection | Points | Vector Dim | Quantization | on_disk | Payload Indexed |
|------------|--------|-----------|--------------|---------|-----------------|
| products-us | 500 | 768 | None | false | yes (5 fields) |
| embeddings-archive | 200 | 1536 | int8 scalar | false | no |
| products-it-it | 50 | 768 | None | false | no |
| products-en-gb | 50 | 768 | None | false | no |
| products-de-de | 50 | 768 | None | false | no |
| products-fr-fr | 50 | 768 | None | false | no |
| products-ko-kr | 50 | 768 | None | false | no |
| products-zh-cn | 50 | 768 | None | false | no |
| products-pt-br | 50 | 768 | None | false | no |
| products-nl-nl | 50 | 768 | None | false | no |
| products-ja-jp | 50 | 768 | None | false | no |
| products-es-es | 50 | 768 | None | false | no |

**All collections show `indexed_vectors_count: 0`** meaning the HNSW index has not been built (point counts are below the `indexing_threshold` of 10,000).

---

## Issues Found

### Issue 1: Redundant Locale Collections (High Impact)

The cluster contains 11 separate locale-specific product collections:

- `products-us`, `products-en-gb`, `products-de-de`, `products-fr-fr`, `products-it-it`
- `products-es-es`, `products-ko-kr`, `products-zh-cn`, `products-pt-br`, `products-nl-nl`, `products-ja-jp`

Each stores 50 points (except `products-us` with 500) with identical vector dimensions (768). All are separate collections when the only payload difference is a `locale` field (e.g. `"locale": "de-DE"`).

This design duplicates vectors in memory for every locale. The 10 non-US locale collections waste approximately **1.46 MB** of RAM on vector storage alone (10 collections x 50 points x 768 dims x 4 bytes).

The correct approach is a single `products` collection with a `locale` keyword field, filtering at query time. This reduces collection overhead from 12 to 2-3, saves per-collection segment memory, and eliminates duplicated HNSW graph structures.

```
# Current: 11 separate collections
products-de-de -> 50 points with locale: "de-DE"
products-fr-fr -> 50 points with locale: "fr-FR"
...

# Better: single collection with locale filtering
products -> 550+ points, each with locale: "de-DE" / "fr-FR" / etc.
# Query with: filter = {"must": [{"key": "locale", "match": {"value": "de-DE"}}]}
```

---

### Issue 2: Bloated Payloads in products-us (High Impact)

Each point in `products-us` has **4,748 bytes of payload** (4.6 KB per point). Across 500 points this is **2.26 MB** of payload data.

Breakdown of payload fields per point:

| Field | Bytes | Notes |
|-------|-------|-------|
| description | ~2,002 | Padded with repeated "A" characters (synthetic/garbage data) |
| full_text_content | ~2,402 | Repeated "Lorem ipsum" text (redundant with description) |
| tags | ~190 | 20 tags per product |
| product_name | ~11 | Normal |
| category | ~13 | Normal |
| price | ~18 | Normal |
| locale | ~7 | Normal |

Two fields stand out as problematic:

1. `description`: Contains 2 KB of padding characters ("AAAA..."). This appears to be test/synthetic data but if representative of production data it indicates payloads are not being cleaned or truncated before ingestion.

2. `full_text_content`: An additional 2.4 KB field of repeated Lorem ipsum text. This field is not indexed but is stored in RAM because `on_disk_payload: true` is set at the collection level (payload stored on disk), however the text index on `description` forces index structures into RAM.

The `description` field also has a **text index** configured (tokenizer: word, min_token_len: 2, max_token_len: 20). Inverted text indexes for 500 documents are relatively small, but this is unnecessary if the collection is used only for vector similarity search.

**Estimated wasted payload memory:** `(2,002 + 2,402) bytes x 500 points = ~2.1 MB`

---

### Issue 3: All Vectors in RAM, No on_disk Configuration (Medium Impact)

Every collection has `on_disk: false` for vectors. This means all vector data is loaded into RAM rather than memory-mapped from disk.

For a product catalog use case:
- Locale-specific collections with only 50 points each are unlikely to be hot enough to justify full RAM residence.
- `embeddings-archive` is named as an archive (cold/historical data) yet its vectors are in RAM.

The correct setting for archival or infrequently-accessed collections is `on_disk: true` at the vector config level. Combined with Qdrant's mmap, vectors are loaded on demand rather than kept fully resident.

```json
// When recreating or migrating collections:
"vectors": {
  "size": 768,
  "distance": "Cosine",
  "on_disk": true
}
```

---

### Issue 4: embeddings-archive Uses 1536-Dim Vectors Without on_disk (Medium Impact)

`embeddings-archive` stores 200 points with 1536-dimensional vectors (double the locale collections). Int8 scalar quantization is correctly configured, reducing vector RAM from 1.17 MB to ~0.30 MB. However:

- The collection still has `on_disk: false` so quantized vectors remain in RAM.
- The `always_ram: false` setting on the scalar quantization config means quantized vectors could be moved to disk, but this requires `on_disk: true` at the vector level.

The combination of `int8` quantization + `on_disk: true` for the vector config would bring this collection's RAM usage close to zero for the vector component.

---

### Issue 5: No HNSW Index Built (Low Impact for Current Scale)

All collections show `indexed_vectors_count: 0` despite having points. This is expected behavior: Qdrant only builds the HNSW index once `points_count >= indexing_threshold` (default: 10,000). With 50-500 points per collection, all searches currently use brute-force flat scan.

This is not a memory problem at current scale. However, it means the WAL segments hold unmerged data and segments are not fully optimized. Running the optimizer or increasing point counts past the threshold would consolidate segments and reduce per-collection overhead.

---

## Memory Estimates

| Component | RAM Usage |
|-----------|-----------|
| products-us vectors (500 x 768 x float32) | 1.46 MB |
| products-us payload (500 x 4.7 KB) | 2.26 MB |
| 10 locale collections vectors (10 x 50 x 768 x float32) | 1.46 MB |
| embeddings-archive vectors (200 x 1536 x int8) | 0.30 MB |
| HNSW index overhead (none built yet) | ~0 MB |
| Segment + WAL overhead (12 collections x 2 segments each) | ~5-10 MB (estimated) |
| **Estimated total data RAM** | **~10.5 MB** |
| **Actual memory_active_bytes (from /metrics)** | **19.7 MB** |
| **Actual memory_resident_bytes** | **28.4 MB** |
| **memory_retained_bytes (virtual)** | **116.5 MB** |

The gap between estimated data RAM (~10.5 MB) and actual resident memory (28.4 MB) is accounted for by:
- Per-collection metadata and segment overhead (Qdrant allocates per-collection structures)
- Memory allocator fragmentation and retained memory in the allocator pool
- 12 open collections each maintaining active segment handles

---

## Recommendations (Priority Order)

### 1. Consolidate locale collections into one (or few) collections

**Impact: High.** Reduces collection count from 11 product collections to 1. Eliminates duplicated per-collection segment overhead, WAL allocations, and metadata structures.

Use a single `products` collection with a `locale` keyword payload field. Apply a payload filter at query time:

```python
from qdrant_client.models import Filter, FieldCondition, MatchValue

results = client.search(
    collection_name="products",
    query_vector=query_embedding,
    query_filter=Filter(
        must=[FieldCondition(key="locale", match=MatchValue(value="de-DE"))]
    ),
    limit=10
)
```

Add a `locale` keyword index to make filtered search efficient:

```python
client.create_payload_index(
    collection_name="products",
    field_name="locale",
    field_schema="keyword"
)
```

### 2. Clean or truncate the products-us payload

**Impact: High.** Remove or truncate the `description` and `full_text_content` fields. If these fields contain test/synthetic data, they should not be in production. If full text is genuinely needed, consider storing only a short excerpt in the payload and keeping the full text in a separate database (PostgreSQL, Elasticsearch) referenced by ID.

Also remove the text index on `description` unless full-text search within Qdrant is specifically required:

```python
client.delete_payload_index(
    collection_name="products-us",
    field_name="description"
)
```

### 3. Enable on_disk for vector storage on low-traffic collections

**Impact: Medium.** For locale collections with 50 points and `embeddings-archive`, set `on_disk: true` for vectors. This requires recreating the collections, but for collections this small the migration is fast.

```python
from qdrant_client.models import VectorParams, Distance

client.recreate_collection(
    collection_name="embeddings-archive",
    vectors_config=VectorParams(
        size=1536,
        distance=Distance.COSINE,
        on_disk=True  # memory-map vectors from disk
    ),
    # preserve quantization config
)
```

### 4. Keep embeddings-archive int8 quantization, add on_disk

**Impact: Medium.** The int8 scalar quantization on `embeddings-archive` is good practice. Pair it with `on_disk: true` and set `always_ram: false` (already the default) to move quantized vectors to memory-mapped storage.

### 5. Remove or archive embeddings-archive if it is cold data

**Impact: Medium.** If `embeddings-archive` is historical/archival and not queried in production, consider whether it needs to live in the same cluster as production catalog data. Moving it to a separate low-cost cluster or snapshotting and deleting it would free both RAM and the per-collection overhead.

---

## Summary

The primary memory drivers are:

1. **11 separate locale collections** where 1 consolidated collection with locale filtering would suffice. This fragments memory across many small collections and duplicates per-collection overhead.

2. **Bloated payloads in products-us**: each point carries ~4.4 KB of synthetic padding text in `description` and `full_text_content` fields that appear to be test artifacts.

3. **All vectors in RAM** (`on_disk: false`) including archival data in `embeddings-archive`.

Addressing issues 1 and 2 alone would reduce payload memory by ~2 MB and eliminate the overhead of maintaining 10 extra collections, cutting the gap between actual and expected memory usage significantly.
