# Quantization Recommendation for 80M OpenAI text-embedding-3-small Vectors

## TL;DR

Use **Scalar Quantization (SQ, int8)** as the primary recommendation. It cuts memory by ~4x with negligible recall loss for OpenAI embeddings. If you need even more aggressive savings and can tolerate a bit more complexity, **Binary Quantization (BQ)** with oversampling and rescoring is worth testing, but SQ is the safer, higher-quality default.

## Current Memory Footprint

Each vector at 1536 dimensions stored as float32:

```
1536 dims * 4 bytes = 6,144 bytes per vector
80,000,000 vectors * 6,144 bytes = ~460 GB just for vectors
```

That is roughly 460 GB of RAM dedicated solely to vector data (not counting indexes, payloads, or overhead).

## Quantization Options in Qdrant

Qdrant offers three quantization methods:

### 1. Scalar Quantization (int8) -- Recommended

Converts each float32 component to an int8 (1 byte), reducing per-vector storage from 6,144 bytes to 1,536 bytes.

**Memory after SQ:** ~115 GB for vectors (a 4x reduction)

**Why this is the best choice for your case:**

- OpenAI embeddings are normalized and well-distributed, which is ideal for scalar quantization. The values map cleanly into the int8 range with minimal information loss.
- Recall impact is typically less than 1% for OpenAI embeddings. Multiple production deployments report 99%+ recall retention with SQ on these models.
- It is the simplest to enable. One configuration change, no retraining, no model changes.
- Search speed actually improves because less data needs to be loaded from memory (better cache utilization).

**Configuration in Qdrant:**

```json
{
  "quantization_config": {
    "scalar": {
      "type": "int8",
      "quantile": 0.99,
      "always_ram": true
    }
  }
}
```

Setting `quantile` to 0.99 clips the top/bottom 0.5% of values before quantizing, which improves the resolution of the int8 mapping for the vast majority of values. Setting `always_ram` to true keeps quantized vectors in RAM for fast distance computation, while original vectors can optionally be stored on disk (used only for rescoring).

### 2. Binary Quantization (1-bit)

Converts each float32 component to a single bit (positive or negative), reducing per-vector storage from 6,144 bytes to 192 bytes.

**Memory after BQ:** ~14.4 GB for vectors (a 32x reduction)

**Trade-offs:**

- Extremely aggressive compression. The memory savings are dramatic.
- OpenAI embeddings do work with binary quantization better than many other models because they are high-dimensional (1536) and normalized. Higher dimensionality means more bits to work with, which partially compensates for the per-dimension information loss.
- However, recall degrades more noticeably (typically 5-10% drop at default settings). You must use oversampling (e.g., 2-3x) and rescoring against original vectors to recover quality.
- Rescoring requires keeping original vectors accessible (on disk is fine), which adds latency per query.
- The effective quality with oversampling + rescoring can get close to unquantized results, but at the cost of higher query latency compared to SQ.

**Configuration:**

```json
{
  "quantization_config": {
    "binary": {
      "always_ram": true
    }
  },
  "search_params": {
    "quantization": {
      "rescore": true,
      "oversampling": 2.0
    }
  }
}
```

### 3. Product Quantization (PQ)

Splits the vector into subvectors and quantizes each subgroup using a learned codebook.

**Memory after PQ:** Depends on configuration, typically 16-64x compression is possible.

**Why PQ is not the top recommendation here:**

- PQ requires a training phase on a sample of your data to build codebooks. With 80M vectors this is manageable but adds operational complexity.
- For normalized, high-quality embeddings like OpenAI's, SQ already achieves excellent recall at 4x compression. PQ's additional compression is usually not needed unless you are extremely memory-constrained.
- PQ can distort distances more than SQ for well-behaved embedding distributions, meaning you may need more aggressive rescoring.
- PQ is most valuable when you need compression beyond what SQ offers but better quality than BQ. For most workloads at this scale, SQ is the sweet spot.

## Recommended Strategy

### Phase 1: Enable Scalar Quantization (immediate)

1. Enable SQ (int8) on your collection with `quantile: 0.99` and `always_ram: true`.
2. Move original (full-precision) vectors to disk using `on_disk: true` in the vector config if you want to maximize RAM savings. The quantized vectors stay in RAM for search, and originals on disk are used only for optional rescoring.
3. This alone should bring your vector memory from ~460 GB down to ~115 GB in RAM, with originals on disk.

### Phase 2: Evaluate and tune

1. Benchmark recall against a ground-truth set before and after quantization. With OpenAI text-embedding-3-small, expect less than 1% recall loss at top-10/top-100.
2. If recall is acceptable (it almost certainly will be), you are done.
3. If you need even less RAM (say you want to fit everything on a smaller instance), test Binary Quantization with oversampling of 2.0 and rescoring enabled. Measure the recall and latency impact.

### Phase 3: Consider dimensionality reduction as a complement

OpenAI text-embedding-3-small supports Matryoshka-style dimensionality reduction. You could reduce from 1536 to 1024 or even 768 dimensions before storing, then apply SQ on top of that. This stacks: 768 dims with int8 gives you 768 bytes per vector, roughly an 8x total reduction from the original. However, test recall at reduced dimensions for your specific queries before committing to this.

## Summary Table

| Method | Bytes/Vector | Total RAM (80M vecs) | Recall Impact | Complexity |
|--------|-------------|----------------------|---------------|------------|
| None (float32) | 6,144 | ~460 GB | Baseline | None |
| Scalar (int8) | 1,536 | ~115 GB | < 1% loss | Low |
| Binary (1-bit) | 192 | ~14.4 GB | 5-10% without rescoring, ~1-2% with rescoring | Medium |
| Product (PQ) | Variable | ~15-60 GB | Variable | High |

## Bottom Line

**Go with Scalar Quantization (int8).** It is the highest-confidence, lowest-risk option for OpenAI embeddings at your scale. You get a 4x memory reduction with virtually no quality loss. If after enabling SQ you still need to cut memory further, layer on Binary Quantization with rescoring or reduce dimensionality, but SQ alone should solve most memory pressure issues.
