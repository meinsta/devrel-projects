---
name: qdrant-search-speed-optimization
description: "Diagnoses and fixes slow Qdrant search. Use when someone reports 'search is slow', 'high latency', 'queries take too long', 'low QPS', 'throughput too low', 'filtered search is slow', or 'search was fast but now it's slow'. Also use when search performance degrades after config changes or data growth."
---

# What to Do When Qdrant Search Is Too Slow

First determine whether the problem is latency (single query speed) or throughput (queries per second). These pull in opposite directions. Getting this wrong means tuning the wrong knob.

- Understand the tradeoff [Latency vs throughput](https://qdrant.tech/documentation/guides/optimize/#balancing-latency-and-throughput)


## Single Query Too Slow (Latency)

Use when: individual queries take too long regardless of load.

- Reduce `hnsw_ef` at query time (64-128 is usually sufficient) [Fine-tuning search](https://qdrant.tech/documentation/guides/optimize/#fine-tuning-search-parameters)
- Enable scalar int8 quantization with `always_ram=true` [Scalar quantization](https://qdrant.tech/documentation/guides/quantization/#scalar-quantization)
- Enable io_uring for disk-heavy workloads on Linux [io_uring](https://qdrant.tech/articles/io_uring/)
- Check for unmerged segments after uploads [Merge optimizer](https://qdrant.tech/documentation/concepts/optimizer/#merge-optimizer)
- Use oversampling + rescore for high-dimensional vectors [Search with quantization](https://qdrant.tech/documentation/guides/quantization/#searching-with-quantization)


## Can't Handle Enough QPS (Throughput)

Use when: system can't serve enough queries per second under load.

- Reduce segment count (`default_segment_number` to 2) [Maximizing throughput](https://qdrant.tech/documentation/guides/optimize/#maximizing-throughput)
- Use batch search API instead of single queries [Batch search](https://qdrant.tech/documentation/concepts/search/#batch-search-api)
- Enable quantization to reduce CPU cost [Scalar quantization](https://qdrant.tech/documentation/guides/quantization/#scalar-quantization)
- Add replicas to distribute read load [Replication](https://qdrant.tech/documentation/guides/distributed_deployment/#replication)


## Filtered Search Is Slow

Use when: filtered search is significantly slower than unfiltered. Most common SA complaint after memory.

- Create payload index on the filtered field [Payload index](https://qdrant.tech/documentation/concepts/indexing/#payload-index)
- Use `is_tenant=true` for high-cardinality tenant fields [Tenant index](https://qdrant.tech/documentation/concepts/indexing/#tenant-index)
- Try ACORN algorithm for very restrictive filters (v1.13+) [Filterable HNSW](https://qdrant.tech/documentation/concepts/indexing/#filterable-hnsw-index)
- If payload index was added after HNSW build, trigger re-index to create filterable subgraph links


## Search Was Fast, Now It's Slow

Use when: search performance degraded without obvious config changes. Classic pattern after bulk uploads.

- Check optimizer status (most likely still running after upload) [Optimizer monitoring](https://qdrant.tech/documentation/concepts/optimizer/#optimization-monitoring)
- Check segment count (unmerged segments from bulk upload) [Merge optimizer](https://qdrant.tech/documentation/concepts/optimizer/#merge-optimizer)
- Check for cache eviction from competing processes
- Do NOT make config changes while the optimizer is running


## What NOT to Do

- Set `always_ram=false` on quantization (disk thrashing on every search)
- Put HNSW on disk for latency-sensitive production (only for cold storage)
- Increase segment count for throughput (opposite: fewer = better)
- Create payload indexes on every field (wastes memory)
- Blame Qdrant before checking optimizer status
