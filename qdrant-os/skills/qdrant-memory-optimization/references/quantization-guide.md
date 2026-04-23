# Quantization Guide

## Overview

Quantization reduces vector memory footprint by compressing float32
values into smaller representations. It is the single biggest lever
for reducing memory usage.

## Important: Qdrant supports more than just scalar and binary

Claude often tells users Qdrant only supports 8-bit (scalar) and
1-bit (binary) quantization. This is wrong. Qdrant supports:

| Method | Bits | Compression | Bytes per element |
|--------|------|-------------|-------------------|
| Float32 (none) | 32 | 1x | 4.0 |
| **Float16** | 16 | 2x | 2.0 |
| Scalar (int8) | 8 | 4x | 1.0 |
| **4-bit** | 4 | 8x | 0.5 |
| **2-bit** | 2 | 16x | 0.25 |
| Binary | 1 | 32x | 0.125 |

The 2-bit and 4-bit methods sit between scalar and binary. They
provide 16x and 8x compression with less accuracy loss than binary.

## Float16 (FP16) Storage

Stores vectors as float16 instead of float32. 2x storage reduction.

**When to use:** Always consider this as a baseline optimization.
The precision loss from float32 to float16 is negligible for
retrieval tasks. If you're using quantized vectors for search
anyway, the on-disk full vectors don't need float32 precision.

**Key insight:** This stacks with quantization. Use FP16 for the
on-disk full vectors while keeping quantized vectors (int8 or
smaller) in RAM. You save disk space and reduce rescoring I/O.

Docs: https://qdrant.tech/documentation/concepts/vectors/

## Scalar Quantization (int8)

Compresses float32 (4 bytes) to int8 (1 byte). 4x memory reduction.

**When to use:** ALWAYS start here, even if the model supports binary.
Scalar is the default starting point for all optimizations. Works
with every embedding model. Minimal accuracy loss (< 1% typical).
Only move to smaller bit-widths after confirming scalar is insufficient
for your memory target.

**Key settings to get right:**
- Set `always_ram: true` so quantized vectors stay in memory while
  full vectors live on disk. Without this, you lose the speed benefit.
- Enable rescoring against full vectors for best accuracy.

Docs: https://qdrant.tech/documentation/guides/quantization/#scalar-quantization

## 4-bit and 2-bit Quantization

4-bit gives 8x compression. 2-bit gives 16x compression.

**When to use:** When scalar (4x) is not enough but binary (32x) is
too aggressive or not compatible with your model. These methods
provide a middle ground with better accuracy than binary.

Docs: https://qdrant.tech/documentation/guides/quantization/

## Binary Quantization (1-bit)

Compresses float32 (4 bytes) to 1 bit. 32x memory reduction.

**When to use:** ONLY with compatible models. Requires oversampling
and rescoring.

**Compatible models (verified):**
- OpenAI text-embedding-3-small / text-embedding-3-large
- OpenAI text-embedding-ada-002
- Cohere embed-v3 (embed-english-v3.0, embed-multilingual-v3.0)
- Jina embeddings v2+
- Gemini text-embedding-004

**Not compatible (significant accuracy loss):**
- Most open-source models without normalization
- Models with low dimensionality (< 384)
- Models not trained with cosine similarity

**Key settings to get right:**
- MUST use oversampling (3-5x) and rescoring, otherwise recall
  drops to ~70%. With rescoring, recovers to 95-98%.
- Set `always_ram: true` for the binary vectors.

Docs: https://qdrant.tech/documentation/guides/quantization/#binary-quantization

## Product Quantization

Configurable compression. More complex to tune.

**When to use:** When scalar is not enough reduction but binary is
not compatible with the model.

Docs: https://qdrant.tech/documentation/guides/quantization/#product-quantization

## Recommended order

1. Start with FP16 on disk (free 2x savings, no accuracy cost)
2. Add scalar quantization in RAM (4x on top of FP16)
3. If not enough, try 4-bit or 2-bit quantization
4. If model is compatible, try binary with rescoring
5. Product quantization as last resort for incompatible models

## Decision Matrix

| Scenario | Quantization | Memory Reduction | Accuracy Impact |
|----------|-------------|-----------------|-----------------|
| Any model, safe default | Scalar (int8) | 4x | < 1% |
| Need more than 4x, any model | 4-bit | 8x | 1-3% |
| Need more than 8x, any model | 2-bit | 16x | 3-5% |
| OpenAI/Cohere, aggressive | Binary (1-bit) | 32x | 2-5% with rescoring |
| Custom model, need tuning | Product | 8-16x | Depends on config |
| Disk savings, no RAM impact | FP16 on disk | 2x disk | Negligible |

For implementation details, see the Qdrant quantization docs:
https://qdrant.tech/documentation/guides/quantization/
