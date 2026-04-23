# Quantization recommendation for OpenAI text-embedding-3-small at 80M vectors

## Short answer

Use **binary quantization**. Your model (OpenAI text-embedding-3-small) is on the verified compatibility list, and at 80M vectors with 1536 dimensions you need aggressive compression. Binary quantization gives you a 32x memory reduction. Scalar quantization (4x) is the safe fallback if you find accuracy unacceptable after testing, but start with binary.

## Memory estimates for your workload

Using the formula: `RAM = vectors * dimensions * bytes_per_element * 1.5 (HNSW overhead)`

| Quantization | Bytes per element | Estimated RAM | Reduction vs current |
|---|---|---|---|
| None (current, float32) | 4 | ~737 GB | baseline |
| Scalar (int8) | 1 | ~184 GB | 4x |
| Binary (1-bit) | 0.125 | ~23 GB | 32x |

Your current setup without quantization requires roughly 737 GB of RAM. That is almost certainly hitting hardware limits or forcing full disk storage with poor latency.

Binary quantization brings that down to approximately 23 GB, which fits comfortably on a single node with 32 GB+ RAM (keeping under the 80% utilization guideline).

Scalar quantization at ~184 GB is a big improvement but still requires a large machine or a multi-node cluster.

## Why binary works for your model

OpenAI text-embedding-3-small is explicitly verified as compatible with binary quantization. The requirements for binary quantization compatibility are:

- Model trained with cosine similarity (OpenAI models are)
- Dimensionality >= 384 (you have 1536)
- Normalized embeddings (OpenAI outputs are L2-normalized)

## Configuration requirements (critical)

Binary quantization without proper settings will tank your recall to ~70%. You must configure these:

1. **Oversampling at 3-5x**: This fetches more candidates during the initial binary search pass. Set oversampling to 3 as a starting point, increase to 5 if recall is still not meeting your bar.

2. **Rescoring enabled**: After the binary pass fetches candidates, rescore against the full float32 vectors. This recovers recall to 95-98%.

3. **`always_ram: true`**: Keep the binary quantized vectors in RAM. The full float32 vectors should live on disk via mmap. Without this, both original and quantized vectors compete for memory and you lose the benefit.

4. **Trigger segment optimization** after applying the configuration change. Quantization does not retroactively compress existing segments until optimization runs.

## If accuracy is not sufficient

If binary quantization with rescoring does not meet your accuracy requirements after benchmarking:

1. Fall back to **scalar quantization** (4x reduction, < 1% accuracy loss typical)
2. Combine scalar quantization with **mmap** for the original vectors so the ~184 GB footprint is partially offloaded to disk
3. Product quantization (8-16x) is an option but requires more tuning and is harder to get right

## What to avoid

- Do not skip rescoring with binary quantization. The accuracy drop without it is severe.
- Do not try to solve this by adding RAM alone. At 737 GB baseline, quantization is the first lever.
- Do not shard across multiple nodes before trying quantization plus mmap on a single node.
- Do not use full disk storage for real-time queries. It introduces 2-5 second latency.

## Reference

- Qdrant quantization docs: https://qdrant.tech/documentation/guides/quantization/
- Binary quantization specifics: https://qdrant.tech/documentation/guides/quantization/#binary-quantization
- Scalar quantization specifics: https://qdrant.tech/documentation/guides/quantization/#scalar-quantization
