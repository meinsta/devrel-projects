# Advisory: RAM Growth After Data Ingestion Stopped

This is almost certainly not a memory leak in the traditional sense. The behavior you are describing matches a well-understood Qdrant pattern. Let me walk through what is likely happening and how to confirm it.

---

## What Is Probably Happening: OS Page Cache Warming

Qdrant stores vectors on disk using memory-mapped files. When queries come in, the operating system reads those vector pages from disk into RAM and keeps them there as page cache. The OS does this automatically to make future reads faster.

This cache fills up available RAM over time as different pages get accessed. From the outside, monitoring tools like `htop`, `top`, `docker stats`, and most Kubernetes memory metrics report data memory plus page cache as a single combined number. So the alert at 3.24 GB of 4 GB may be almost entirely OS cache, not Qdrant application data.

When you restart the cluster, both page cache and actual application memory are flushed. Memory drops immediately. This is the behavior you are seeing and it is consistent with cache warming, not a leak.

---

## How to Confirm: Check the Qdrant Metrics Endpoint

Before drawing any conclusions, check what Qdrant itself reports about its memory usage. Hit the `/metrics` endpoint or open the Qdrant web dashboard. Look for the breakdown between:

- **Data memory**: HNSW graph, ID tracker, payload indexes, quantized vectors with `always_ram=True`, collection overhead. This is what Qdrant actually needs to function.
- **Cache**: mmap pages the OS is holding for performance. Not required. Evicted automatically under memory pressure.

If you see something like 15-20% data memory and 60-70% cache, your node is healthy. The OS is doing exactly what it is supposed to do.

---

## What Would Actually Be Concerning

A true problematic pattern would be one of these:

**1. Actual data memory is growing.** If the Qdrant metrics show data usage (not cache) increasing over time with no ingestion, that is worth investigating. Check your collection count: each collection carries 12-14 MB of baseline overhead in RAM regardless of how much data it holds. If you have dozens of collections, that overhead alone can account for several gigabytes.

**2. Slow creep with zero traffic.** If memory grows 1-12 MB per day even with no queries and no ingestion, that is a known issue pattern in some Qdrant versions. It is not normal cache behavior. The fix is to upgrade to the latest Qdrant release. Memory management improvements ship regularly and customers have seen RAM drop immediately after upgrading.

**3. Cache is growing faster than expected.** If you have active query traffic touching many different vectors, cache will fill available RAM relatively quickly. This is expected and healthy. The OS will evict cache pages if actual memory pressure occurs. The 80% alert threshold you have may just be firing on cache, not on a real problem.

---

## The Restart Behavior Is Not Evidence of a Leak

A common assumption is: "if restarting fixes it, something must have leaked." This is not accurate in Qdrant's case. Restart flushes both cache and any application memory. Cache dropping on restart is normal. It does not distinguish between a leak and healthy cache accumulation.

Restart is also a valid operational tool. For example, you might restart a node deliberately before scaling it down to free cache and reduce footprint.

---

## What to Do Right Now

**Step 1: Check the Qdrant metrics endpoint or dashboard.** Identify the data memory vs cache split. If data memory is stable (not growing) and within a reasonable range for your collection size, you are not in danger. The 80% alert is firing on cache.

**Step 2: Estimate your expected data memory.** A rough formula:

```
data_memory = num_vectors * vector_dimension * 4 bytes * 1.5
```

The 1.5x multiplier covers the HNSW graph, segment metadata, and temporary segments. Add payload memory if payloads are in RAM: `num_points * avg_payload_bytes * 1.5`. Compare this estimate to what Qdrant reports as data usage.

**Step 3: Check collection count.** If you have many collections (dozens or more), collection overhead may be contributing meaningfully to data memory. Each collection holds 12-14 MB in RAM regardless of size.

**Step 4: If Qdrant version is not current, upgrade.** Especially if you see slow data memory growth even without traffic. Newer versions have better memory management.

---

## Adjusting Your Alerting

If investigation confirms the growth is page cache, consider updating your monitoring to alert on Qdrant's reported data memory rather than OS-level total memory. Alerting on total memory in a Qdrant deployment will produce false positives because Qdrant intentionally allows the OS to cache as much as RAM allows.

---

## Summary

| Symptom | Likely Cause | Status |
|---|---|---|
| RAM grows after ingestion stops | OS page cache warming from queries | Normal and expected |
| Memory drops on restart | Flush of both cache and app memory | Normal, not evidence of a leak |
| 80% memory alert | Alert threshold firing on combined data + cache | Likely a monitoring artifact |
| No OOM crashes | OS evicting cache under pressure | Healthy behavior |

The pattern you are describing is consistent with normal Qdrant operation. Confirm by checking the data vs cache split in `/metrics`. If data memory is stable, you do not have a memory leak and do not need to take any remediation action beyond possibly adjusting your alert thresholds.

If you share the Qdrant version you are running, the number of collections, and what the `/metrics` endpoint shows for data memory, I can give you a more specific assessment.
