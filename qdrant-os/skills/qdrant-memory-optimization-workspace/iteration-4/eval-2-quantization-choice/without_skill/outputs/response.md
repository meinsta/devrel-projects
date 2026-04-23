# Quantization Recommendation for 80M Vectors at 1536 Dims

## Current memory estimate

Without quantization, your approximate memory usage:

```
80M * 1536 * 4 bytes (float32) = ~491 GB just for raw vectors
```

With HNSW index overhead, the total is even higher. This is a lot of data to keep in RAM.

## Quantization options in Qdrant

### Scalar quantization (int8) - recommended starting point

Compresses each float32 element (4 bytes) to int8 (1 byte). 4x reduction in memory.

- Memory for 80M vectors: ~123 GB for quantized vectors
- Accuracy loss: typically less than 1%
- Works with all embedding models including OpenAI
- Safest and most predictable option

```json
{
  "quantization_config": {
    "scalar": {
      "type": "int8",
      "always_ram": true
    }
  }
}
```

### Binary quantization (1-bit) - aggressive option

Compresses each element to a single bit. 32x reduction.

- Memory for 80M vectors: ~15 GB for quantized vectors
- Your model (text-embedding-3-small) is compatible with binary quantization
- Requires oversampling (3-5x) and rescoring to maintain good recall
- Without rescoring, expect significant accuracy degradation

```json
{
  "quantization_config": {
    "binary": {
      "always_ram": true
    }
  }
}
```

### Product quantization - configurable middle ground

Splits each vector into subvectors and quantizes each independently. More complex to configure but can provide 8-16x compression.

- Useful when scalar is not enough but binary is not compatible with your model
- Requires tuning the number of segments and centroids

## Recommendation

For your specific setup (OpenAI text-embedding-3-small, 1536 dims, 80M vectors):

1. **Start with scalar quantization.** It is safe, predictable, and gives you 4x reduction. Combined with mmap storage for full vectors, this may be sufficient.

2. **If 4x is not enough, try binary quantization.** OpenAI embeddings work well with binary quantization. Make sure to enable oversampling (set to 3-5x) and rescoring against full-precision vectors. This gives 32x compression with 95%+ recall when rescoring is enabled.

3. **Combine with mmap storage.** Keep quantized vectors in RAM (`always_ram: true`) and let full vectors live on disk via mmap. The full vectors are only accessed during rescoring of the top candidates.

## Practical plan

1. Apply scalar quantization with `always_ram: true`
2. Enable mmap for full vector storage
3. Benchmark search quality on your actual queries
4. If memory is still too high or you want more compression, switch to binary quantization
5. Benchmark again to verify recall is acceptable with rescoring
