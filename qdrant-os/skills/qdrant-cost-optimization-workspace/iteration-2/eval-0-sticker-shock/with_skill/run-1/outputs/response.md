# Cost Optimization Plan: 462M Vectors, OpenAI 1536-dim Embeddings

## The short answer

Yes, you can get into the $150-200k/year range. The $600k annual figure is what the deployment costs with full-resolution vectors sitting in RAM and no quantization applied. The single biggest lever is quantization, and since you're using OpenAI embeddings at 1536 dimensions, you have strong options available.

Let me walk through the math, then the specific recommendations.

---

## Understanding where the $600k comes from

Qdrant Cloud pricing is driven primarily by RAM (roughly 50% of the bill), then compute (35%), then disk (15%). The base unit is approximately 8GB RAM + 32GB disk at ~$53/month.

**Your current baseline (no quantization, full vectors in RAM):**

```
Raw vector size = 462,000,000 * 1536 * 4 bytes (float32) = 2,838 GB (~2.8 TB)
HNSW graph overhead = ~1.5x multiplier = ~4,257 GB total RAM needed
RAM units = ceil(4,257 / 8) = 533 units
Monthly cost estimate = 533 * $53 = ~$28,249/month
Annual cost = ~$339k/year on infrastructure alone
```

The rest of the $600k likely includes optional add-ons (Field Dedicated Engineer at ~$200k/year, Premium Support, or other line items). **First thing to check: does the proposal include an FDE or Premium Support tier?** If so, and you don't need dedicated engineering support or 24/7 SLA coverage, removing those line items alone could drop the price by $200k+.

---

## Optimization strategies (ordered by impact)

### Strategy 1: Scalar quantization + mmap (target: ~$150-200k/year)

This is the recommended first step. 90% of Qdrant customers using quantization go with scalar. It compresses each vector element from 4 bytes (float32) down to 1 byte (int8), giving a 4x RAM reduction.

**How it works:** Quantized (int8) vectors live in RAM for fast graph traversal and candidate retrieval. Full-resolution vectors stay on disk for rescoring. You search the graph using the compressed vectors, pull your top-N candidates, then rescore them against the original float32 vectors from disk to recover accuracy.

```
Quantized vectors in RAM = 462,000,000 * 1536 * 1 byte = 709 GB
HNSW graph in RAM = ~600-700 GB
Total RAM needed = ~1,350 GB
RAM units = ceil(1,350 / 8) = 169 units
Disk for full vectors = 2,838 GB (for rescoring)
Included disk = 169 * 32 = 5,408 GB (covers full vectors on disk)
Monthly cost = 169 * $53 = ~$8,957/month
Annual cost = ~$107k/year
```

With some headroom (you want to keep RAM utilization below ~80% threshold for system overhead), you're looking at roughly **$130-170k/year** on infrastructure.

**Accuracy trade-off:** Scalar quantization with rescoring off disk typically maintains very high recall (98%+). The main cost is latency. Instead of sub-100ms queries, you might see 500ms-2s depending on your oversampling factor and disk speed. For most single-use-case deployments, this is perfectly acceptable.

