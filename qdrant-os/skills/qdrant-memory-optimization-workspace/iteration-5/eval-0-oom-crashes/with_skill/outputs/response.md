# Fixing Qdrant OOM Kills on Kubernetes (96GB Nodes, 80GB HNSW)

Your HNSW index consuming 80GB out of 96GB leaves zero headroom for the OS, payload indexes, and query-time allocations. The OOM killer is doing exactly what it should. Here is how to fix this without adding RAM, ordered by impact and urgency.

## Immediate: Enable mmap to Stop the Crashes Today

Move vector storage to memory-mapped files. This hands memory management to the OS kernel, which pages data in and out based on access patterns instead of holding everything resident in RAM.

```yaml
# PATCH /collections/{collection_name}
{
  "optimizers_config": {
    "memmap_threshold": 20000
  }
}
```

Or set it in the collection's vector configuration:

```yaml
{
  "vectors": {
    "on_disk": true
  }
}
```

This stops OOM kills immediately. Your hot working set stays in RAM through the page cache while cold segments live on disk. Latency may increase slightly (expect 5-20ms added for warm queries, more for cold), but you stop crashing.

**Important note on mmap behavior in k8s:** After enabling mmap, RSS will still grow as queries load pages into the page cache. This is normal. The OS reclaims pages under memory pressure instead of triggering OOM. Make sure your k8s resource limits use `resources.limits.memory` set somewhat above your expected working set, and confirm your pods are NOT setting memory requests equal to limits (which prevents the kernel from reclaiming page cache).

Docs: https://qdrant.tech/documentation/concepts/storage/

## Then: Apply Quantization to Shrink the Footprint

Quantization is the single biggest lever. Your 80GB HNSW index tells us you have a large vector set stored at float32. Here is what quantization does to that number.

### Memory math for your situation

Assuming your setup is roughly 10M vectors at 1536 dimensions (OpenAI-class embeddings), the math works out to:

```
Current (float32):     10M * 1536 * 4 bytes * 1.5 (HNSW) = ~92 GB
Scalar (int8):         10M * 1536 * 1 byte  * 1.5        = ~23 GB
4-bit quantization:    10M * 1536 * 0.5     * 1.5        = ~12 GB
2-bit quantization:    10M * 1536 * 0.25    * 1.5        = ~6 GB
Binary (1-bit):        10M * 1536 * 0.125   * 1.5        = ~3 GB
```

Even scalar quantization alone drops you from 80GB to roughly 20GB. That fits your 96GB nodes with room to spare.

### Recommended quantization path

**Step 1: Scalar quantization (int8). Start here.**

Works with every embedding model. Less than 1% accuracy loss typical. 4x memory reduction.

```json
PUT /collections/{collection_name}
{
  "vectors": {
    "size": 1536,
    "distance": "Cosine",
    "on_disk": true
  },
  "quantization_config": {
    "scalar": {
      "type": "int8",
      "quantile": 0.99,
      "always_ram": true
    }
  }
}
```

The critical settings:

- `always_ram: true` keeps the small quantized vectors in RAM for fast search
- `on_disk: true` on the full vectors pushes originals to mmap/disk
- Rescoring against full vectors is enabled by default, preserving accuracy

**Step 2: If scalar is not enough, go to 4-bit or 2-bit.**

These provide 8x and 16x compression respectively, with moderate accuracy impact (1-5%). They sit between scalar and binary and work with any model.

**Step 3: If you use OpenAI, Cohere, Jina, or Gemini embeddings, binary quantization is an option.**

32x compression, but ONLY with compatible models. You MUST enable oversampling (3-5x) and rescoring, otherwise recall drops to around 70%. With rescoring it recovers to 95-98%.

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
      "oversampling": 3.0
    }
  }
}
```

Do NOT use binary quantization if your model has fewer than 384 dimensions or was not trained with cosine similarity.

Docs: https://qdrant.tech/documentation/guides/quantization/

## Also Consider: FP16 for On-Disk Vectors

Qdrant supports storing vectors as float16 on disk. This halves disk usage with negligible accuracy impact for retrieval. It stacks with quantization: use FP16 for the full on-disk vectors and int8 (or smaller) for the in-RAM quantized copy. This reduces rescoring I/O since the full vectors being read from disk are half the size.

Docs: https://qdrant.tech/documentation/concepts/vectors/

## Check for Hidden Memory Consumers

Before assuming the HNSW index is the only problem:

1. **Payload indexes on high-cardinality fields.** If you have text or keyword indexes on fields with millions of unique values, those eat RAM too. Remove indexes on fields you do not filter by. Use keyword index type instead of full-text for high-cardinality strings.

2. **Segment optimization.** After changing quantization or storage config, Qdrant needs to re-optimize segments. Until optimization completes, both old (unquantized) and new (quantized) data may coexist in memory. Monitor the optimization progress and expect a temporary memory spike during the transition.

3. **"I enabled quantization but memory didn't decrease."** This usually means `always_ram` is not set, so both original and quantized vectors compete for memory. Or the collection has not been optimized yet after the config change. Verify `always_ram: true` and trigger segment optimization.

## Kubernetes-Specific Recommendations

1. **Set memory requests lower than limits.** This gives the kernel room to manage the mmap page cache. A common pattern: request 60GB, limit 90GB on a 96GB node.

2. **Set up alerting at 75-80% memory utilization.** Do not wait for OOM. Use Qdrant's Prometheus metrics endpoint (`/metrics`) with your existing k8s monitoring stack.

3. **Do NOT shard prematurely.** If quantization + mmap gets you under 80% memory on a single node, stay on a single node. Sharding adds network overhead, operational complexity, and does not help if the problem is data size per shard. Only shard when a single node truly cannot hold the data after optimization, or when QPS exceeds single-node capacity (typically 200-500+ QPS).

Docs: https://qdrant.tech/documentation/guides/monitoring/

## Action Plan for Your SRE Team

| Priority | Action | Expected Impact | Downtime |
|----------|--------|----------------|----------|
| P0 (today) | Enable mmap (`on_disk: true`) | Stops OOM kills immediately | Rolling restart |
| P1 (this week) | Apply scalar quantization with `always_ram: true` | 4x memory reduction (80GB to ~20GB) | Re-optimization period, no downtime |
| P1 (this week) | Set k8s memory requests < limits | Lets kernel manage page cache properly | Pod restart |
| P2 (next week) | Audit payload indexes, remove unused ones | Frees additional RAM | None |
| P2 (next week) | Add Prometheus alerting at 75% memory | Prevents future surprises | None |
| P3 (evaluate) | Try 4-bit or binary quantization if scalar is insufficient | 8-32x reduction | Re-optimization period |
| P3 (evaluate) | Enable FP16 for on-disk full vectors | 2x disk savings, faster rescoring | Re-optimization period |

The combination of mmap + scalar quantization should take you from 80GB resident to roughly 20GB resident, giving you 4x the headroom on the same 96GB nodes. No new hardware needed.
