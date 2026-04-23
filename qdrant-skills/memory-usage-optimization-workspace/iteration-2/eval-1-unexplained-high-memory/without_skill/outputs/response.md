# Diagnosing Unexplained High Memory: 460M Vectors, 20GB Per Instance

## The Short Answer

Your 7-8GB estimate only counts raw vector bytes. Qdrant stores six additional structures in memory that your baseline calculation misses entirely. Once you account for all of them, 20GB per instance is consistent with default configuration settings. Nothing is leaking. Nothing is broken. Qdrant is doing exactly what it is configured to do.

---

## Your Baseline Calculation and Why It Falls Short

You calculated:

```
460,000,000 points / 6 instances = ~76.7M points per instance
76.7M * 16 bytes = ~1.17GB raw vectors per instance
```

Even with the standard Qdrant 1.5x overhead multiplier applied to raw vectors:

```
1.17GB * 1.5 = ~1.76GB
```

That still lands nowhere near 20GB. The multiplier in Qdrant's official documentation is a rough estimate intended to cover metadata and temporary segments during optimization. It does not include the HNSW graph, payload storage, payload indexes, ID mapping structures, WAL, or OS page cache attribution. Let's go through each contributor.

---

## The Six Hidden Memory Consumers

### 1. HNSW Graph Index

This is almost certainly your largest single surprise. Qdrant builds an HNSW (Hierarchical Navigable Small World) graph for approximate nearest-neighbor search. Each node in the graph stores connections to neighboring nodes. Each connection is a 4-byte integer.

With the default `m=16` setting, each point can have up to 16 connections at the base layer and additional connections at upper layers. In practice, the average is roughly `m * 2` connections per node when accounting for the bidirectional nature of the graph construction.

Memory estimate per instance with `m=16`:

```
76.7M points * 16 connections * 4 bytes per connection = ~4.92GB
```

With the multilayer structure of HNSW (upper layers are sparse, but they exist), the real figure lands closer to 5-6GB for the graph alone per instance.

If your collection was configured with `m=32` (common for higher-recall use cases), double that estimate to 10-12GB just for the graph.

The HNSW graph lives in RAM by default. It is not moved to disk unless you explicitly configure `hnsw_config.on_disk: true`.

### 2. ID Mapping Tables

Every point in Qdrant has:
- An external ID (the UUID or integer you assigned, stored as u128: 16 bytes)
- An internal sequential ID (u64: 8 bytes)
- A version number (u64: 8 bytes)

The mappings between these must be held in memory for fast lookup during updates, deletions, and search result construction.

Memory estimate per instance:

```
76.7M points * (16 + 8 + 8) bytes = ~2.45GB
```

Practically, because of alignment and data structure overhead in Rust's hash maps, this number can run 20-30% higher than the raw byte calculation.

### 3. Payload Storage

Unless you explicitly set `on_disk: true` for payload storage when creating the collection, all payload data lives in RAM. Even moderate payloads compound quickly at this scale.

If your points carry an average payload of 100 bytes (a few string fields, a timestamp, a category label), that is:

```
76.7M points * 100 bytes = ~7.14GB per instance
```

Even a "minimal" payload of 20 bytes adds 1.4GB per instance. Check your actual average payload size. This is the most variable factor in your calculation and the one most likely to be dramatically underestimated.

### 4. Payload Field Indexes

If you created field indexes on any payload fields for filtering (for example, indexing a `category` or `user_id` field), Qdrant keeps all values for those indexed fields in RAM regardless of whether payload storage itself is set to on-disk. This is documented behavior: once a field index exists, Qdrant preserves all values of that field in RAM permanently.

A high-cardinality indexed field (millions of unique values like user IDs) can add hundreds of MB to multiple GB on top of the base payload storage.

### 5. Segment Structures and WAL

Qdrant organizes data internally into segments. During normal operation, it maintains:
- One or more immutable segments (the indexed, compacted data)
- At least one mutable segment (accepting new writes)
- A Write-Ahead Log (WAL) for crash recovery

The WAL default capacity is 32MB per shard, but there are additional in-memory buffers for the mutable segment. During active ingestion this balloon, but you stopped ingestion a week ago, which means this is not the primary culprit for your sustained 20GB. However, if optimization has not fully completed since ingestion stopped, temporary segments from the optimizer may still be consuming memory.

