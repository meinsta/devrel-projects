# Why Memory Didn't Drop After Enabling Scalar Int8 Quantization

## The Short Answer

Your configuration is partially correct, but there are at least five distinct reasons memory usage may appear unchanged even when the optimizer shows `ok`. The `ok` status only confirms the optimizer finished its work without errors. It does not confirm that all segments have been rebuilt with quantized storage, that original vectors have been evicted from RAM, or that the OS-level memory reading you are looking at reflects actual pressure rather than page cache.

---

## Root Cause Analysis

### 1. The HNSW Index Is Not on Disk

This is the most common and most impactful oversight. Setting `on_disk: true` on your vectors moves the raw float32 data to memory-mapped storage. It does not affect the HNSW graph index.

For 5 million vectors at 768 dimensions, the HNSW graph alone can consume several gigabytes of RAM depending on your `m` parameter. With the default `m=16`, the rough overhead is:

```
HNSW memory ~ num_vectors * m * 8-10 bytes
             ~ 5,000,000 * 16 * 8 = ~640 MB (just for the graph edges)
```

If `hnsw_config.on_disk` is `false` (the default), that entire graph stays in RAM regardless of what you did to the vectors. Add the quantized vectors you pinned with `always_ram: true`, and you can easily see 1-2 GB still consumed by non-vector data alone.

**Fix:** Set `hnsw_config.on_disk: true` if you want the graph off RAM, or accept it as a fixed RAM cost and size accordingly. Note that moving the HNSW graph to disk has a real search latency cost.

---

### 2. You Are Measuring Page Cache, Not Actual RAM Pressure

When Qdrant uses mmap (which `on_disk: true` enables), the OS maps vector files into virtual address space and reads them through the page cache. Tools like `htop`, `docker stats`, and `top` report RSS (Resident Set Size), which includes all pages the process has touched, whether they are truly pinned in RAM or just sitting in the OS page cache waiting to be evicted under pressure.

Qdrant's own documentation explicitly warns about this: "Memory usage metrics as reported by `top` or `htop` may be misleading. They are not showing the minimal amount of memory required to run the service."

What this means in practice: after enabling quantization with `on_disk: true`, the original vector files may be mmap'd and still fully resident in page cache because nothing has asked the OS to free those pages yet. The reading in your monitoring tool will not drop until the OS has reason to evict those cached pages (another memory-hungry process, restart, or a cache pressure tool like `vmtouch`).

**How to confirm:** Compare `RES` versus actual free memory pressure. If your system is not OOM-killing or swapping, the page cache may simply be holding old data that will be evicted naturally.

---

### 3. The Optimizer Rebuilt Segments But Did Not Evict the Old mmap Files from Page Cache

Even after the optimizer finishes rebuilding segments with quantization applied, the old mmap-backed files for original vectors remain in the OS page cache until the OS reclaims them. The optimizer status showing `ok` means the rebuild finished successfully. It does not mean page cache was flushed.

A restart of the Qdrant process is the most reliable way to start fresh and observe true post-quantization memory consumption. After restart, only the data actually accessed during warmup will be in RAM.

---

### 4. Segments Created Before Quantization Was Enabled May Not Have Been Rebuilt Yet

The optimizer applies quantization during segment rebuilds. Segments that were already indexed and not recently touched may not be immediately re-optimized. The optimizer prioritizes segments based on size thresholds and activity.

The `ok` optimizer status means no optimizer task is currently running or queued, not that every segment has been rebuilt with quantization applied. You can verify per-segment quantization status by calling the collection info endpoint and inspecting individual segment details.

**How to force a rebuild:** Temporarily lower `indexing_threshold` to force the optimizer to reprocess all segments, then restore the original value. This is intrusive but reliable.

---

### 5. The Quantized Vectors Themselves Are Still RAM-Resident (By Design)

You set `always_ram: true` for quantized vectors. For 5 million vectors at 768 dimensions with int8 scalar quantization, the in-RAM cost is:

```
Quantized size = 5,000,000 * 768 * 1 byte = ~3.6 GB
```

