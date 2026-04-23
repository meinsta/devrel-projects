# Fixing 3-4 Second Latency After Switching to Disk

Yes, there is a middle ground, and it is the recommended production configuration. You do not need to go back to full RAM.

## What went wrong

The issue is that you switched to **full disk** storage, not **mmap** (memory-mapped files). These are fundamentally different:

- **Full disk:** Every query reads directly from disk. HNSW graph traversal requires 200-250 random reads per search. Each read hits cold storage. Result: 2-5 seconds per query.
- **mmap:** Data lives on disk files, but the OS caches frequently accessed pages in RAM automatically. Hot vectors stay in memory, cold ones live on disk. Result: 50-500ms per query.

The key insight: keeping the HNSW graph in memory is what matters most for latency. Graph traversal in RAM is nearly instantaneous (low single-digit ms). On disk, each of the 200+ hops incurs disk I/O, which is what pushes you into multi-second territory.

## The middle ground: mmap + scalar quantization

This is the recommended configuration for most production workloads. It gives you near-RAM latency at dramatically lower memory usage.

### Step 1: Switch from full disk to mmap

```http
PUT /collections/{collection_name}
{
  "optimizers_config": {
    "memmap_threshold": 10000
  }
}
```

This alone should bring latency from 3-4 seconds down to 50-500ms range, depending on how much of your data is "hot" and your disk speed (NVMe SSDs perform best here).

Docs: https://qdrant.tech/documentation/concepts/storage/

### Step 2: Add scalar quantization with `always_ram: true`

This is the critical optimization. Scalar quantization compresses your vectors from 4 bytes per element (float32) down to 1 byte (int8), a 4x reduction. Setting `always_ram: true` keeps these small quantized vectors in memory for the initial search phase.

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

How it works:
- The quantized vectors (small, 4x compressed) stay in RAM for fast initial candidate selection
- The full-precision vectors stay on disk via mmap, loaded only for rescoring the top candidates
- You get fast search with minimal memory usage

Docs: https://qdrant.tech/documentation/guides/quantization/#setting-up-quantization-in-qdrant

### Step 3: Enable rescoring for accuracy

With quantization, you want rescoring enabled so the final results are scored against full-precision vectors. This recovers any accuracy lost from compression. The performance cost is minimal because rescoring only loads a small number of top candidates from disk, not the entire dataset.

## What to expect

Here is the latency comparison across storage configurations:

| Configuration | p50 latency | p95 latency | Relative memory |
|---|---|---|---|
| Full RAM, no quantization | 5ms | 10ms | 1.0x (baseline) |
| Full RAM + scalar | 5ms | 15ms | 0.25x |
| **mmap + scalar (recommended)** | **50ms** | **500ms** | **0.20-0.25x** |
| mmap + binary (if model supports it) | 30ms | 200ms | 0.05-0.10x |
| Full disk (your current config) | 1s | 5s | ~0x |

Your chatbot was at 15ms (likely full RAM). With mmap + scalar quantization, expect 50-500ms p95, which should be fine for a chatbot use case. You use roughly 20-25% of the memory compared to your original full-RAM setup.

If your embedding model is compatible with binary quantization (OpenAI, Cohere, Jina, Gemini), you can go even further: mmap + binary quantization gives 30ms p50 / 200ms p95 at 5-10% of the original memory. But always use oversampling (3-5x) and rescoring with binary, otherwise recall drops to around 70%.

## If you need even lower latency

If 50-500ms is still too high for your chatbot:

1. Consider 4-bit or 2-bit quantization (8x or 16x compression) to keep more data in RAM while using mmap
2. Use NVMe SSDs if you are not already. Spinning disks or slow SSDs will push mmap latency higher.
3. Check whether your hot data (frequently queried vectors) fits in available RAM. mmap performance depends on the OS cache hit rate.

Do not go back to full RAM. The mmap + quantization approach is the standard production configuration and handles the vast majority of real-time workloads.
