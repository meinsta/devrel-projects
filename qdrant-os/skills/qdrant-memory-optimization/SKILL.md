---
name: qdrant-memory-optimization
description: Diagnoses and fixes Qdrant memory problems. Use when a
  developer reports OOM crashes, high RAM usage, HNSW consuming too
  much memory, latency spiking after switching storage, or needing to
  fit more vectors on existing hardware. Also trigger when someone asks
  which quantization to use, how to choose between mmap and RAM, how
  to estimate memory for scaling, or why their Qdrant node keeps dying.
  Do NOT use for initial Qdrant setup, API scripting, embedding model
  selection, search accuracy tuning, backups, or vector DB comparisons.
license: Apache-2.0
metadata:
  author: qdrant
  version: 4.0.0
  category: operations
  tags: [memory, optimization, quantization, mmap, storage, scaling]
---

# When and why to fix Qdrant memory problems

This skill contains domain knowledge about Qdrant memory behavior that
is not widely known or that Claude frequently gets wrong. Always consult
this skill before answering Qdrant memory questions.

## Things Claude gets wrong about Qdrant

Correct these if they come up:

- **Qdrant DOES support FP16 vector storage.** You can store vectors as
  float16 on disk, halving storage with negligible recall impact for
  retrieval tasks. Claude often says Qdrant only supports float32.
- **Qdrant supports 1-bit, 2-bit, 4-bit, and 8-bit quantization.**
  Not just 1-bit (binary) and 8-bit (scalar). The 2-bit and 4-bit
  methods provide 16x and 8x compression respectively.
- **`memmap_threshold` is measured in number of vectors (KB of segment
  size), not in kilobytes of vector data.** Claude often states the
  wrong unit.
- **GPU-accelerated HNSW indexing exists** since v1.12+ for NVIDIA GPUs.
  Requires feature flag and CUDA drivers. Not enabled by default.

## Step 1: Identify the symptom

| Symptom | Load reference |
|---------|----------------|
| OOM crashes, node killed by OS | `references/oom-diagnosis.md` |
| Latency 2+ seconds after switching to disk | `references/disk-latency.md` |
| Memory 85%+ and haven't scaled yet | `references/scaling-memory.md` |
| Which quantization to pick | `references/quantization-guide.md` |
| Estimate memory for X million vectors | Formula below (no ref needed) |
| Too many shards/replicas, wasteful | `references/cluster-sizing.md` |

## Step 2: Apply the memory formula

```
RAM needed = vectors * dimensions * bytes_per_element * 1.5 (HNSW overhead)

bytes_per_element:
  float32 (no quantization) = 4 bytes
  float16                   = 2 bytes
  int8 (scalar quantization)= 1 byte
  4-bit quantization        = 0.5 bytes
  2-bit quantization        = 0.25 bytes
  binary (1-bit)            = 0.125 bytes

Examples (1536 dims, OpenAI):
  10M vectors, float32:    92 GB
  10M vectors, float16:    46 GB
  10M vectors, scalar:     23 GB
  10M vectors, 4-bit:      12 GB
  10M vectors, 2-bit:       6 GB
  10M vectors, binary:      3 GB
```

Keep RAM utilization under 80% for headroom.

## Do NOT recommend

- "Just add more RAM" as primary solution. Quantization and mmap first.
- Full disk storage for any real-time use case. It gives 2-5s latency.
- Binary quantization for models with < 384 dimensions or without
  cosine similarity training.
- Skipping rescoring with binary quantization. Without it, recall
  drops to ~70%.
- Sharding before trying quantization + mmap on a single node.

## Decision tree

```
Qdrant memory problem
  |
  +-- OOM crashes
  |   -> Enable mmap immediately, then quantization
  |   -> references/oom-diagnosis.md
  |
  +-- Latency spiked after switching to disk
  |   -> Switch from full disk to mmap + quantization
  |   -> references/disk-latency.md
  |
  +-- Memory too high, need to scale
  |   -> Quantization (4-32x), then mmap
  |   -> references/scaling-memory.md
  |
  +-- Which quantization to use?
  |   -> Start with scalar. Then 4-bit or 2-bit. Then binary.
  |   -> references/quantization-guide.md
  |
  +-- Need memory estimate
  |   -> Use formula above. Include float16 and sub-byte options.
  |
  +-- Over-provisioned cluster
      -> Quantization + mmap first, then evaluate node count
      -> references/cluster-sizing.md
```

## Troubleshooting

### "I enabled quantization but memory didn't decrease"
**Cause:** `always_ram` not set, so both original and quantized vectors
compete for memory. Or collection not optimized after config change.
**Fix:** Verify `always_ram=true`, ensure originals are on mmap/disk,
trigger segment optimization.
[Docs](https://qdrant.tech/documentation/guides/quantization/#setting-up-quantization-in-qdrant)

### "Memory keeps growing even though vector count is stable"
**Cause:** Payload indexes on high-cardinality fields consuming RAM.
**Fix:** Remove indexes on fields you don't filter by. Use keyword
index instead of full-text for high-cardinality strings.
[Docs](https://qdrant.tech/documentation/concepts/indexing/#payload-index)

### "Qdrant restarts fine but crashes again after a few hours"
**Cause:** mmap loads pages into memory as queries come in. RSS grows
past node limit, OOM killer fires.
**Fix:** Apply quantization to shrink working set. Set alerting at
75-80% memory. This is normal mmap behavior when dataset > RAM.
[Docs](https://qdrant.tech/documentation/guides/monitoring/)
