# Yes, Qdrant supports 4-bit and 2-bit quantization between scalar and binary

Qdrant supports a full spectrum of quantization levels, not just scalar (8-bit, 4x compression) and binary (1-bit, 32x compression). Here is the complete set of options:

| Method | Bits | Compression | Bytes per dimension |
|--------|------|-------------|---------------------|
| Float32 (none) | 32 | 1x | 4.0 |
| Float16 | 16 | 2x | 2.0 |
| Scalar (int8) | 8 | 4x | 1.0 |
| **4-bit** | **4** | **8x** | **0.5** |
| **2-bit** | **2** | **16x** | **0.25** |
| Binary | 1 | 32x | 0.125 |

The two options that sit between scalar and binary are:

## 4-bit quantization (8x compression)

This doubles the compression of scalar quantization while maintaining reasonable accuracy. Typical accuracy impact is 1-3%, which is far better than what you would see with binary quantization on an open-source model. This is the recommended next step when scalar is not compressing enough.

## 2-bit quantization (16x compression)

This provides 16x compression with a 3-5% typical accuracy impact. Still much safer than binary for open-source models, which often lack the cosine-similarity training and normalization properties that binary quantization depends on.

## Why binary fails with open-source models

Binary quantization works well with models specifically designed for it (OpenAI, Cohere embed-v3, Jina v2+, Gemini). Most open-source models were not trained with the properties that make binary quantization viable:

- They may lack proper normalization
- They may not have been trained with cosine similarity as the objective
- Models with fewer than 384 dimensions are especially poor candidates

Even with oversampling (3-5x) and rescoring, binary quantization on incompatible models produces significant recall degradation that rescoring cannot fully recover.

## Recommended approach for your deployment

Given that scalar (4x) is not enough and binary (32x) destroys accuracy with your open-source model:

1. **Try 4-bit quantization first.** 8x compression is double what scalar gives you, and accuracy loss is modest.
2. **If 8x is still not enough, try 2-bit.** 16x compression with 3-5% accuracy hit is often acceptable.
3. **Stack FP16 on disk with quantized vectors in RAM.** Store your full-precision vectors as float16 on disk instead of float32. This halves disk usage and reduces rescoring I/O, with negligible precision loss for retrieval. This is a free optimization on top of any quantization method.
4. **Always enable rescoring against full vectors** and set `always_ram: true` for the quantized vectors.

## Configuration

Quantization is configured per collection. Consult the Qdrant quantization docs for the exact API parameters for 4-bit and 2-bit methods:

https://qdrant.tech/documentation/guides/quantization/

## Memory estimate example

For 10 million vectors at 1536 dimensions (OpenAI-sized):

- Float32 (no quantization): ~92 GB
- Scalar (int8, 4x): ~23 GB
- **4-bit (8x): ~12 GB**
- **2-bit (16x): ~6 GB**
- Binary (1-bit, 32x): ~3 GB

The formula: `vectors * dimensions * bytes_per_element * 1.5` (the 1.5 multiplier accounts for HNSW graph overhead).

Keep RAM utilization under 80% for operational headroom.