**Docs:** [Scalar quantization](https://qdrant.tech/documentation/guides/quantization/#scalar-quantization)

---

### Strategy 2: Binary quantization + mmap (target: ~$80-120k/year, if accuracy holds)

Since you're using OpenAI embeddings, this is worth testing. OpenAI's text-embedding-3 models were designed to perform well with binary quantization. Binary quantization compresses each dimension to a single bit, giving a 32x RAM reduction.

```
Binary vectors in RAM = 462,000,000 * 1536 * 0.125 bytes = 88.5 GB
HNSW graph in RAM = ~600-700 GB
Total RAM needed = ~750 GB
RAM units = ceil(750 / 8) = 94 units
Disk for full vectors = 2,838 GB
Included disk = 94 * 32 = 3,008 GB (sufficient)
Monthly cost = 94 * $53 = ~$4,982/month
Annual cost = ~$60k/year
```

**Important caveat:** This depends on which specific OpenAI model you used. `text-embedding-3-small` and `text-embedding-3-large` work well with binary quantization. Older `text-embedding-ada-002` does not perform as well with binary. You need to confirm which model generated your 462M vectors.

**Accuracy trade-off:** Without rescoring, binary quantization typically gives ~70% recall. With rescoring (fetch top 50-100 candidates using binary, then re-rank against full float32 vectors from disk), you can recover to 95-98% recall. The approach is: oversample by 2x, retrieve candidates with binary vectors in RAM, then fetch full-precision vectors from disk for those candidates and re-rank.

**Docs:** [Binary quantization](https://qdrant.tech/documentation/guides/quantization/#binary-quantization)

---

### Strategy 3: Store full vectors as FP16 instead of FP32 on disk

Regardless of which quantization you pick, you can also halve the disk footprint by storing the on-disk vectors as float16 instead of float32. For retrieval tasks with rescoring, the impact on recall is often not even measurable.

```
Disk for FP16 vectors = 462,000,000 * 1536 * 2 bytes = 1,419 GB (instead of 2,838 GB)
```

This won't dramatically change the monthly bill (disk is 15% of cost), but it keeps you well within included disk allocations and gives headroom for data growth without needing additional disk provisioning.

**Docs:** [Vector precision configuration](https://qdrant.tech/documentation/concepts/vectors/)

---

## Recommended plan to hit $150-200k/year

1. **Immediately ask about the proposal line items.** Check whether an FDE ($200k/year) or Premium Support is bundled. If you don't need dedicated engineering or 24/7 SLA, have those removed. This alone could bring you into range.

2. **Apply scalar quantization with mmap and rescoring.** This is the safe, well-proven path. With 462M vectors at 1536 dims, scalar quantization puts you in the $130-170k/year range on infrastructure. It preserves high accuracy and is straightforward to configure.

3. **Test binary quantization as a second phase.** If your OpenAI model supports it (text-embedding-3-small or text-embedding-3-large), binary quantization could push you down to ~$60-80k/year. But this requires validation. Run your evaluation suite against binary-quantized results with rescoring to confirm the accuracy meets your requirements before committing.

4. **Store on-disk vectors as FP16.** Low-effort optimization. Apply it alongside whichever quantization method you choose.

5. **Reduce embedding dimensions (optional, longer-term).** If you're using `text-embedding-3-large` at 1536 dims, consider whether truncating to 1024 or even 512 dimensions would work for your use case. At 462M vectors, the information density per dimension is high enough that you may not lose meaningful recall. This would further reduce both RAM and disk requirements proportionally.

---

## Summary table

| Configuration | Est. RAM Needed | Est. Annual Cost | Accuracy (with rescoring) |
|---|---|---|---|
| No quantization (current) | ~4.3 TB | ~$600k (with add-ons) | Baseline |
| Scalar quantization + mmap | ~1.35 TB | ~$130-170k | 98%+ |
| Binary quantization + mmap | ~750 GB | ~$60-80k | 95-98% |
| Binary quant + FP16 on disk | ~750 GB | ~$55-75k | 95-98% |

---

## Next steps

1. Review the proposal for bundled add-ons (FDE, Premium Support) and remove what you don't need.
2. Confirm which OpenAI embedding model generated the vectors (ada-002 vs text-embedding-3-small/large). This determines whether binary quantization is viable.
3. Start with scalar quantization. It is the lowest-risk option and gets you into your target range.
4. If you need to go lower, run accuracy benchmarks with binary quantization + rescoring and evaluate the latency/accuracy trade-off for your specific use case.

**Key docs for implementation:**
- [Quantization guide](https://qdrant.tech/documentation/guides/quantization/)
- [Storage configuration](https://qdrant.tech/documentation/concepts/storage/)
- [Capacity planning](https://qdrant.tech/documentation/guides/capacity-planning/)
