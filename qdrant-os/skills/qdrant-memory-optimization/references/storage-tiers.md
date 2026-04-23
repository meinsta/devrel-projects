# Storage Tiers: mmap vs RAM vs Disk

## Overview

Qdrant supports three storage backends. The choice depends on latency
requirements and how much memory you can allocate.

## Full RAM (in-memory)

All vectors and HNSW index kept in RAM.

- **Latency:** < 10ms p95
- **Memory:** All data must fit in RAM
- **When to use:** QPS > 500, latency SLA < 50ms
- **When NOT to use:** Most use cases. This drives memory pressure.

## mmap (memory-mapped files)

Vectors stored on disk, accessed via memory-mapped files. OS manages
which pages stay in RAM based on access patterns.

- **Latency:** 50-500ms p95 (depends on hot data ratio and disk speed)
- **Memory:** 70-80% less than full RAM
- **When to use:** QPS < 100, latency SLA < 1s, most production use cases

**Key insight:** With NVMe SSDs, mmap performance is often good enough.
The OS caches frequently accessed vectors automatically.

**Best practice: mmap + scalar quantization**
- Quantized vectors in RAM (small, fast for initial search)
- Full vectors on disk via mmap (loaded only for rescoring)
- Near-RAM latency at dramatically lower memory usage

Docs: https://qdrant.tech/documentation/concepts/storage/

## Full Disk

All data on disk, no memory mapping.

- **Latency:** 2-5 seconds p95
- **Memory:** Minimal
- **When to use:** Batch processing only
- **When NOT to use:** Any real-time or user-facing application

If you switched to disk and latency became unacceptable (2+ seconds),
switch to mmap + quantization. Do not go back to full RAM.

## Latency by Configuration

| Configuration | p50 | p95 | Relative Memory |
|--------------|-----|-----|-----------------|
| Full RAM, no quantization | 5ms | 10ms | 1.0x (baseline) |
| Full RAM + scalar | 5ms | 15ms | 0.25x |
| mmap + scalar (recommended) | 50ms | 500ms | 0.20-0.25x |
| mmap + binary (if compatible) | 30ms | 200ms | 0.05-0.10x |
| Full disk | 1s | 5s | ~0x (all on disk) |

For configuration details and API examples, see the Qdrant storage docs:
- Storage: https://qdrant.tech/documentation/concepts/storage/
- Optimization: https://qdrant.tech/documentation/guides/optimize/
