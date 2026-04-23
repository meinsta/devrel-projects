# Qdrant Memory Growth Diagnosis: Is This a Memory Leak?

**Short answer: Almost certainly not a memory leak.** What you are describing is the expected behavior of Qdrant combined with standard OS-level memory management. Here is a detailed breakdown of what is happening and how to confirm it.

---

## What You Are Seeing

- Memory climbs to ~3.24 GB (80% of 4 GB) after ingestion stopped
- Restarting the cluster immediately drops memory back down
- Growth continues even with no new data coming in

This pattern is a classic signature of **memory-mapped file caching**, not a leak.

---

## Root Cause: mmap and the OS Page Cache

Qdrant uses memory-mapped files (`mmap`) extensively for serving vectors and payload indexes from disk. When you read data (e.g., search queries), the OS kernel loads the relevant file pages into RAM and keeps them there as long as free memory is available. This is called the **page cache**.

The OS treats page cache as "free memory that is being used productively." From the OS perspective, holding these pages is beneficial because future reads will be served from RAM instead of disk. The kernel will evict these pages when another process actually needs the RAM.

However, monitoring tools (including cloud provider dashboards and basic `free`/`top` output) often report page cache as "used" memory, which is technically accurate but functionally misleading. The memory is not "lost" and it is not growing without bound due to a bug.

Here is why memory keeps climbing even after ingestion stops:

1. Search queries continue to access vector segments on disk
2. Each newly accessed segment gets paged into RAM
3. Because you still have ~20% free RAM, the OS has no reason to evict old pages
4. Over time, more and more of the dataset gets cached, pushing utilization toward the ceiling

When you restart the cluster, the process exits, all mmap mappings are released, and the OS reclaims the page cache. Memory drops instantly. This is expected and is not recovery from a leak.

---

## How to Confirm This Is Not a Leak

There are a few things you can check to rule out a true leak:

**1. Check RSS vs. cache breakdown**

On the host running Qdrant, check:

```bash
# Look at Qdrant process RSS (Resident Set Size)
cat /proc/<qdrant_pid>/status | grep -E "VmRSS|VmPeak|VmSize"

# Check system-wide memory breakdown
free -h
```

If the majority of memory is in the `buff/cache` column of `free -h` rather than in `used`, you are looking at page cache, not a leak.

**2. Check Qdrant's own memory telemetry**

Qdrant exposes a `/metrics` endpoint (Prometheus format) and a `/telemetry` REST endpoint. Look at:

- `app_info` and `memory` fields under `/telemetry`
- `process_resident_memory_bytes` in Prometheus metrics

If Qdrant's self-reported RSS is stable and only the OS-level "used" figure is climbing, page cache is the culprit.

**3. Look at segment file sizes vs. RAM**

Qdrant stores segments under the configured `storage_path`. If the total size of your vector segment files is close to 3+ GB, it makes sense that the OS would eventually cache most of them in RAM during normal query load.

---

## What a Real Memory Leak Would Look Like

A genuine memory leak has a different signature:

- Qdrant's own RSS (not just OS-level "used") grows monotonically
- Growth continues even with zero query traffic and zero ingestion
- The process eventually crashes with OOM rather than stabilizing near a ceiling
- Memory does not release proportionally when workload decreases

None of those match what you described.

---

## What You Can Do

### Option 1: Do nothing (recommended if performance is good)

If searches are fast and you are not hitting OOM kills, the current behavior is optimal. The OS is caching your hot vectors in RAM, which is exactly what you want. The 80% figure looks alarming but the memory is working for you.

### Option 2: Limit mmap cache with `mmap_advice`

Qdrant supports configuring how aggressively it uses mmap. In your `config.yaml`, you can tune:

```yaml
storage:
  # Use on-disk payload storage to reduce RAM pressure
  on_disk_payload: true

  # Per-collection: prefer on-disk vectors for large collections
  # (set at collection creation time or via update)
```

For individual collections, you can set `on_disk` vector storage, which tells Qdrant to keep vectors on disk and rely on mmap rather than loading everything into the process heap. This shifts the memory from process heap to page cache, which is more easily reclaimed.

### Option 3: Set collection-level memmap threshold

When creating or updating a collection, you can control when Qdrant switches segments to mmap mode:

```json
{
  "optimizers_config": {
    "memmap_threshold": 20000
  }
}
```

Lowering this threshold moves more data to mmap-backed storage sooner. Combined with OS-level `vm.drop_caches` tuning, this gives you more predictable memory behavior.

### Option 4: Tune OS page cache reclaim

If you need to cap memory usage without restarting, you can drop page cache on the host:

```bash
sync && echo 1 > /proc/sys/vm/drop_caches
```

This is a one-time flush. For ongoing control, tune `vm.vfs_cache_pressure` (default 100, higher values reclaim cache more aggressively):

```bash
sysctl -w vm.vfs_cache_pressure=200
```

This is a host-level change and affects all processes, not just Qdrant.

### Option 5: Add more RAM

If your working set (hot vectors accessed regularly) is approaching 4 GB, the real fix is more RAM. The OS cache is telling you exactly how much data it wants to keep hot. Giving it room to breathe will improve query latency.

---

## Summary

| Symptom | Memory Leak | Page Cache (Your Case) |
|---|---|---|
| Memory grows over time | Yes | Yes |
| Growth stops after ingestion ends | No | Yes (once dataset is cached) |
| Restart recovers memory | Partial | Full and immediate |
| Zero-traffic growth | Yes | No |
| Process RSS matches OS "used" | Yes | No, cache is separate |

Your cluster is behaving correctly. The memory being consumed is the OS intelligently caching your vector data for fast retrieval. No code fix or patch is needed.

If you want to set a hard ceiling to prevent alerts from firing, the most practical options are: tuning `mmap_threshold` to push data to disk-backed mmap, increasing the alert threshold to ~90% (since this cache is always evictable), or provisioning more RAM to match your dataset size.

---

*Diagnosed as: expected mmap page cache accumulation, not a memory leak.*
