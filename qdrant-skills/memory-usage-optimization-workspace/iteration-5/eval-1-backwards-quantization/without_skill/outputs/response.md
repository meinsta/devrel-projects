# Diagnostic: Scalar Quantization Memory Optimization Not Working

## Collection Inspected

**Cluster:** `https://94214c31-6930-4f9f-9f33-ec90c15a76c0.eu-west-2-0.aws.cloud.qdrant.io:6333`
**Collection:** `embeddings-archive`
**Qdrant version:** `1.16.3`

---

## Raw Collection Config (from API)

```json
{
  "status": "green",
  "optimizer_status": "ok",
  "indexed_vectors_count": 0,
  "points_count": 200,
  "segments_count": 2,
  "config": {
    "params": {
      "vectors": {
        "size": 1536,
        "distance": "Cosine",
        "on_disk": false
      },
      "shard_number": 1,
      "replication_factor": 1,
      "write_consistency_factor": 1,
      "on_disk_payload": true
    },
    "hnsw_config": {
      "m": 16,
      "ef_construct": 100,
      "full_scan_threshold": 10000,
      "max_indexing_threads": 0,
      "on_disk": false
    },
    "optimizer_config": {
      "deleted_threshold": 0.2,
      "vacuum_min_vector_number": 1000,
      "default_segment_number": 0,
      "max_segment_size": null,
      "memmap_threshold": null,
      "indexing_threshold": 10000,
      "flush_interval_sec": 5,
      "max_optimization_threads": null
    },
    "quantization_config": {
      "scalar": {
        "type": "int8",
        "always_ram": false
      }
    }
  }
}
```

---

## Root Cause Analysis

Three distinct problems are present, each independently preventing memory savings.

### Problem 1: Vectors Not Indexed (Critical)

```
"indexed_vectors_count": 0
"points_count": 200
```

There are 200 points but **zero indexed vectors**. Quantization in Qdrant only applies to indexed segments. Until vectors are moved from the "small segments" (in-RAM mutable form) into an indexed segment, no quantized representation is built and stored. The original float32 vectors remain fully in memory.

The `indexing_threshold` is set to `10000`, which means the optimizer will not build an HNSW index (and therefore will not apply quantization) until a segment has at least 10,000 vectors. With only 200 points, the threshold is never crossed and quantization is never triggered.

**Fix:** Lower the indexing threshold:

```http
PATCH /collections/embeddings-archive
{
  "optimizer_config": {
    "indexing_threshold": 100
  }
}
```

This will cause the optimizer to build an indexed segment, applying scalar quantization in the process.

### Problem 2: Original Vectors Are Retained in RAM

Even after indexing is triggered, Qdrant by default keeps the original float32 vectors alongside the quantized int8 vectors. This is done to support re-scoring (rescoring improves accuracy by re-ranking quantized search results using exact distances). The result is that memory usage does not drop -- you are holding both the full float32 copy and the quantized int8 copy.

To eliminate the original vectors from RAM, set `on_disk: true` for vectors so the originals are memory-mapped from disk rather than held in RAM. The quantized vectors then serve as the fast in-memory index for ANN search, and the originals are only loaded from disk during the optional rescore phase.

```http
PATCH /collections/embeddings-archive
{
  "vectors": {
    "on_disk": true
  }
}
```

Current config shows `"on_disk": false`, which keeps all raw float32 vectors in RAM regardless of quantization.

### Problem 3: `always_ram` Is Not the Issue Here, but Worth Understanding

```json
"quantization_config": {
  "scalar": {
    "type": "int8",
    "always_ram": false
  }
}
```

`always_ram: false` means quantized vectors are not forced into RAM. This is actually the correct setting for memory reduction. If `always_ram` were `true`, the quantized vectors would be pinned in RAM, which adds memory overhead. This setting is fine as-is.

---

## Summary of Problems

| # | Problem | Why It Matters |
|---|---------|----------------|
| 1 | `indexed_vectors_count: 0` (threshold is 10000, only 200 points exist) | Quantization never runs. Raw float32 vectors serve all queries. |
| 2 | `vectors.on_disk: false` | Even if quantization ran, original float32 vectors stay in RAM alongside quantized copies, negating memory savings. |

---

## Recommended Fixes

Apply both patches:

**Step 1: Lower the indexing threshold so quantization is actually triggered.**

```http
PATCH /collections/embeddings-archive
Content-Type: application/json

{
  "optimizer_config": {
    "indexing_threshold": 100
  }
}
```

**Step 2: Move original vectors to disk so only quantized int8 vectors stay in RAM.**

```http
PATCH /collections/embeddings-archive
Content-Type: application/json

{
  "vectors": {
    "on_disk": true
  }
}
```

After applying these, wait for the optimizer to run (check `optimizer_status` and watch `indexed_vectors_count` climb to 200). Memory usage should drop by approximately 4x (float32 to int8) for the vector storage component once both changes are active.

---

## Expected Memory Savings

- Vector dimensions: 1536
- Points: 200
- Float32 size per vector: 1536 x 4 bytes = 6144 bytes
- Int8 size per vector: 1536 x 1 byte = 1536 bytes
- Reduction ratio: 4x on vector data

At 200 points, the absolute savings are small, but the same configuration issues would block savings at any scale.
