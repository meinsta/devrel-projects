# Why Your Latency Jumped from 15ms to 3-4 Seconds

The problem is that you switched to **full disk storage**, not **mmap**. These are fundamentally different in Qdrant and the distinction is the entire reason for your latency regression.

**Full disk** means every single query reads directly from disk. HNSW graph traversal requires 200-250 random reads per search. Each read hits disk with cold-start latency. That is why you're seeing 3-4 seconds per query. This storage mode is only appropriate for offline batch processing, never for a user-facing chatbot.

**mmap (memory-mapped files)** is the middle ground you're looking for. Data lives on disk, but the OS caches frequently accessed pages in RAM automatically. Hot vectors stay in memory, cold ones stay on disk. The OS manages this for you. On NVMe SSDs, this brings latency down to 50-500ms p95.

## The Recommended Configuration: mmap + Scalar Quantization

The best approach for your chatbot combines two things:

1. **Switch from full disk to mmap storage** so the OS can cache hot pages in RAM.
2. **Enable scalar quantization with `always_ram: true`** so the small quantized vectors (4x smaller than originals) stay in RAM for the initial HNSW search, while the full-precision vectors remain on disk and are only loaded for rescoring the top candidates.

This gives you near-RAM search speed at roughly 75-80% less memory than full RAM mode.

### Step 1: Update storage to mmap

```http
PUT /collections/{collection_name}
{
  "vectors": {
    "size": <your_dim>,
    "distance": "Cosine"
  },
  "optimizers_config": {
    "memmap_threshold": 10000
  }
}
```

For an existing collection, update the optimizer config:

```http
PATCH /collections/{collection_name}
{
  "optimizers_config": {
    "memmap_threshold": 10000
  }
}
```

This tells Qdrant to move segments larger than 10,000 vectors to mmap storage. Adjust the threshold based on your dataset size.

Docs: https://qdrant.tech/documentation/concepts/storage/

### Step 2: Enable scalar quantization with always_ram

```http
PUT /collections/{collection_name}
{
  "vectors": {
    "size": <your_dim>,
    "distance": "Cosine",
    "quantization_config": {
      "scalar": {
        "type": "int8",
        "always_ram": true
      }
    }
  }
}
```

For an existing collection:

```http
PATCH /collections/{collection_name}
{
  "quantization_config": {
    "scalar": {
      "type": "int8",
      "always_ram": true
    }
  }
}
```

The `always_ram: true` flag is critical. Without it, quantized vectors may also end up on disk, and you lose the speed benefit entirely.

Docs: https://qdrant.tech/documentation/guides/quantization/#scalar-quantization

### Step 3: Enable rescoring in your search requests

When querying, set rescoring to use the full-precision vectors for the final ranking:

```http
POST /collections/{collection_name}/points/query
{
  "query": [0.1, 0.2, ...],
  "params": {
    "quantization": {
      "rescore": true
    }
  },
  "limit": 10
}
```

Rescoring keeps accuracy loss under 1% for scalar quantization.

## Expected Results

| Configuration | p50 Latency | p95 Latency | Memory vs Full RAM |
|--------------|-------------|-------------|-------------------|
| Full RAM (your original) | 5ms | 10ms | 1.0x (baseline) |
| **mmap + scalar quantization** | **50ms** | **500ms** | **0.20-0.25x** |
| Full disk (your current) | 1s | 5s | ~0x |

You should go from 3-4 seconds down to under 500ms, while using roughly 75-80% less RAM than your original full-RAM setup. For a chatbot where users already expect a brief pause for the LLM to generate a response, sub-500ms vector search is more than fast enough.

## If You Need Even Lower Latency

If you're using OpenAI, Cohere, Jina, or Gemini embeddings, you can use **binary quantization** instead of scalar. This gives 32x memory reduction and even faster search (30ms p50, 200ms p95). However, you **must** enable oversampling (3-5x) and rescoring, otherwise recall drops to around 70%. With rescoring it recovers to 95-98%.

## What NOT to Do

- Do not go back to full RAM. You switched away for a reason, and mmap + quantization solves the problem without that memory cost.
- Do not use full disk storage for any real-time application. It is a batch-processing mode.
- Do not skip the `always_ram: true` setting on quantization. That single flag is the difference between fast and slow.
- Do not skip rescoring when using quantization, especially binary quantization.
