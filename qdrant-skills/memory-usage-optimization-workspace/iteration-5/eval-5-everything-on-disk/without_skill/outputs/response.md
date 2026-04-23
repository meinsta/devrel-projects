# Why Is Each Qdrant Instance Using 20 GB of RAM Despite Everything Being on Disk?

## Setup Summary

- 2.7 billion UUID points total
- 6 instances (so roughly 450 million points per instance)
- Vectors on disk, payloads on disk, HNSW on disk
- Each instance reports ~20 GB RAM usage
- Your calculation: 460M points x 16 bytes = ~7.4 GB for ID tracker

The 20 GB figure is not a misconfiguration bug. It is explained by several components that remain in RAM regardless of on-disk settings, plus OS-level measurement behavior that inflates what you see. Here is a breakdown.

---

## Component 1: The ID Tracker (Your Calculation Is Missing Fields)

You calculated 460M x 16 bytes = 7.4 GB. That is only the `internal_to_external` mapping (the Vec<u128> storing the UUID for each internal point ID). The ID tracker has three distinct structures, all kept in required RAM:

| Mapping | Size per point | Purpose |
|---|---|---|
| `internal_to_version` | 4 bytes | Version number per point (compressed u64) |
| `internal_to_external` | 16 bytes | Internal sequential ID to UUID |
| `external_to_internal` | ~12 bytes | UUID to internal ID (HashMap, 8 bytes key index + 4 bytes value) |

Total per point (UUID): approximately 32 bytes.

For 460 million points:

```
460,000,000 x 32 bytes = 14.7 GB
```

This is the documented figure from Qdrant's large-scale search tutorial, which measured ~12.4 GB for 400 million points after the v1.13.5 optimization that reduced ID tracker memory by approximately 2x. Before that release, the same dataset consumed closer to 25 GB just for the ID tracker.

So your 7-8 GB estimate was using only the UUID storage field. The actual ID tracker floor for your workload is around 14-15 GB per instance, not 7-8 GB.

---

## Component 2: What "Everything on Disk" Actually Means

Setting `on_disk: true` for vectors, payloads, and HNSW does not mean those structures use zero RAM. It means they are stored in memory-mapped files (mmap). The OS page cache will load recently accessed pages into RAM automatically as queries run. This is OS-level caching behavior, not Qdrant consuming heap memory.

The distinction Qdrant's own documentation draws is:

- **Required (data) memory**: Cannot be evicted. Process crashes if this is exhausted. Includes the ID tracker and quantized vectors (if any).
- **Cache memory**: Backed by mmap, managed by the OS page cache. This includes the HNSW graph and original vectors when on-disk. The OS will evict these pages under memory pressure, causing slower queries instead of crashes.

When you read "20 GB" from `top`, `htop`, or container memory metrics, the RSS (Resident Set Size) figure includes both categories. After a period of query traffic, the OS fills available RAM with hot HNSW pages and vector data. That is the correct and intended behavior. The system is not leaking memory.

---

## Component 3: HNSW Graph Pages in the Page Cache

Even with `hnsw_config.on_disk: true`, the HNSW graph will populate the page cache with hot nodes during search. For 460M points with default `m=16`, the raw HNSW graph size is roughly:

```
460M points x 16 links x 4 bytes per link x ~1.2 (level multiplier) = ~35 GB on disk
```

The most-traversed entry-point nodes and upper-layer graph nodes will be hot in the OS page cache. On a freshly started instance with cold cache, RAM usage looks lower. After search traffic, you will see it climb toward the 15-25 GB range just from HNSW page cache warming. This is normal and beneficial for performance.

---

## Component 4: Payload Indexes Stay in RAM

This is the most commonly missed source of unexpected RAM use. From the Qdrant documentation:

> "Those payload values that are involved in filtering and are indexed remain in RAM."

`on_disk_payload: true` stores raw payload values in RocksDB on disk. But every payload field index (created via `create_payload_index`) loads its index structure into required RAM regardless of the payload storage setting. If you have indexed payload fields, those indexes contribute to RAM usage in proportion to the number of distinct values and total points indexed. For 460M points with even a modest indexed field (e.g., a category or tenant ID), this can add gigabytes.

---

## Component 5: Per-Shard Overhead

Each shard carries fixed overhead: a Write-Ahead Log (WAL, default 32 MB per shard), segment metadata, and optimizer state. With many shards per instance, this multiplies. On large machines Qdrant auto-selects a higher `default_segment_number` (sometimes 8-12 per collection), each with its own WAL and metadata structures. This adds hundreds of MB to a few GB depending on your shard count.

---

## Putting the Numbers Together

For one instance with 460M UUID points, a realistic breakdown:

