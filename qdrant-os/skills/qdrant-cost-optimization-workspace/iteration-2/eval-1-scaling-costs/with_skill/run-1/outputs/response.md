# Qdrant Scaling Cost Projection: 10M to 100M Vectors

## Your Setup

- **Embedding model:** Cohere embed-v3
- **Dimensions:** 1024
- **Quantization:** Scalar (int8)
- **Current scale:** 10M vectors
- **Target scale:** 100M vectors by end of year

## The Formula

Qdrant managed cloud pricing breaks down as roughly 50% memory (RAM), 35% compute, and 15% disk. The core pricing unit is:

> **1 RAM unit = 8 GB RAM + 32 GB disk = ~$53/month**

The formula for total RAM needed:

```
Total RAM = quantized_vectors_in_RAM + HNSW_graph_overhead

Quantized vectors in RAM = num_vectors * dimensions * bytes_per_element
HNSW graph overhead      = ~1.3x of quantized vector size (at this dimension)

RAM units                = ceil(Total RAM GB / 8)
Monthly cost             = RAM units * $53
```

With scalar quantization, each dimension is stored as 1 byte (int8) instead of 4 bytes (float32), giving you a 4x compression ratio.

## Current Cost: 10M Vectors (Scalar Quantization)

```
Quantized vectors in RAM = 10,000,000 * 1024 * 1 byte
                         = 10,240,000,000 bytes
                         = 9.54 GB

HNSW graph overhead      = ~12-14 GB (graph edges, metadata)
Total RAM needed         = ~23 GB

RAM units                = ceil(23 / 8) = 3 units
Included disk            = 3 * 32 = 96 GB

Full-precision vectors on disk (for rescoring) = 10M * 1024 * 4 bytes = 40.96 GB
96 GB included disk covers this.

Monthly cost             = 3 * $53 = ~$159/month
Annual cost              = ~$1,908/year
```

## Projected Cost: 100M Vectors (Scalar Quantization, Same Config)

```
Quantized vectors in RAM = 100,000,000 * 1024 * 1 byte
                         = 102,400,000,000 bytes
                         = 95.4 GB

HNSW graph overhead      = ~120-140 GB
Total RAM needed         = ~230 GB

RAM units                = ceil(230 / 8) = 29 units
Included disk            = 29 * 32 = 928 GB

Full-precision vectors on disk (for rescoring) = 100M * 1024 * 4 bytes = 409.6 GB
928 GB included disk covers this.

Monthly cost             = 29 * $53 = ~$1,537/month
Annual cost              = ~$18,444/year
```

## Scaling Pattern Summary

| Scale | Quantization | RAM Needed | RAM Units | Monthly Cost | Annual Cost |
|-------|-------------|-----------|-----------|-------------|-------------|
| 10M vectors | Scalar (int8) | ~23 GB | 3 | ~$159 | ~$1,908 |
| 25M vectors | Scalar (int8) | ~58 GB | 8 | ~$424 | ~$5,088 |
| 50M vectors | Scalar (int8) | ~115 GB | 15 | ~$795 | ~$9,540 |
| 75M vectors | Scalar (int8) | ~173 GB | 22 | ~$1,166 | ~$13,992 |
| 100M vectors | Scalar (int8) | ~230 GB | 29 | ~$1,537 | ~$18,444 |

With scalar quantization and the same configuration, scaling is linear. 10x the vectors means roughly 10x the cost.

## Ways to Reduce Cost at 100M Scale

If $1,537/month feels too high at the 100M mark, here are two paths to consider.

### Option A: Binary Quantization (32x compression)

Cohere embed-v3 should be tested for binary quantization compatibility. Not every model works well with binary quantization, so you would need to validate recall against your dataset. If it works:

```
Binary vectors in RAM    = 100,000,000 * 1024 * 0.125 bytes = 12.8 GB
HNSW graph overhead      = ~120-140 GB
Total RAM needed         = ~148 GB

RAM units                = ceil(148 / 8) = 19 units
Monthly cost             = 19 * $53 = ~$1,007/month
Annual cost              = ~$12,084/year
```

That would save roughly $6,360/year compared to scalar at 100M. However, the real win from binary quantization is on the vector storage side. The HNSW graph overhead dominates at this scale, which limits the gap.

**Important trade-off:** Binary quantization with Cohere embed-v3 will likely need rescoring with full-precision vectors from disk to maintain acceptable recall (target 95-98%). This adds latency. If your SLA requires sub-100ms searches, test carefully.

### Option B: Store Full Vectors as FP16 Instead of FP32

You can store the on-disk full-resolution vectors as float16, cutting disk storage in half (from 409.6 GB to 204.8 GB at 100M scale). For retrieval tasks, the precision loss from FP16 is rarely measurable. This does not change RAM cost directly, but it reduces disk needs and speeds up rescoring from disk.

### Option C: Reduce Dimensions

Cohere embed-v3 supports Matryoshka representations, meaning you can truncate to 512 or 768 dimensions with moderate recall loss. At 512 dimensions with scalar quantization:

```
Quantized vectors in RAM = 100,000,000 * 512 * 1 byte = 47.7 GB
HNSW graph overhead      = ~65-75 GB
Total RAM needed         = ~120 GB

RAM units                = ceil(120 / 8) = 15 units
Monthly cost             = 15 * $53 = ~$795/month
Annual cost              = ~$9,540/year
```

That is roughly a 48% cost reduction at 100M scale compared to 1024 dimensions. The accuracy impact depends on your use case, so test on your actual queries.

## Key Takeaway

With your current setup (1024 dims, scalar quantization), going from 10M to 100M vectors will take your monthly cost from roughly **$159/month to $1,537/month**. That is a linear 10x increase.

If you need to keep costs lower as you grow, the most impactful levers are:

1. **Test binary quantization** with Cohere embed-v3 (validate recall first)
2. **Reduce dimensions** to 512 or 768 if your application tolerates it
3. **Use FP16** for on-disk vectors to reduce storage overhead

The recommendation: start with scalar quantization as you scale (which you are already doing), and at the 50M mark, run a binary quantization test against your actual queries. If recall holds above 95% with rescoring, switch to binary to flatten the cost curve for the second half of your growth.

## References

- [Scalar quantization docs](https://qdrant.tech/documentation/guides/quantization/#scalar-quantization)
- [Binary quantization docs](https://qdrant.tech/documentation/guides/quantization/#binary-quantization)
- [Capacity planning guide](https://qdrant.tech/documentation/guides/capacity-planning/)
- [Storage configuration](https://qdrant.tech/documentation/concepts/storage/)
- [Vector precision configuration](https://qdrant.tech/documentation/concepts/vectors/)
