# Fixing Qdrant OOM Crashes on 96GB K8s Nodes

## Understanding the Problem

With an HNSW index consuming 80GB on 96GB nodes, you have virtually no headroom. The HNSW graph is proportional to vector count (roughly 1.5x the raw vector data size), and it resists being paged out because graph traversal requires random access across the entire structure. Once query traffic warms up the OS page cache, RSS climbs past the node limit and the OOM killer fires. Three crashes in a week is consistent with this pattern.

You have several options, ordered from "stop the bleeding now" to "long-term capacity plan."

## Option 1: Enable mmap Storage (Immediate, Stops Crashes)

Move vector data to disk-backed memory-mapped files. The OS manages what stays resident in RAM versus on disk based on access patterns. This stops OOM kills immediately because Qdrant's RSS is no longer bounded by your full dataset size.

**Trade-off:** Latency may increase for cold queries (vectors not in page cache). For most workloads the hot working set is a small fraction of total data, so the impact is moderate (expect 50-500ms range instead of single-digit ms).

**What to do:** Update your collection's vector storage configuration to use mmap. This is a non-destructive change. Qdrant will rebuild the storage in the background.

Docs: https://qdrant.tech/documentation/concepts/storage/

## Option 2: Apply Scalar Quantization (4x Memory Reduction)

Scalar quantization converts each float32 vector element (4 bytes) to int8 (1 byte). This gives a 4x reduction in vector data size with less than 1% accuracy loss for most embedding models. It works with any model.

**Back-of-napkin math for your situation:**
- If your HNSW index is 80GB with float32 vectors, scalar quantization brings the vector portion down to roughly 20GB.
- With HNSW overhead (1.5x multiplier), you'd land around 30GB total, well within your 96GB nodes.

**Key setting:** Set `always_ram=true` on the quantized vectors. This keeps the small quantized representations in RAM for fast initial search. Full-resolution vectors stay on disk (via mmap) and are loaded only for rescoring the top candidates. This gives you both low memory and low latency.

Docs: https://qdrant.tech/documentation/guides/quantization/#scalar-quantization

## Option 3: Binary Quantization (32x Reduction, Model-Dependent)

If you're using OpenAI, Cohere embed-v3, Jina v2+, or Gemini embeddings, binary quantization compresses vectors by 32x (each float becomes a single bit). For your 80GB index, this would drop vector data to roughly 2.5GB.

**Critical requirements:**
- You must enable rescoring against full vectors (kept on disk via mmap). Without rescoring, recall drops to around 70%. With rescoring and 3-5x oversampling, recall recovers to 95-98%.
- This does not work well with most open-source models, especially those with low dimensionality (under 384 dims).

Docs: https://qdrant.tech/documentation/guides/quantization/#binary-quantization

## Option 4: Move HNSW Index to mmap

Starting from Qdrant 1.x, you can also memory-map the HNSW graph itself (not just the vectors). Since the graph is what's eating your 80GB, this directly addresses the problem. The OS will keep hot graph pages in memory and page out cold ones.

**Trade-off:** Graph traversal involves 200+ random hops. If a significant portion of the graph is not in the page cache, each hop hits disk, pushing latency into the hundreds of milliseconds or seconds range. Combining this with quantization (so the graph is smaller) mitigates the issue.

Docs: https://qdrant.tech/documentation/concepts/storage/

## Option 5: Check Payload Indexes

If memory keeps growing even with stable vector counts, payload indexes may be a hidden contributor. Indexes on high-cardinality string fields (e.g., user IDs, URLs) consume significant RAM.

**What to do:**
- Audit which payload fields have indexes enabled.
- Remove indexes on fields you don't actually filter by.
- For high-cardinality string fields, switch from full-text to keyword index.

Docs: https://qdrant.tech/documentation/concepts/indexing/#payload-index

## Recommended Action Plan

1. **Right now (stop the crashes):** Enable mmap storage for vectors. This is the fastest path to stability. No data loss, no accuracy impact, just a latency trade-off.

2. **This week (reduce the footprint):** Apply scalar quantization with `always_ram=true`. This brings your memory requirement from ~80GB down to ~20-30GB, giving you massive headroom on 96GB nodes.

3. **This week (set up alerting):** Configure alerts at 75-80% memory utilization so you catch problems before the OOM killer does. Qdrant exposes Prometheus metrics for this. Docs: https://qdrant.tech/documentation/guides/monitoring/

4. **Next sprint (evaluate binary quantization):** If your embedding model supports it, binary quantization gives 32x reduction. Test accuracy with rescoring on a staging collection first.

5. **Audit payload indexes:** Remove any indexes on fields you aren't filtering by in production queries.

## Memory Estimation Formula

For future capacity planning:

```
RAM needed = vectors * dimensions * bytes_per_element * 1.5 (HNSW overhead)

bytes_per_element:
  float32 (no quantization) = 4 bytes
  int8 (scalar quantization) = 1 byte
  binary quantization        = 0.125 bytes
```

Example for 1536-dim embeddings (OpenAI) at 10M vectors:
- No quantization: ~92 GB
- Scalar quantization: ~23 GB
- Binary quantization: ~3 GB

Rule of thumb: keep utilization under 80% of node RAM to leave headroom for query processing, payload indexes, and traffic spikes.