| Component | Approximate RAM |
|---|---|
| ID tracker (required) | 14-15 GB |
| Payload indexes (if any indexed fields) | 1-5 GB depending on fields |
| Per-shard WAL and metadata | 0.5-2 GB |
| HNSW page cache (hot nodes, post-warmup) | 3-8 GB (evictable) |
| Quantized vectors in RAM (if used with always_ram) | varies |
| OS/process baseline | 0.5-1 GB |

The 20 GB figure at steady state is entirely consistent with 14-15 GB of required ID tracker memory plus 4-6 GB of page cache for HNSW hot nodes and OS overhead.

---

## Will Doubling the Replication Factor to 2 Double RAM per Instance?

Short answer: not necessarily per instance, but the total cluster RAM doubles.

How replication works in Qdrant:

- A replication factor of 2 creates 2 physical copies of every shard.
- Those copies are distributed across different nodes. Qdrant's documentation explicitly states: "it is advised to make sure the hardware can host the additional shard replicas beforehand" and confirms that replication factor 2 doubles physical shard count.
- Each node hosts a subset of the total shards. The replicas land on different nodes than the primaries.

What this means for your setup:

With 6 instances and replication factor 2, you now have twice as many physical shards total, but they are distributed across 6 nodes. Depending on how your collection is configured (number of shards vs. number of nodes), each node could end up hosting roughly twice as many shards as before, which would double per-node RAM usage. Or, if you scale out to 12 nodes simultaneously, per-node RAM stays approximately the same.

The critical variable is the ratio of total shards to nodes:

- Same 6 nodes, replication factor 2: each node likely hosts ~2x the shard count, so per-node RAM approaches ~40 GB.
- 12 nodes with replication factor 2: each node hosts roughly the same number of shards as before, per-node RAM stays near 20 GB.

The ID tracker memory is not shared between replicas. Each replica shard has its own ID tracker in RAM. This is the dominant component that scales linearly with replication.

---

## What You Can Do to Reduce Required RAM

1. **Verify your Qdrant version is 1.13.5 or later.** This release halved ID tracker memory usage. If you are on an older version, upgrading alone could cut ID tracker RAM from ~28 GB to ~14 GB per instance.

2. **Audit payload indexes.** Run a collection info check and look at `indexed_vectors_count` and payload index schemas. If you have indexed fields that you do not use for filtering, drop them.

3. **Check `default_segment_number`.** On large machines, Qdrant may auto-configure 8-12 segments per collection. Reducing this to 4-6 lowers per-shard overhead.

4. **Understand your RAM measurement.** Before treating the 20 GB as pathological, check how much of it is RSS anonymous (heap, required) vs. RSS file-backed (page cache, evictable). On Linux, `/proc/<pid>/smaps_rollup` gives you `Rss`, `Anonymous`, and `File` breakdowns. The file-backed portion is the HNSW and vector page cache. That portion shrinking under memory pressure is normal and safe.

5. **If you want to reduce HNSW page cache footprint**, reduce the `m` parameter on your HNSW config. Lower `m` reduces graph connectivity per point and shrinks the graph on disk, which means fewer pages cached. Trade-off is slightly lower recall.

6. **For replication scaling**, add nodes proportionally rather than increasing replication factor on a fixed cluster, if RAM is the constraint.

---

## Sources

- [Minimal RAM you need to serve a million vectors - Qdrant](https://qdrant.tech/articles/memory-consumption/)
- [Large-Scale Search - Qdrant](https://qdrant.tech/documentation/tutorials-operations/large-scale-search/)
- [Capacity Planning - Qdrant](https://qdrant.tech/documentation/guides/capacity-planning/)
- [Database Optimization FAQ - Qdrant](https://qdrant.tech/documentation/faq/database-optimization/)
- [Storage - Qdrant](https://qdrant.tech/documentation/concepts/storage/)
- [Distributed Deployment - Qdrant](https://qdrant.tech/documentation/guides/distributed_deployment/)
- [High RAM Usage with Large Collection - Discussion #4826](https://github.com/orgs/qdrant/discussions/4826)
- [Which type of ID will consume less memory? - Discussion #7072](https://github.com/orgs/qdrant/discussions/7072)
- [Optimize immutable id tracker mapping - PR #6023](https://github.com/qdrant/qdrant/pull/6023)
- [Mutable in-memory ID tracker without RocksDB - PR #6150](https://github.com/qdrant/qdrant/pull/6150)
- [Payload Index - Qdrant](https://qdrant.tech/documentation/concepts/indexing/)
- [Vector Search Resource Optimization Guide - Qdrant](https://qdrant.tech/articles/vector-search-resource-optimization/)
- [Qdrant 1.11 Release - The Vector Stronghold](https://qdrant.tech/blog/qdrant-1.11.x/)
