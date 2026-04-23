# Quantization Recommendation for 80M OpenAI text-embedding-3-small Vectors (1536 dims)

## Current Memory Footprint (no quantization)

```
80M * 1536 * 4 bytes * 1.5 (HNSW overhead) = ~737 GB
```

That is enormous. You almost certainly need quantization to make this viable.

## Recommended Approach: Scalar Quantization (int8) + FP16 on Disk

**Start with scalar quantization (int8).** This is the universal safe default. It works with every embedding model, compresses 4x, and typical accuracy loss is under 1%.

```
80M * 1536 * 1 byte * 1.5 = ~184 GB RAM for quantized vectors
```

On top of scalar quantization, **store the full-precision vectors on disk as FP16 instead of float32.** FP16 halves disk usage for the original vectors with negligible precision loss. This reduces rescoring I/O when reading full vectors from disk.

### Configuration

```json
PUT /collections/{collection_name}
{
  "vectors": {
    "size": 1536,
    "distance": "Cosine",
    "datatype": "float16"
  },
  "quantization_config": {
    "scalar": {
      "type": "int8",
      "always_ram": true
    }
  },
  "optimizers_config": {
    "memmap_threshold": 20000
  }
}
```

Key settings:

- `always_ram: true` keeps quantized vectors in RAM for fast search while full vectors stay on disk (mmap). Without this, you lose the speed benefit.
- `datatype: "float16"` stores original vectors as FP16 on disk, cutting disk footprint in half.
- `memmap_threshold` moves segments to mmap so the original float16 vectors are not loaded into RAM.

## If 184 GB Is Still Too Much

You have several options to compress further. Here is the progression:

| Method | Compression | RAM Estimate (80M, 1536d) | Accuracy Impact |
|--------|-------------|---------------------------|-----------------|
| Scalar (int8) | 4x | ~184 GB | < 1% |
| 4-bit | 8x | ~92 GB | 1-3% |
| 2-bit | 16x | ~46 GB | 3-5% |
| Binary (1-bit) | 32x | ~23 GB | 2-5% with rescoring |

**4-bit quantization** brings you to ~92 GB, which is a single high-memory node. Accuracy loss is moderate (1-3%).

**Binary quantization is viable for your model.** OpenAI text-embedding-3-small is on the verified compatibility list for binary quantization. With binary you get 32x compression (down to ~23 GB), which fits on commodity hardware. However, you **must** enable oversampling (3-5x) and rescoring against full vectors, otherwise recall drops to roughly 70%. With rescoring, recall recovers to 95-98%.

Binary quantization config:

```json
"quantization_config": {
  "binary": {
    "always_ram": true
  }
}
```

Search request with required rescoring:

```json
{
  "vector": [...],
  "limit": 10,
  "params": {
    "quantization": {
      "rescore": true,
      "oversampling": 3.0
    }
  }
}
```

## Recommended Order of Operations

1. **Start with scalar (int8) + FP16 on disk.** This is the safe, predictable choice. Measure recall and latency.
2. **If RAM is still too high**, move to 4-bit quantization. Re-measure.
3. **If you need aggressive compression**, switch to binary quantization with rescoring. Your model (text-embedding-3-small) supports it. This gets 80M vectors into ~23 GB RAM.
4. Do not skip rescoring with binary. Without it, quality degrades significantly.

## Important Notes

- After changing quantization config on an existing collection, trigger segment optimization so the change takes effect. Qdrant will not automatically re-quantize existing segments without this.
- If you enable quantization but memory does not decrease, verify that `always_ram` is set to `true` and that originals are on mmap/disk. Otherwise both original and quantized vectors compete for RAM.
- Keep total RAM utilization under 80% to leave headroom for HNSW graph traversal and payload indexes.

## Summary

For your setup (80M vectors, 1536 dims, OpenAI text-embedding-3-small): start with **scalar quantization (int8)** as the safe default at 4x compression. If that is not enough, you can go all the way to **binary quantization** since your model is compatible, giving you 32x compression and fitting the entire dataset in ~23 GB RAM with rescoring enabled.
