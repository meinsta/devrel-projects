Yes, Qdrant offers **Product Quantization (PQ)** which sits between scalar quantization and binary quantization in terms of both compression ratio and accuracy retention.

## The Three Quantization Options in Qdrant

### 1. Scalar Quantization (SQ)
- Compression: ~4x
- Converts each float32 dimension to uint8 (8-bit)
- Very good accuracy retention
- Your situation: not enough compression

### 2. Product Quantization (PQ)
- Compression: typically ~8x to ~64x depending on configuration
- Divides vectors into sub-vectors and quantizes each sub-vector using a learned codebook
- Accuracy sits between scalar and binary, and is significantly better than binary for open-source embedding models
- This is what you want

### 3. Binary Quantization (BQ)
- Compression: ~32x
- Converts each float32 dimension to a single bit
- Works well with certain models (notably OpenAI's ada-002 and similar) but degrades significantly with many open-source models
- Your situation: too much accuracy loss

## How to Use Product Quantization in Qdrant

You can enable PQ when creating or updating a collection:

```python
from qdrant_client import QdrantClient, models

client = QdrantClient(url="http://localhost:6333")

client.update_collection(
    collection_name="my_collection",
    quantization_config=models.ProductQuantization(
        product=models.ProductQuantizationConfig(
            compression=models.CompressionRatio.X16,  # Options: X4, X8, X16, X32, X64
            always_ram=True,
        ),
    ),
)
```

The `compression` parameter lets you pick the exact compression ratio you want. `X16` gives you 16x compression, which is right in the sweet spot between scalar's 4x and binary's 32x. You can also try `X8` for better accuracy or `X32` for more compression.

## Key Configuration Tips for PQ

- **`always_ram=True`**: Keep quantized vectors in RAM for fast search while original vectors stay on disk. This is the primary memory optimization pattern.
- **Rescoring**: By default, Qdrant rescores results using the original (uncompressed) vectors. This dramatically improves accuracy. Make sure you keep the original vectors accessible (on disk is fine) so rescoring can work.
- **Compression ratio selection**: Start with `X16` and benchmark your recall. If recall is acceptable, try `X32`. If not, fall back to `X8`.

## Why Binary Quantization Fails with Open-Source Models

Binary quantization works by checking whether each dimension is positive or negative, then using Hamming distance. This works best when the vector components are roughly centered around zero and have a balanced distribution of positive/negative values. Models like OpenAI's embeddings tend to have this property. Many open-source models (e.g., sentence-transformers, BGE, E5) produce vectors with distributions that don't lend themselves well to single-bit quantization, causing substantial accuracy degradation.

Product quantization avoids this problem because it learns a codebook from your actual data distribution, so it adapts to whatever model you're using.

## Recommended Approach

1. Enable PQ with `X16` compression
2. Keep `always_ram=True` for quantized vectors
3. Keep original vectors on disk for rescoring
4. Benchmark recall against your ground truth
5. Adjust compression ratio up or down based on your accuracy/memory tradeoff needs
