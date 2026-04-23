# Fixing OOM Crashes on Your 96GB K8s Nodes

You have several strong options before adding RAM. Let me walk through them in priority order.

## Why it's crashing

With HNSW eating 80GB on a 96GB node, you're running at ~83% memory utilization. The HNSW index has overhead of roughly 1.5x the raw vector data, and it resists being paged out because graph traversal needs fast random access. Any traffic spike or OS memory pressure pushes you over the edge, and the OOM killer fires.

## Immediate fix: enable mmap storage

Switch your vector storage from in-memory to mmap. This moves vector data to disk-backed memory-mapped files, and the OS manages what stays in RAM based on access patterns.

This stops the OOM kills immediately. The OS will no longer try to hold everything in RAM. Instead, it caches the hot pages and pages out cold data automatically.

```http
PUT /collections/{collection_name}
{
  "optimizers_config": {
    "memmap_threshold": 10000
  }
}
```

Note: `memmap_threshold` is measured in number of vectors (KB of segment size), not kilobytes of vector data.

Docs: https://qdrant.tech/documentation/concepts/storage/

## Then: apply quantization (the biggest lever)

Quantization is the single biggest tool for reducing memory. Here is what your options look like. Qdrant supports more quantization levels than most people realize: not just scalar (int8) and binary (1-bit), but also float16, 4-bit, and 2-bit.

To estimate your current situation, use this formula:

```
RAM needed = vectors * dimensions * bytes_per_element * 1.5 (HNSW overhead)
```

Assuming you have enough vectors to fill 80GB of HNSW, here is the compression you can expect:

| Quantization | Bytes per element | Compression | Expected HNSW footprint |
|---|---|---|---|
| float32 (current) | 4.0 | 1x | ~80 GB |
| float16 | 2.0 | 2x | ~40 GB |
| Scalar (int8) | 1.0 | 4x | ~20 GB |
| 4-bit | 0.5 | 8x | ~10 GB |
| 2-bit | 0.25 | 16x | ~5 GB |
| Binary (1-bit) | 0.125 | 32x | ~2.5 GB |

**Recommended starting point: scalar quantization with `always_ram: true`.**

Scalar quantization (int8) works with every embedding model, causes less than 1% accuracy loss, and gives you 4x compression. That alone takes your 80GB HNSW index down to roughly 20GB, well within your 96GB node capacity.

```http
PUT /collections/{collection_name}
{
  "quantization_config": {
    "scalar": {
      "type": "int8",
      "always_ram": true
    }
  }
}
```

Set `always_ram: true` so the quantized vectors stay in memory for fast search. Full-precision vectors stay on mmap/disk and are loaded only for rescoring. Without this flag, both original and quantized vectors compete for memory, which defeats the purpose.

If 4x is not enough, you can go to 4-bit (8x) or 2-bit (16x) quantization. These sit between scalar and binary and provide stronger compression with less accuracy loss than binary.

Docs: https://qdrant.tech/documentation/guides/quantization/

## Also consider: FP16 on-disk storage

Even with quantization, your on-disk full vectors (used for rescoring) are stored as float32 by default. Switching to float16 halves the disk footprint and reduces rescoring I/O. The precision difference between float32 and float16 is negligible for retrieval tasks.

This stacks with quantization: use FP16 for the on-disk full vectors while keeping int8 (or smaller) quantized vectors in RAM.

Docs: https://qdrant.tech/documentation/concepts/vectors/

## Set alerting before the next crash

Do not wait for OOM kills. Set memory alerts at 75-80% utilization so your SRE team gets warning before things go sideways.

Docs: https://qdrant.tech/documentation/guides/monitoring/

## What NOT to do

- Do not jump to sharding before trying quantization + mmap on a single node. Sharding adds operational complexity and often is not necessary once you compress properly.
- Do not switch to full disk storage. It gives 2-5 second latency, which is unusable for real-time workloads.
- Do not use binary quantization blindly. It requires compatible models and must use oversampling (3-5x) with rescoring, otherwise recall drops to around 70%.

## Summary: the action plan

1. Enable mmap now to stop the crashes
2. Apply scalar quantization with `always_ram: true` (80GB drops to ~20GB)
3. If 20GB is still too tight, switch to 4-bit quantization (~10GB)
4. Enable FP16 for on-disk vectors to reduce rescoring I/O
5. Set memory alerting at 75-80%
6. Only consider sharding if the data still does not fit after all of the above
