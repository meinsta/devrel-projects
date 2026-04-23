# Qdrant OOM Crashes: Options Beyond Adding More RAM

## 1. Switch HNSW to Memory-Mapped (mmap) Storage

This is the single highest-impact change. By default, Qdrant loads the entire HNSW graph into RAM. You can switch to memory-mapped files, which lets the OS manage what stays in RAM vs. gets paged to disk.

In your collection config (or at creation time):

```json
{
  "hnsw_config": {
    "on_disk": true
  }
}
```

You can also move the vectors themselves to disk:

```json
{
  "optimizers_config": {
    "memmap_threshold": 20000
  }
}
```

Or explicitly set vector storage to on-disk:

```json
{
  "vectors": {
    "size": 1536,
    "distance": "Cosine",
    "on_disk": true
  }
}
```

With `on_disk: true` for HNSW, the graph is memory-mapped. The OS kernel will keep hot pages in the page cache and evict cold ones. Your 80GB index might only need 15-30GB of actual RSS depending on access patterns. This is the most effective lever you have.

**Trade-off**: Latency increases, especially for cold queries. Expect p99 to go up. For many workloads, p50 barely changes because the hot portion of the graph fits in RAM anyway.

## 2. Enable Quantization

Quantization compresses vectors in memory, which directly reduces both vector storage and the effective size of HNSW graph traversals.

**Scalar quantization** (simplest, good first step):

```json
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

This cuts vector memory by roughly 4x (float32 to int8). Setting `always_ram: true` keeps the quantized vectors in RAM for fast rescoring while the full vectors live on disk.

**Binary quantization** (most aggressive, 32x compression):

```json
{
  "quantization_config": {
    "binary": {
      "always_ram": true
    }
  }
}
```

Binary quantization works well with high-dimensional embeddings (1536+ dims, especially OpenAI embeddings). It does not work well with lower-dimensional models. Always test recall before deploying.

**Product quantization** (middle ground):

```json
{
  "quantization_config": {
    "product": {
      "compression": "x16",
      "always_ram": true
    }
  }
}
```

The pattern to use: keep quantized vectors in RAM (`always_ram: true`), put full vectors on disk (`on_disk: true`), and use oversampling + rescoring to maintain recall:

```json
{
  "search_params": {
    "quantization": {
      "rescore": true,
      "oversampling": 2.0
    }
  }
}
```

## 3. Reduce HNSW Graph Parameters

The HNSW index size is proportional to `m` (number of connections per node). The default `m=16` means each point stores 16 outgoing edges per layer. Reducing this directly shrinks the graph.

```json
{
  "hnsw_config": {
    "m": 8,
    "ef_construct": 100
  }
}
```

Halving `m` from 16 to 8 roughly halves the HNSW graph memory. You lose some recall at low `ef` search values, but for many workloads `m=8` or `m=12` is sufficient. Benchmark with your actual queries before committing.

**Note**: Changing `m` requires a full re-index. Plan for downtime or do a rolling migration.

## 4. Shard Across Multiple Nodes (Distributed Mode)

Instead of fitting everything on one 96GB node, distribute collections across multiple smaller nodes.

```json
{
  "shard_number": 6,
  "replication_factor": 2
}
```

With 6 shards across 3 nodes, each node holds roughly 2 shards worth of data. Your 80GB index becomes ~13GB per shard per node. This also improves query throughput since shards are searched in parallel.

You can also use **resharding** on an existing collection if you started with fewer shards than you need.

## 5. Use Payload Indexes and Filtering to Reduce Search Scope

If your queries always filter by tenant, date range, or category, make sure you have payload indexes:

```json
{
  "field_name": "tenant_id",
  "field_schema": "keyword"
}
```

With indexed filtering, Qdrant can skip large portions of the HNSW graph entirely, reducing the working set that needs to be in memory.

## 6. Collection-Level Optimizations

**Separate collections by access pattern.** If you have hot data (last 30 days) and cold data (archive), split them into separate collections. Keep the hot collection in RAM, put the cold collection on disk with mmap.

**Set indexing thresholds** to control when Qdrant builds the HNSW index:

```json
{
  "optimizers_config": {
    "indexing_threshold": 20000
  }
}
```

Segments below this threshold use a brute-force flat index (no HNSW overhead).

## 7. Configure Resource Limits Properly in k8s

Even after the above changes, make sure your k8s resource config is correct:

```yaml
resources:
  requests:
    memory: "60Gi"
  limits:
    memory: "88Gi"  # Leave headroom below 96Gi for system
```

Set Qdrant's internal memory limits in the config:

```yaml
# qdrant config
storage:
  performance:
    max_search_threads: 4  # Limit parallelism to reduce peak memory
```

Also, **do not set memory limits equal to requests**. Leave headroom. OOM kills happen when RSS hits the limit, and mmap page cache does not count against RSS (which is one more reason to use mmap).

## 8. Use Disk-Backed Snapshots for Recovery

Since you are crashing frequently, make sure you have snapshot-based recovery rather than relying on the node staying up:

```bash
# Create snapshots on a schedule
curl -X POST "http://localhost:6333/collections/{collection}/snapshots"
```

Store snapshots on a PersistentVolume or S3. This way, when a node OOM-kills, the replacement pod can restore from snapshot rather than re-indexing from scratch.

## Recommended Action Plan (Priority Order)

1. **Immediate**: Enable `on_disk: true` for HNSW. This alone should drop RSS from 80GB to a fraction of that. This is the single biggest win.
2. **Same day**: Enable scalar quantization with `always_ram: true` and move full vectors to disk.
3. **This week**: Review and potentially lower the `m` parameter if recall allows it.
4. **This sprint**: Evaluate sharding if single-node mmap latency is not acceptable for your SLAs.
5. **Ongoing**: Set up proper k8s memory requests/limits with headroom, and automate snapshot backups.

The combination of mmap HNSW + scalar quantization + vectors on disk typically reduces RAM usage by 80-90% compared to a fully in-memory deployment, at the cost of some latency increase that is acceptable for most production workloads.
