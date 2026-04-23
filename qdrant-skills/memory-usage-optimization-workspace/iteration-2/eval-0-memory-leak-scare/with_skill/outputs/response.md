# Memory Diagnosis: Is This a Leak?

**Short answer:** Almost certainly not a memory leak. This is a well-known pattern caused by OS page cache behavior, not a Qdrant defect.

---

## What Is Actually Happening

The symptom you describe (RAM grows steadily, drops on restart, cluster still functional at 80%) matches the OS page cache pattern almost exactly.

Qdrant stores vectors using memory-mapped files (mmap). The operating system caches these mmap file reads in the page cache to avoid repeated disk I/O. As your application queries data over time, the OS fills available RAM with cached pages. This looks identical to a memory leak in tools like `htop`, `docker stats`, or cloud monitoring dashboards because they report RSS (Resident Set Size), which includes page cache.

When you restart the cluster, the cache is cold. The OS has not yet cached anything, so memory reads as low. Over the next days, query traffic warms the cache back up, and reported memory climbs again. This cycle is exactly what you are observing.

**This is not a bug. This is the OS working correctly.**

---

## How to Confirm

Check the Qdrant metrics endpoint directly rather than relying on OS-level memory metrics:

```
GET http://<your-qdrant-host>:6333/metrics
```

Look for two specific values:

- `app_info` (confirms version)
- Memory metrics that separate actual data allocation from cache

The Qdrant web dashboard also separates "data usage" from "cache" in its memory display. If your actual data usage is significantly below 80%, you are looking at cache, not a leak.

A genuine leak would show Qdrant's internal allocator consuming memory independent of query activity, and it would not have a clean ceiling near 80% like you describe. It would keep climbing past 100% until the process is OOM-killed.

---

## When This Would Be a Genuine Leak

There is a known slow-growth pattern in older Qdrant versions: 1-12 MB of growth per day even with zero query activity and zero ingestion. That pattern is a genuine leak. It is distinguishable from your situation in two ways:

1. The growth rate is very slow (megabytes per day, not gigabytes)
2. It occurs even when the cluster receives no traffic at all

Your cluster hitting 80% of 4 GB (3.24 GB) while under query load is consistent with normal cache behavior, not this slow-leak pattern.

---

## Immediate Checks to Do

**Check 1: Verify `on_disk` configuration for your vectors.**

If vectors were configured with `on_disk: false` (or created on an older version where this was not the default), full-resolution vectors load entirely into RAM as actual allocations, not cache. This would cause genuinely high baseline memory.

```python
info = client.get_collection("your_collection_name")
print(info.config.params.vectors)
# Look for on_disk field
```

If `on_disk` is `False` or absent, this is likely a major contributor and is fixable.

**Check 2: Check quantization configuration.**

A common misconfiguration: quantized vectors set to `on_disk=True` and original full-resolution vectors left in RAM. This is backwards. The correct setup keeps quantized vectors in RAM (they are small and used for candidate selection) and moves originals to disk (they are large and only needed for rescoring).

```python
print(info.config.quantization_config)
```

**Check 3: Check collection count.**

Each collection carries 12-14 MB of baseline overhead regardless of data. If you have many collections, the overhead adds up.

```python
collections = client.get_collections()
print(len(collections.collections))
```

---

## Recommended Actions

These are ordered by expected impact.

**Action 1: Move vectors to disk, keep quantized vectors in RAM.**

This is the highest-impact change if your vectors are currently not explicitly set to `on_disk=True`.

```python
client.update_collection(
    collection_name="your_collection_name",
    vectors_config=models.VectorParamsDiff(on_disk=True),
    quantization_config=models.ScalarQuantization(
        scalar=models.ScalarQuantizationConfig(
            type=models.ScalarType.INT8,
            always_ram=True,
        ),
    ),
)
```

With this setup, Qdrant keeps only the small quantized vectors resident in RAM. Full-resolution vectors are read from disk only during rescoring. Memory use drops substantially.

**Action 2: Lower the memmap threshold if not using explicit `on_disk`.**

If you want to keep the current collection config but push segments to disk sooner:

```python
client.update_collection(
    collection_name="your_collection_name",
    optimizers_config=models.OptimizersConfigDiff(memmap_threshold=20000),
)
```

**Action 3: Move payloads to disk if they are large.**

Check whether `on_disk_payload` is enabled. Large payloads kept in RAM can contribute significantly. Before enabling this, create indexes for any fields you filter on, otherwise filtered queries will hit disk without an index and become slow.

```python
# Create index first
client.create_payload_index(
    collection_name="your_collection_name",
    field_name="your_filter_field",
    field_schema=models.KeywordIndexParams(type="keyword"),
)

# Then move payloads to disk
client.update_collection(
    collection_name="your_collection_name",
    params=models.CollectionParamsDiff(on_disk_payload=True),
)
```

**Action 4: Upgrade Qdrant if on an older version.**

Memory management has improved significantly across recent releases. If you are running anything below 1.11, upgrading alone may reduce your baseline.

---

## On the Alerting Threshold

At 80% of 4 GB, the OS page cache is full and the system is working as designed. The OS will begin evicting cache pages under memory pressure to make room for new requests. This causes a slight increase in disk I/O (cache misses) but does not cause crashes or data loss.

If you want headroom, the cleanest solution is to implement the `on_disk=True` configuration above, which reduces the actual working set and gives the page cache more room to operate. Alternatively, if this is a Kubernetes deployment, set memory limits with headroom and let the OS manage the cache within those bounds.

The cluster does not need a restart. Restarting to clear cache is trading a short-term metric improvement for a warmup period where query latency will be elevated until the cache refills.

---

## Summary

| Symptom | Likely Cause | Action |
|---|---|---|
| Memory grows after restart | OS page cache warming up | Expected behavior, see configuration fixes |
| Memory drops on restart | Cache cleared | Confirms this is cache, not data |
| Stays below crash threshold | Working set fits in RAM | Good sign, not a leak |
| Grows over days without ingestion | Cache + query activity | Normal if under query load |

The pattern you are describing does not indicate a memory leak. It indicates that your cache is filling up, which is the OS doing its job. Focus your effort on verifying the `on_disk` vector configuration and quantization setup. Those two changes will give you the most memory reduction if they are currently misconfigured.
