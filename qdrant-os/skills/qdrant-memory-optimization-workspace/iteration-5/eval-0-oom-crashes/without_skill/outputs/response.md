# Qdrant OOM Crashes: Options Beyond Adding More RAM

You have several concrete levers to pull here, ranging from quick config changes to architectural shifts. Let me walk through them in order of impact and implementation effort.

## 1. Switch HNSW Index to On-Disk (Memmap) Storage

This is likely your single biggest win. By default, Qdrant loads the entire HNSW graph into RAM. You can switch to memory-mapped (mmap) storage for the index, which moves the graph to disk and lets the OS page in only the portions actively being queried.

Set this at the collection level:

```json
PUT /collections/{collection_name}
{
  "optimizers_config": {
    "indexing_threshold": 20000
  },
  "hnsw_config": {
    "on_disk": true
  }
}
```

With `on_disk: true` for HNSW, the index lives on disk and the OS manages a page cache. On NVMe SSDs, the latency hit is often surprisingly small (maybe 1.5-3x slower for search, depending on your access patterns). This alone could drop your 80GB HNSW footprint to a few GB of resident memory.

## 2. Use On-Disk Vectors (Memmap) Too

If your vectors themselves are also in RAM, you can move those to disk as well:

```json
PUT /collections/{collection_name}
{
  "vectors": {
    "": {
      "size": 768,
      "distance": "Cosine",
      "on_disk": true
    }
  }
}
```

Or update an existing collection:

```json
PATCH /collections/{collection_name}
{
  "vectors": {
    "": {
      "on_disk": true
    }
  }
}
```

Combined with on-disk HNSW, this can reduce your memory footprint by 80-90%. The tradeoff is latency, but for many production workloads, the difference is tolerable, especially with NVMe.

## 3. Quantization: Scalar or Product Quantization

Quantization compresses vectors in memory, reducing their footprint significantly while keeping them in RAM for fast access.

**Scalar Quantization (SQ)** converts float32 vectors to int8, giving you roughly a 4x reduction in vector memory:

```json
PUT /collections/{collection_name}
{
  "vectors": {
    "size": 768,
    "distance": "Cosine"
  },
  "quantization_config": {
    "scalar": {
      "type": "int8",
      "always_ram": true
    }
  }
}
```

**Binary Quantization (BQ)** is even more aggressive (32x compression) but works best with certain embedding models (OpenAI's ada-002, Cohere embeddings). Not great for all models.

**Product Quantization (PQ)** offers tunable compression ratios. More complex to configure, but useful if scalar quantization is not aggressive enough.

The `always_ram: true` flag keeps the quantized vectors in RAM for the initial coarse search, then does rescoring against the full vectors on disk. This gives you the best of both worlds: small RAM footprint with high accuracy.

## 4. Enable Rescoring with Oversampling

When using quantization, you lose some precision. Compensate by oversampling and rescoring:

```json
POST /collections/{collection_name}/points/search
{
  "vector": [0.1, 0.2, ...],
  "limit": 10,
  "params": {
    "quantization": {
      "rescore": true,
      "oversampling": 2.0
    }
  }
}
```

This searches 2x more candidates using the quantized (cheap) vectors, then rescores the top candidates against full-precision vectors. Accuracy stays very close to uncompressed while memory stays low.

## 5. Shard Across Multiple Nodes (Distributed Mode)

If you have 80GB of HNSW on a single node, you can split the collection across multiple smaller nodes instead of using one big node.

```json
PUT /collections/{collection_name}
{
  "vectors": {
    "size": 768,
    "distance": "Cosine"
  },
  "shard_number": 6,
  "replication_factor": 2
}
```

With 6 shards across 3 nodes, each node holds roughly 2 shards, and each shard's HNSW index is proportionally smaller. This distributes the memory pressure across your cluster. In Kubernetes, this is straightforward with the Qdrant Helm chart.

## 6. Reduce HNSW `m` and `ef_construct` Parameters

The HNSW graph's memory consumption is directly proportional to `m` (number of edges per node). The default `m=16` is good for accuracy, but if you can tolerate slightly lower recall, reducing it saves significant memory:

```json
PUT /collections/{collection_name}
{
  "hnsw_config": {
    "m": 8,
    "ef_construct": 100
  }
}
```

Halving `m` from 16 to 8 roughly halves the HNSW graph size. You will lose some recall, so benchmark this against your quality requirements. For many use cases (especially with rescoring), `m=8` is completely fine.

## 7. Set Memory Limits and Resource Requests Properly in K8s

Make sure your Qdrant pods have proper resource limits that leave headroom for the OS page cache:

```yaml
resources:
  requests:
    memory: "70Gi"
  limits:
    memory: "88Gi"  # leave ~8GB for OS and page cache
```

If you are using mmap (on-disk) storage, do NOT set the memory limit too tight. The OS page cache needs breathing room. Mmap-backed storage will show high RSS in some metrics tools, but that memory is reclaimable. Make sure your OOM killer threshold accounts for this. Some teams set `oom_score_adj` to avoid the kernel killing Qdrant prematurely when page cache is inflated.

## 8. Use Payload Indexes Selectively

If you have large payloads stored alongside your vectors, those eat RAM too. Move large payloads to on-disk storage:

```json
PUT /collections/{collection_name}
{
  "on_disk_payload": true
}
```

Only keep payload fields that you actively filter on as indexed. Unindexed payloads on disk have near-zero memory cost.

## 9. Consider Collection Aliases and Lifecycle Management

If you have collections with stale or rarely-accessed data, consider:

- Archiving old collections to on-disk-only configurations
- Using collection aliases to swap between hot (in-RAM) and warm (on-disk) versions
- Deleting unused indexes or collections that are consuming memory silently

## Recommended Strategy for Your Situation

Given that you are crashing at 80GB HNSW on 96GB nodes, here is what I would do in order:

1. **Immediate (stop the bleeding):** Enable `on_disk: true` for HNSW. This alone should drop your resident memory from 80GB to a manageable level. Requires a collection reindex, so plan for some downtime or do a rolling update with replicas.

2. **Short term:** Add scalar quantization with `always_ram: true` and rescoring. This keeps search fast while cutting vector memory 4x.

3. **Medium term:** Evaluate your shard count and consider distributing across more nodes if query latency with on-disk HNSW is not meeting your SLOs.

4. **Ongoing:** Reduce `m` if recall benchmarks allow it, move payloads to disk, and set proper K8s resource limits with page cache headroom.

The combination of on-disk HNSW, scalar quantization with rescoring, and on-disk payloads can easily bring an 80GB footprint down to under 10GB of resident RAM, with search latency that is still in the low tens of milliseconds on NVMe storage.
