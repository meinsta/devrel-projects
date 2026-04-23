# Scalar Quantization Enabled But RAM Didn't Decrease

## Summary

Enabling scalar quantization on a Qdrant collection compresses vectors on disk, but it does not automatically reduce the amount of RAM in use. The most likely explanation for unchanged memory consumption is that the original full-precision vectors are still being held in memory by the OS page cache or by Qdrant's own mmap-backed segment files. Quantization changes the storage representation, but it does not change how Qdrant loads or caches data unless you also configure the memory mapping and on-disk storage settings correctly.

---

## Root Cause Analysis

### 1. Quantized vectors exist on disk, but original vectors are still mapped into RAM

Qdrant stores vectors in segment files backed by memory-mapped files (mmap). When you enable scalar quantization, Qdrant writes a separate quantized copy of each vector. However, the original full-precision vectors remain in the segment files. Qdrant will continue to memory-map those original vectors unless you explicitly tell it to keep them on disk.

The key setting that controls this is `on_disk` within the vector storage configuration. If `on_disk: false` (the default), Qdrant eagerly loads all vector data into RAM regardless of whether quantization is active.

### 2. `always_ram` flag on quantization config keeps quantized vectors in RAM too

The quantization config has an `always_ram` option. If it is set to `true` (which is the default in many configurations), the quantized vectors are explicitly pinned in RAM. That is intentional for performance: quantized vectors are used for the first-pass HNSW search, and having them in RAM makes that fast. But this means you now have both the quantized vectors AND the original vectors resident in memory, which can actually increase RAM usage.

### 3. Original vectors are not deleted after quantization

Scalar quantization does not delete or replace the original vectors. The originals are required for re-scoring (rescoring) during search: Qdrant uses the compressed vectors for approximate candidate selection, then re-scores the top candidates using the full-precision originals for accuracy. As long as re-scoring is enabled (which it is by default), the full-precision vectors must be accessible and will be mmap-loaded or cached.

### 4. The OS page cache is holding mmap'd data

Even if Qdrant is configured to keep vectors on disk, the Linux kernel will aggressively page-cache recently accessed mmap'd pages. This appears in tools like `htop`, `free`, or Prometheus node exporter as high "cached" or "buff/cache" memory. This is not "used" memory in the traditional sense, but it looks alarming in metrics dashboards. The OS will evict this cache under memory pressure, so it is generally not a problem, but it does explain why node-level metrics show high cache memory even after quantization.

---

## What You Need to Change

### Step 1: Set original vectors to on-disk storage

When creating or recreating the collection, set the vector config to store originals on disk:

```json
"vectors": {
  "size": 1536,
  "distance": "Cosine",
  "on_disk": true
}
```

With `on_disk: true`, Qdrant will not load original vectors into RAM proactively. They will only be paged in by the OS when actually needed for re-scoring, and the OS may evict those pages under memory pressure.

### Step 2: Control whether quantized vectors live in RAM

If you want to reduce RAM usage, set `always_ram: false` in the quantization config:

```json
"quantization_config": {
  "scalar": {
    "type": "int8",
    "quantile": 0.99,
    "always_ram": false
  }
}
```

With `always_ram: false`, the quantized vectors are also stored via mmap and subject to OS page eviction. Search will be somewhat slower because the quantized vectors are no longer pinned, but RAM usage will drop significantly.

If you want the performance benefit of RAM-pinned quantized vectors (fast HNSW traversal) while keeping original vectors on disk, set `always_ram: true` and `on_disk: true` together. That is the typical production tuning: quantized vectors in RAM for speed, originals on disk and loaded on demand for rescoring.

### Step 3: Rebuild the collection index after changing settings

Quantization and storage settings only take effect after segments are rebuilt. After updating the collection config, trigger optimization:

```json
PUT /collections/{collection_name}
{
  "optimizers_config": {
    "indexing_threshold": 0
  }
}
```

Wait until all segments have been re-indexed (check via `GET /collections/{collection_name}` and look at the `optimizer_status` field). Then restore the indexing threshold to its normal value.

---

## Recommended Configuration for Memory-Efficient Deployment

```json
{
  "vectors": {
    "size": 1536,
    "distance": "Cosine",
    "on_disk": true
  },
  "quantization_config": {
    "scalar": {
      "type": "int8",
      "quantile": 0.99,
      "always_ram": true
    }
  },
  "hnsw_config": {
    "on_disk": true
  }
}
```

This configuration gives you:
- Quantized vectors pinned in RAM (fast approximate search).
- Original full-precision vectors on disk (only paged in during rescoring).
- HNSW graph on disk (reduces RAM further at the cost of slightly slower graph traversal).

Expected RAM reduction relative to baseline: roughly 75-80% for `int8` scalar quantization, because each float32 (4 bytes) becomes an int8 (1 byte), and the originals are only paged in transiently.

---

## Checklist for Diagnosis

| Question | What to check |
|---|---|
| Is `on_disk` set to `true` for the vector config? | `GET /collections/{name}` response, `config.params.vectors.on_disk` |
| Is `always_ram` set to `true` for quantization? | `config.params.quantization_config.scalar.always_ram` |
| Have segments been re-optimized since quantization was enabled? | `optimizer_status` in collection info should show `ok` and segment count should stabilize |
| Is the high memory from OS page cache (buff/cache) rather than RSS? | Check `free -h` or the node exporter `node_memory_Cached_bytes` metric vs `node_memory_MemTotal_bytes` |
| Is rescore enabled? | `params.quantization` in your search request; if `rescore: true`, originals will be loaded |

---

## Key Takeaway

Scalar quantization alone does not reduce RAM. It reduces disk space and can reduce RAM only if you also configure `on_disk: true` for the original vectors. The cache memory visible in node metrics is typically the OS page cache for mmap'd segment files, which is normal behavior. Tune the `on_disk` and `always_ram` flags, rebuild the index, and you will see the expected RAM reduction.
