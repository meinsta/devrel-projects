## Yes, Qdrant supports float16 (FP16) vector storage

Qdrant supports storing vectors as float16 instead of float32, which cuts your per-vector storage from 4 bytes per dimension to 2 bytes per dimension. For your use case (200M vectors at 1536 dims), this is a straightforward way to halve disk usage with negligible recall impact.

### Storage math for your dataset

Using the memory formula:

```
Storage = vectors * dimensions * bytes_per_element * 1.5 (HNSW overhead)
```

| Storage type | Bytes/element | Raw vector data | With HNSW overhead |
|---|---|---|---|
| Float32 (current) | 4 | ~1.15 TB | ~1.72 TB |
| **Float16** | 2 | ~576 GB | ~864 GB |
| Scalar (int8) | 1 | ~288 GB | ~432 GB |

Float16 gives you the 2x reduction you're looking for on disk, and the precision loss going from float32 to float16 is negligible for retrieval tasks. At 1536 dimensions (which looks like OpenAI embeddings), the rounding error from FP16 has virtually no measurable effect on search quality.

### How to think about this

FP16 is specifically a **disk storage optimization**. It reduces the size of the full-precision vectors stored on disk. The key insight is that FP16 stacks with quantization:

- Store full vectors on disk as **FP16** (2x disk savings)
- Keep **quantized vectors in RAM** (scalar/int8 for 4x RAM savings, or smaller bit-widths for more)
- Use rescoring against the FP16 on-disk vectors for final ranking

This means you can get 2x disk savings from FP16 *and* 4x+ RAM savings from quantization simultaneously.

### Recommended configuration for 200M vectors at 1536 dims

1. **Enable FP16 for on-disk vector storage.** This is your immediate 2x disk win with no accuracy cost. See: https://qdrant.tech/documentation/concepts/vectors/

2. **Add scalar quantization (int8) with `always_ram: true`.** This keeps compressed vectors in RAM for fast search while the FP16 full vectors live on disk for rescoring. Without `always_ram: true`, you lose the speed benefit because both original and quantized vectors compete for memory.

3. **Enable rescoring** against the full (FP16) vectors for best accuracy.

With this setup, your RAM footprint for the quantized vectors would be roughly:

```
200M * 1536 * 1 byte * 1.5 = ~432 GB RAM (scalar quantization)
```

If that is still too much RAM, consider 4-bit quantization (8x compression, ~108 GB RAM) or 2-bit quantization (16x, ~54 GB RAM). Both are supported in Qdrant and provide better accuracy than binary quantization.

If you're using OpenAI embeddings, binary quantization with rescoring is also viable (32x compression, recovers to 95-98% recall with 3-5x oversampling), but start with scalar quantization first and only go smaller if you need to.

### Search quality impact

| Method | Typical accuracy impact |
|---|---|
| FP16 on disk | Negligible (not measurable in practice) |
| Scalar (int8) in RAM | < 1% recall loss |
| 4-bit in RAM | 1-3% recall loss |
| Binary with rescoring | 2-5% recall loss |

For your question specifically: yes, switching to FP16 on disk will cut your disk usage in half without losing search quality. It is the safest optimization to apply and should be considered a baseline for any deployment.

### References

- Qdrant vector storage (FP16): https://qdrant.tech/documentation/concepts/vectors/
- Quantization guide: https://qdrant.tech/documentation/guides/quantization/
- Storage optimization (mmap): https://qdrant.tech/documentation/guides/optimize/
