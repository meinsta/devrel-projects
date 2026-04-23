# Qdrant OOM Crashes: Options Beyond Adding More RAM

You have a real problem: 80GB HNSW index on 96GB nodes leaves almost nothing for the OS, Qdrant's other memory needs, payload indexes, or query buffers. Three OOM kills in a week means you are operating right at the edge. Here are your concrete options, ordered roughly by impact and ease of deployment.

---

## 1. Switch HNSW to Memory-Mapped (mmap) Storage

This is the single highest-impact change you can make. By default, Qdrant loads the entire HNSW graph into RAM. You can switch it to memory-mapped mode, which lets the OS page parts of the index in and out of RAM on demand.

**How to configure it:**

```json
PUT /collections/{collection_name}
{
  "optimizers_config": {
    "memmap_threshold": 10000
  }
}
```

Or in your collection config:

```yaml
storage:
  hnsw_index:
    on_disk: true
```

Setting `on_disk: true` for the HNSW index tells Qdrant to use mmap instead of loading the full graph into memory. Your RAM usage will drop dramatically because the OS will only keep hot pages resident. The tradeoff is latency: queries that hit cold pages will take a disk read. On NVMe SSDs, this penalty is usually acceptable (single-digit milliseconds added). On spinning disks, do not bother.

**What to expect:** RAM usage for the HNSW index drops from 80GB to whatever your OS decides to keep warm, typically 20-40% of the full index depending on your query patterns. Latency p50 stays similar, p99 goes up.

---

## 2. Enable On-Disk Vectors

If your vectors themselves are also in memory, you can move them to disk too:

```json
PUT /collections/{collection_name}
{
  "vectors": {
    "on_disk": true
  }
}
```

This is separate from the HNSW index. The vectors (the actual float arrays) can be stored on disk and accessed via mmap. Combined with on-disk HNSW, your total memory footprint drops to a fraction of the dataset size.

---

## 3. Quantization

Quantization reduces the memory footprint of vectors by compressing them from float32 to smaller representations. Qdrant supports several options:

### Scalar Quantization (easiest, least risk)

Converts float32 vectors to int8. Cuts vector memory by 4x.

```json
PUT /collections/{collection_name}
{
  "quantization_config": {
    "scalar": {
      "type": "int8",
      "quantile": 0.99,
      "always_ram": true
    }
  }
}
```

Setting `always_ram: true` keeps quantized vectors in RAM for fast scoring while the full vectors live on disk. This gives you the best of both worlds: fast approximate scoring in RAM, with optional rescoring from disk vectors for precision.

### Binary Quantization (most aggressive)

Converts each float32 dimension to a single bit. 32x memory reduction. Works well for high-dimensional models (768+), particularly those from OpenAI or Cohere. Not great for lower-dimensional models or models where subtle distance differences matter.

### Product Quantization (PQ)

More complex, configurable compression ratio. Good middle ground but slower to build the index.

**Recommendation for your situation:** Start with scalar quantization plus `always_ram: true`. Keep full vectors on disk. You get ~4x vector memory reduction while maintaining good recall (typically 99%+ with rescoring enabled).

---

## 4. Increase Sharding Across Nodes

If you have a single collection on one node holding the full 80GB index, shard it across multiple nodes. Each node then holds a fraction of the data.

```json
PUT /collections/{collection_name}
{
  "shard_number": 6,
  "replication_factor": 2
}
```

With 6 shards across, say, 3 nodes, each node holds 2 shards (roughly 27GB of HNSW index each). This also parallelizes search across nodes.

Note: You cannot reshard an existing collection without recreating it. Plan for a migration window or use collection aliases to do a blue-green swap.

---

## 5. Tune HNSW Parameters to Reduce Graph Size

The HNSW graph size is directly proportional to the `m` parameter (number of edges per node). Default is typically `m=16`.

```json
PUT /collections/{collection_name}
{
  "hnsw_config": {
    "m": 8,
    "ef_construct": 100
  }
}
```

Reducing `m` from 16 to 8 cuts the graph memory roughly in half. The tradeoff is recall: you need higher `ef` at search time to compensate, which adds latency. For many use cases, `m=8` with `ef=128` at query time gives nearly identical recall to `m=16` with `ef=64`.

This requires a full reindex, so plan accordingly.

---

## 6. Set Kubernetes Memory Limits and Qdrant's Internal Limits Properly

Your OOM kills might be partly a Kubernetes resource limit issue. Make sure:

- **Pod memory limit** is set below the node's total RAM, leaving room for the OS and kubelet (at least 4-8GB for a 96GB node).
- **Pod memory request** equals the limit, so the pod gets a Guaranteed QoS class and does not get evicted first.

```yaml
resources:
  requests:
    memory: "85Gi"
  limits:
    memory: "88Gi"
```

Also check if Qdrant's internal `storage.performance.max_search_threads` is set too high. Each search thread allocates temporary buffers. Reducing concurrency reduces peak memory.

---

## 7. Use Collection-Level Payload and Vector Storage Separation

If you have large payloads stored inline, move them to on-disk storage:

```json
PUT /collections/{collection_name}
{
  "on_disk_payload": true
}
```

Payloads can consume surprising amounts of RAM when stored inline, especially if you have large text fields or metadata per point.

---

## 8. Consider Multiple Smaller Collections

If your data has natural partitions (by tenant, by date, by category), split it into multiple smaller collections. Benefits:

- Each collection's HNSW index is independent and smaller.
- You can put different collections on different nodes.
- You can archive or delete old collections without rebuilding the main index.
- Qdrant supports searching across multiple collections in a single request.

---

## Recommended Action Plan for Your Situation

Given that you are actively crashing in production, here is the priority order:

1. **Immediate (today):** Enable `on_disk: true` for HNSW index and vectors on your collection. This is a config change that triggers background optimization. Monitor as segments get rewritten. This alone should bring your RSS from ~80GB+ down to whatever the OS caches (likely 30-40GB with warm queries).

2. **This week:** Enable scalar quantization with `always_ram: true`. This keeps a compressed copy of vectors in RAM for fast initial scoring and rescores from disk for final results. Your effective RAM usage drops further.

3. **Next sprint:** Evaluate your `m` parameter and shard count. If you can tolerate a reindex, reducing `m` and increasing shard count across nodes will give you long-term headroom.

4. **Ongoing:** Set up proper memory monitoring. Track Qdrant's `/metrics` endpoint for `app_info_memory_active_bytes` and segment-level stats. Alert at 80% of your pod memory limit, not at OOM.

---

## Quick Reference: Memory Impact Estimates

| Change | Estimated RAM Reduction | Latency Impact | Rebuild Required? |
|---|---|---|---|
| HNSW on_disk (mmap) | 60-80% of graph | p99 +2-10ms (NVMe) | No (background) |
| Vectors on_disk | 100% of vector storage | p99 +5-15ms | No (background) |
| Scalar quantization (int8) | 75% of vector storage | Minimal with rescore | No (background) |
| Binary quantization | 97% of vector storage | Noticeable, model-dependent | No (background) |
| Reduce m from 16 to 8 | ~50% of graph | Needs higher ef | Yes (full reindex) |
| Increase shard count | Linear with shard count | Network overhead | Yes (recreate collection) |
| On-disk payloads | Depends on payload size | Payload fetch slower | No (background) |

The combination of mmap HNSW + on-disk vectors + scalar quantization should bring your 80GB footprint down to under 15-20GB of active RAM while keeping search quality high. That gives you massive headroom on your 96GB nodes.