Plus per-vector quantization parameters (scale and offset per dimension or per vector), which add roughly another 5-15% overhead.

This is the intended cost of the hybrid `on_disk: true` + `always_ram: true` configuration: you save the original float32 cost (roughly 14.6 GB) but still hold ~3.6-4 GB in RAM for the quantized representations plus whatever the HNSW index costs. If your memory reading was already in that range before enabling quantization, it may look like nothing changed.

The memory reduction only becomes visible if you compare against the pre-quantization baseline correctly and account for what was already in RAM.

---

## Memory Budget Breakdown for Your Case

| Component | Before Quantization | After Correct Config |
|---|---|---|
| Original vectors (float32) | ~14.6 GB | on disk (mmap, page cache pressure only) |
| Quantized vectors (int8) | not present | ~3.6-4 GB in RAM (always_ram: true) |
| HNSW index (m=16, default) | ~640 MB in RAM | ~640 MB in RAM (unless hnsw_config.on_disk: true) |
| Payload indexes (in RAM) | varies | same |
| WAL + internal structures | ~100-300 MB | same |

The theoretical maximum savings are from the original vector column: ~14.6 GB moves off RAM. But if page cache is still holding those mmap'd files, your monitoring tools will not reflect it.

---

## Checklist of What to Verify

1. **Confirm `hnsw_config.on_disk` is set to `true`** if you want the graph off RAM, or account for its cost in your memory budget.

2. **Restart Qdrant** and measure memory after startup. This gives a clean reading without page cache artifacts.

3. **Check per-segment quantization status** via the collection info API. Look at whether each segment reports quantized vector files present.

4. **Do not trust `htop` RES as a hard requirement.** Use it to detect trends and pressure, not as an absolute figure.

5. **Verify payload indexes are not pinned in RAM unexpectedly.** If you have payload indexes configured with `on_disk: false`, those stay in RAM.

6. **Check your `memmap_threshold`.** If `memmap_threshold` is set very high (or not set), segments below that size stay in RAM even with `on_disk: true` at the collection level. The default is 20,000 vectors; segments smaller than this will not use mmap.

---

## Corrected Configuration Reference

```json
{
  "vectors": {
    "size": 768,
    "distance": "Cosine",
    "on_disk": true
  },
  "hnsw_config": {
    "on_disk": true
  },
  "quantization_config": {
    "scalar": {
      "type": "int8",
      "always_ram": true
    }
  }
}
```

With this config after a clean restart:
- Original float32 vectors: on disk, accessed only for rescoring
- HNSW graph: on disk (slower search, but much lower RAM)
- Quantized int8 vectors: in RAM for fast candidate retrieval
- Net RAM for vectors + index: approximately 4-5 GB instead of 15+ GB

If you want to keep HNSW in RAM for search speed, remove `hnsw_config.on_disk: true` and budget ~640 MB extra (at m=16) on top of the quantized vector RAM.

---

## Sources

- [Qdrant Quantization Guide](https://qdrant.tech/documentation/guides/quantization/)
- [Minimal RAM You Need to Serve a Million Vectors](https://qdrant.tech/articles/memory-consumption/)
- [Qdrant Storage Documentation (mmap and on_disk behavior)](https://qdrant.tech/documentation/concepts/storage/)
- [Vector Search Resource Optimization Guide](https://qdrant.tech/articles/vector-search-resource-optimization/)
- [Optimize Performance](https://qdrant.tech/documentation/guides/optimize/)
- [Capacity Planning](https://qdrant.tech/documentation/guides/capacity-planning/)
- [GitHub Issue #5268: RAM usage is incorrect in v1.12.1](https://github.com/qdrant/qdrant/issues/5268)
- [GitHub Discussion #4826: High RAM Usage with Large Collection](https://github.com/orgs/qdrant/discussions/4826)
- [Database Optimization FAQ](https://qdrant.tech/documentation/faq/database-optimization/)
- [Scalar Quantization: Background, Practices and More](https://qdrant.tech/articles/scalar-quantization/)
