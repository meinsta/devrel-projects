# Fixing Disk Latency After Switching From RAM in Qdrant

Yes, there is a middle ground. You do not have to choose between full RAM (expensive) and full disk (unusable latency). The problem is that you switched to **full disk storage**, which forces every HNSW graph traversal hop to read from disk. Each search involves 200+ disk reads, which is why you are seeing 3-4 second latency. That is expected behavior for full disk and it should never be used for real-time applications like a chatbot.

## The Fix: mmap + Scalar Quantization

Switch from full disk to **mmap (memory-mapped files)** combined with **scalar quantization**. This is the standard production configuration for most Qdrant deployments.

### Step 1: Enable mmap storage

Update your collection to use mmap instead of full disk:

```python
from qdrant_client import QdrantClient, models

client = QdrantClient(url="http://localhost:6333")

client.update_collection(
    collection_name="your_collection",
    optimizer_config=models.OptimizersConfigDiff(
        memmap_threshold=20000
    ),
)
```

With mmap, your data lives on disk but the OS automatically caches frequently accessed pages in RAM. Hot vectors stay in memory, cold ones stay on disk. This alone should drop latency from seconds to roughly 50-500ms depending on your disk speed and working set size.

Docs: https://qdrant.tech/documentation/concepts/storage/

### Step 2: Add scalar quantization with `always_ram=true`

This is the key optimization. Scalar quantization compresses your vectors from float32 (4 bytes per dimension) to int8 (1 byte per dimension), giving you a 4x memory reduction. By setting `always_ram=true`, the small quantized vectors stay in RAM for the fast initial HNSW search, while the full-precision vectors remain on disk and are loaded only for rescoring the final candidates.

```python
client.update_collection(
    collection_name="your_collection",
    quantization_config=models.ScalarQuantization(
        scalar=models.ScalarQuantizationConfig(
            type=models.ScalarType.INT8,
            always_ram=True,
        ),
    ),
)
```

Docs: https://qdrant.tech/documentation/guides/quantization/#scalar-quantization

### Step 3: Enable rescoring in your search queries

When searching, use rescoring to maintain accuracy. The quantized vectors are used for the fast initial graph traversal, then the top candidates are rescored against the full vectors on disk:

```python
results = client.query_points(
    collection_name="your_collection",
    query=[0.1, 0.2, ...],  # your query vector
    limit=10,
    search_params=models.SearchParams(
        quantization=models.QuantizationSearchParams(
            rescore=True,
        )
    ),
)
```

## Expected Results

Here is what the latency profile looks like across configurations:

| Configuration | p50 Latency | p95 Latency | Relative Memory |
|--------------|-------------|-------------|-----------------|
| Full RAM, no quantization | 5ms | 10ms | 1.0x (baseline) |
| Full RAM + scalar quantization | 5ms | 15ms | 0.25x |
| **mmap + scalar quantization** | **50ms** | **500ms** | **0.20-0.25x** |
| Full disk (your current setup) | 1s | 5s | ~0x |

With mmap + scalar quantization, you should expect **50-500ms latency** depending on disk type and how much of your data fits in the OS page cache. That is a major improvement from 3-4 seconds, and for a chatbot where the LLM generation itself takes 1-3 seconds, search latency under 500ms is usually acceptable.

## Why This Works

The critical insight is that **keeping the HNSW graph traversal in memory is what matters most**. Each search involves 200+ hops through the graph. With full disk, every hop hits disk. With mmap + quantization:

1. The quantized vectors (4x smaller) stay in RAM via `always_ram=true`
2. The HNSW graph traversal runs against these small in-memory vectors (fast, low ms)
3. Only the final top candidates (say 10-50 vectors) need to be rescored from the full vectors on disk
4. Loading 10-50 full vectors from disk via mmap is fast, especially on NVMe SSDs

## Optional: Further Optimization

If you are using an OpenAI or Cohere embedding model, you can go even further with **binary quantization** (32x compression instead of 4x). This drops latency to around 30-200ms p95 and uses dramatically less memory. However, binary quantization requires compatible models and must always be used with oversampling (3-5x) and rescoring to maintain recall.

If scalar quantization still uses too much memory for your hardware, consider **4-bit quantization** (8x compression) or **2-bit quantization** (16x compression) as intermediate steps before going to binary.

## Summary

Do not go back to full RAM. Switch from full disk to mmap + scalar quantization with `always_ram=true`. This gives you 75-80% memory savings compared to full RAM while keeping latency in the 50-500ms range, which is perfectly usable for a chatbot.
