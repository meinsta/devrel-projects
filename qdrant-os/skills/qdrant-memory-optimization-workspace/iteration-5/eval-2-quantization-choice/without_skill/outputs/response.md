# Quantization Recommendation for Qdrant with OpenAI text-embedding-3-small (1536 dims, 80M vectors)

## TL;DR

Use **Scalar Quantization (SQ)** as your first move. It cuts RAM usage by roughly 4x with minimal recall loss, and it is simple to enable. If you need even more savings and can tolerate a bit more complexity, consider **Binary Quantization (BQ)** with rescoring, which can reduce memory by up to 32x. Product Quantization (PQ) is also an option but is generally slower to configure and offers less favorable tradeoffs for OpenAI embeddings.

## Current Memory Estimate

Each vector at 1536 dimensions stored as float32 consumes:

- 1536 * 4 bytes = 6,144 bytes per vector
- 80M vectors * 6,144 bytes = ~460 GB just for raw vector data (before index overhead, payload, etc.)

That is a significant footprint, so quantization will have a dramatic impact.

## Option 1: Scalar Quantization (Recommended Starting Point)

**What it does:** Converts each float32 component to uint8 (1 byte), reducing vector storage by 4x.

**Expected savings:**
- Vector storage drops from ~460 GB to ~115 GB
- 4x reduction in memory

**Quality impact:** Very low. Scalar quantization with OpenAI embeddings typically loses less than 1% recall. You can further mitigate any loss by enabling rescoring (which re-ranks the top candidates using the original full-precision vectors stored on disk).

**How to enable:**

```json
PUT /collections/{collection_name}
{
  "vectors": {
    "size": 1536,
    "distance": "Cosine"
  },
  "quantization_config": {
    "scalar": {
      "type": "int8",
      "always_ram": true
    }
  }
}
```

For search, use oversampling with rescoring to recover any precision loss:

```json
POST /collections/{collection_name}/points/query
{
  "query": [0.1, 0.2, ...],
  "params": {
    "quantization": {
      "rescore": true,
      "oversampling": 2.0
    }
  },
  "limit": 10
}
```

**Why this is the best starting point:**
- Dead simple to enable
- Predictable 4x savings
- Near-zero quality degradation with OpenAI embeddings
- Rescoring is cheap since full vectors stay on disk and only top candidates get re-read

## Option 2: Binary Quantization (Maximum Savings)

**What it does:** Reduces each float32 component to a single bit. Each dimension becomes 0 or 1.

**Expected savings:**
- Vector storage drops from ~460 GB to ~15 GB (32x reduction)
- Quantized vectors easily fit in RAM even at 80M scale

**Quality impact:** More significant than scalar quantization. Binary quantization works reasonably well with OpenAI embeddings because they tend to have high dimensionality (1536 dims gives enough bits for useful discrimination). However, you absolutely must use rescoring with a higher oversampling factor (3x-4x) to maintain acceptable recall.

**How to enable:**

```json
PUT /collections/{collection_name}
{
  "vectors": {
    "size": 1536,
    "distance": "Cosine"
  },
  "quantization_config": {
    "binary": {
      "always_ram": true
    }
  }
}
```

Search with aggressive rescoring:

```json
POST /collections/{collection_name}/points/query
{
  "query": [0.1, 0.2, ...],
  "params": {
    "quantization": {
      "rescore": true,
      "oversampling": 3.0
    }
  },
  "limit": 10
}
```

**Caveats:**
- Quality depends heavily on the embedding model. OpenAI embeddings work better than average for BQ due to high dimensionality, but you should benchmark recall on your own queries before committing.
- The oversampling during rescoring adds latency. At 80M vectors you may notice this.
- If recall matters a lot to your use case, scalar quantization is the safer bet.

## Option 3: Product Quantization (PQ)

**What it does:** Splits each vector into subvectors and quantizes each subvector independently using learned codebooks.

**Expected savings:** Configurable, typically 8x-32x depending on settings.

**Why I would skip it here:**
- Requires a training phase on existing data
- Slower to set up and harder to tune
- For OpenAI embeddings, scalar quantization already gets you most of the benefit with less complexity
- Binary quantization gives you more extreme savings if scalar is not enough
- PQ shines more when you need a middle ground with non-standard embeddings

## Recommended Strategy

1. **Start with Scalar Quantization.** Enable it, set `always_ram: true` so the quantized vectors stay in RAM while full vectors live on disk. This alone drops your RAM requirement from ~460 GB to ~115 GB for vectors.

2. **Enable `on_disk` storage for full vectors.** Keep quantized vectors in RAM for fast approximate search, but let the original float32 vectors live on disk. They are only needed for rescoring the final candidates.

   ```json
   PUT /collections/{collection_name}
   {
     "vectors": {
       "size": 1536,
       "distance": "Cosine",
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

3. **Benchmark recall.** Run your representative queries and compare recall at different `oversampling` values (1.0, 1.5, 2.0). With OpenAI embeddings and scalar quantization, you should see recall above 99% even with modest oversampling.

4. **If 115 GB is still too much**, switch to Binary Quantization. This gets you down to ~15 GB for vector storage in RAM. Benchmark recall carefully and increase oversampling as needed.

## Additional Memory Reduction Tips

- **Use `on_disk` for the HNSW index** if RAM is still tight. This trades some search latency for memory savings on the graph structure itself.
- **Consider Matryoshka dimension reduction.** OpenAI's text-embedding-3-small supports Matryoshka representations. You can truncate from 1536 to 512 or even 256 dimensions with moderate quality loss. Combined with scalar quantization at 512 dims, you would use only ~38 GB for vectors. This requires re-embedding your data though.
- **Tune HNSW parameters.** Lowering `m` (number of edges per node) from the default 16 to 8 or 12 reduces index memory at the cost of some recall. At 80M vectors, the HNSW graph itself consumes significant memory.

## Summary Table

| Method | RAM for Vectors | Reduction | Recall Impact | Complexity |
|--------|----------------|-----------|---------------|------------|
| None (float32) | ~460 GB | 1x | Baseline | None |
| Scalar (int8) | ~115 GB | 4x | Minimal (<1%) | Low |
| Binary (1-bit) | ~15 GB | 32x | Moderate (2-5%) | Medium |
| Product Quantization | ~30-60 GB | 8-16x | Variable | High |
| Scalar + dim reduction to 512 | ~38 GB | 12x | Low-moderate | Low (re-embed needed) |

**Bottom line: Enable scalar quantization with `always_ram: true` and move full vectors to disk. This is the highest-impact, lowest-risk change you can make.**
