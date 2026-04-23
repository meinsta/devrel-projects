# Scalar Quantization Enabled But RAM Usage Unchanged

## Diagnosis

Scalar quantization reduces the on-disk size of vectors and can reduce RAM usage, but only under specific conditions. The fact that you enabled it and saw no reduction in RAM -- with cache memory still high at the node level -- points to one or more of the following root causes.

---

## Most Likely Causes

### 1. Memmap (on-disk) storage is not enabled

This is the single most common reason quantization does not reduce RAM.

By default, Qdrant loads vectors into RAM using in-memory storage. Scalar quantization compresses the data, but if the storage backend is still `in_memory`, all quantized vectors are simply loaded into RAM in compressed form. The working set shrinks somewhat, but the OS-level cache metrics you are watching may not change meaningfully if the original vectors were already dominating.

More importantly: if you are watching node-level OS cache metrics, the in-memory allocator holds the data in process heap, not in page cache. What you may be seeing is that the full-precision original vectors are still being kept alongside the quantized ones for rescoring.

**Fix:** Set the vector storage type to `on_disk: true` in your collection's vector configuration:

```json
"vectors": {
  "size": 1536,
  "distance": "Cosine",
  "on_disk": true,
  "quantization_config": {
    "scalar": {
      "type": "int8",
      "always_ram": false
    }
  }
}
```

Without `on_disk: true`, quantization alone does not move data out of RAM.

---

### 2. `always_ram: true` is set on the quantized vectors

Qdrant has an `always_ram` flag specifically for quantization. When set to `true`, the quantized index is pinned in RAM regardless of other storage settings. This is the default in some configurations because it speeds up search (quantized vectors are used for the coarse ANN pass, and having them in RAM is fast).

If you enabled quantization but left `always_ram: true`, the quantized vectors are sitting in RAM by design.

**Check your collection config via the REST API:**

```
GET /collections/{collection_name}
```

Look for `quantization_config.scalar.always_ram`. If it is `true`, set it to `false` and the quantized data will be mmap-backed.

---

### 3. Full-precision vectors are still in RAM for rescoring

Scalar quantization is a lossy compression. Qdrant uses quantized vectors for the initial candidate retrieval pass, then rescores the top candidates using the original full-precision vectors to maintain accuracy. This means the original vectors must remain accessible.

If your original vectors are still stored in-memory (not on-disk), the full-precision data stays in RAM. You are now paying for both the quantized index (in RAM, if `always_ram: true`) and the full-precision vectors (in RAM, because `on_disk` is not set).

**Fix:** Enable `on_disk: true` for the vector payload so full-precision vectors are mmap-backed and only pulled into page cache on demand.

---

### 4. The collection was not rebuilt after quantization was enabled

Enabling quantization on an existing collection triggers a background optimization job. Until that job completes, the collection continues using the old unquantized segments. During this period -- which can take a long time on large collections -- RAM usage will not decrease.

**Check optimizer status:**

```
GET /collections/{collection_name}
```

Look at the `optimizer_status` field. If it shows `ok` but segments are still unoptimized, you can trigger optimization manually or check segment info:

```
GET /collections/{collection_name}/cluster
```

Also check the Qdrant logs for optimizer activity. Large collections may take hours to fully re-index with quantization applied.

---

### 5. HNSW graph is still in RAM

The HNSW index graph itself is separate from vector storage. Even if vectors are quantized and on-disk, the HNSW graph can be a significant memory consumer. By default, the HNSW index is kept in RAM.

To move the HNSW graph off RAM as well:

```json
"hnsw_config": {
  "on_disk": true
}
```

This trades some search latency for memory savings. If your node metrics show high anonymous memory rather than file-backed cache, the HNSW graph is likely the culprit.

---

### 6. Page cache is being counted as "used" memory

This is a monitoring interpretation issue rather than a Qdrant configuration issue. When `on_disk` storage is enabled and mmap is used, the OS loads data into page cache as it is accessed. Page cache appears as "used" memory in tools like `free`, `top`, or most infrastructure dashboards, but it is actually reclaimable.

If you switched to `on_disk` mode and still see high "cache" in node metrics, this may be expected behavior. The OS is caching recently accessed vector data for performance. This cache is evicted automatically under memory pressure.

**To distinguish:** Check whether the memory showing up is `cached/buff` vs `used` (RSS). Tools like `smem`, `ps aux`, or `/proc/meminfo` can help. If it is page cache, the system is working correctly and memory will be freed when needed.

---

## Recommended Action Plan

1. Check current collection configuration:
   ```
   GET /collections/{collection_name}
   ```
   Confirm `on_disk` and `always_ram` settings on both vectors and quantization config.

2. If `on_disk` is not set, recreate the collection with:
   - `vectors.on_disk: true`
   - `quantization_config.scalar.always_ram: false`
   - Optionally `hnsw_config.on_disk: true`

3. Re-upload or snapshot-restore data into the new collection.

4. Wait for all optimizer jobs to complete before evaluating RAM.

5. Recheck node metrics and distinguish page cache from process RSS.

---

## Summary Table

| Root Cause | Symptom | Fix |
|---|---|---|
| `on_disk` not set | Full-precision vectors in process heap | Set `vectors.on_disk: true` |
| `always_ram: true` | Quantized index pinned in RAM | Set `always_ram: false` |
| Rescoring overhead | Both quantized + full vectors in RAM | Enable `on_disk` for vectors |
| Optimizer not done | Old segments still active | Wait or check optimizer status |
| HNSW in RAM | Graph memory not released | Set `hnsw_config.on_disk: true` |
| Page cache counted | Metrics show reclaimable cache as used | Distinguish RSS vs page cache |

The most impactful single change is almost always enabling `on_disk: true` on the vector storage. Quantization alone, without moving storage to mmap-backed files, will not produce the RAM reduction most users expect.