### 6. OS Page Cache Attributed to the Qdrant Process

This is the most counterintuitive contributor. When you look at process memory in `htop`, `top`, or your container runtime's memory metrics, the reported RSS (Resident Set Size) includes memory-mapped file pages that the OS has cached for Qdrant. Even if Qdrant configured something as `on_disk` storage, the OS aggressively caches those pages in RAM as long as free memory is available.

This means your monitoring tool may be reporting 20GB because the OS has cached 20GB worth of Qdrant's data files into page cache and is attributing it to the process. The process does not require that 20GB to function, but it will use whatever RAM is available for caching. If you needed to run another process, the OS would evict those pages.

You can verify this by checking the split between RSS anonymous memory and RSS file-backed memory on your Linux hosts:

```bash
cat /proc/<qdrant-pid>/status | grep -E "VmRSS|RssAnon|RssFile|RssShmem"
```

If `RssFile` (file-backed, including mmap pages) is large and `RssAnon` matches your expected footprint, your actual hard memory requirement is much lower than reported.

---

## Putting the Numbers Together

Here is a realistic breakdown for a single instance holding ~76.7M points with default settings and a modest payload:

| Component | Estimate |
|---|---|
| Raw vectors (16 bytes each) | ~1.2GB |
| HNSW graph (m=16, default) | ~5.0GB |
| ID mapping tables | ~2.5GB |
| Payload storage (100 bytes avg) | ~7.1GB |
| Payload field indexes (2-3 fields) | ~1.0GB |
| Segment/WAL overhead | ~0.5GB |
| OS page cache (mmap vectors/index) | variable |
| **Total** | **~17-18GB** |

Add OS page cache attribution and you are comfortably at 20GB. The math resolves completely once you include what the documentation's 1.5x multiplier leaves out.

---

## What to Do Next

### Step 1: Check Your Actual HNSW m Value

Inspect your collection configuration:

```
GET /collections/{collection_name}
```

Look at `config.params.hnsw_config.m`. If it is above 16, your graph memory is correspondingly larger. If you do not need maximum recall, reducing `m` from 32 to 16 roughly halves graph memory.

### Step 2: Measure Actual Payload Size

Run a sample query and inspect point payloads to estimate average payload bytes per point. Multiply by your per-instance point count. This is often the biggest surprise.

### Step 3: Move the HNSW Graph to Disk

If search latency allows slight degradation, enable on-disk HNSW:

```json
PATCH /collections/{collection_name}
{
  "hnsw_config": {
    "on_disk": true
  }
}
```

This moves the graph from RAM to memory-mapped disk files. The OS will still cache hot portions in page cache, but your hard RAM requirement drops by 5-10GB per instance.

### Step 4: Move Payload to Disk

If payload filtering is not latency-critical:

```json
"on_disk_payload": true
```

Set this at collection creation time (it cannot be changed after creation without recreating the collection).

### Step 5: Distinguish Page Cache from True RSS

Before tuning anything, check whether reported memory is actual hard requirement or OS page cache. Drop the page cache momentarily on one node and observe whether the process actually reduces memory footprint or whether it rebuilds page cache from disk immediately. This tells you whether you have a true memory problem or a monitoring interpretation problem.

### Step 6: Consider Scalar Quantization

Your vectors are already 16 bytes, which is unusual. Clarify what datatype you are using. If they are float32 (4 bytes * 4 dimensions = 16 bytes, meaning 4-dimensional vectors), quantization does not help much. If "16 bytes" means you are storing 16 uint8 values (16-dimensional byte vectors), you are already compact. But if by "16-byte vectors" you mean something like UUID-derived embeddings, reconsider whether your vector configuration matches your intended use case.

---

## Summary

Your 7-8GB estimate was too low because it only counted raw vector bytes. The actual memory in use breaks down to: raw vectors (~1.2GB), HNSW graph (~5GB with default m=16), ID mapping structures (~2.5GB), payload storage (~7GB assuming modest payloads), field indexes, and segment overhead. These components together produce the 17-20GB figure you are observing. Nothing is wrong. This is expected behavior under default configuration for a collection of this scale.

The highest-leverage optimizations, in order of likely impact, are: enabling `hnsw_config.on_disk: true`, auditing and potentially reducing payload size, reducing `m` if recall permits, and verifying that reported memory includes OS page cache before concluding you have a real problem.
