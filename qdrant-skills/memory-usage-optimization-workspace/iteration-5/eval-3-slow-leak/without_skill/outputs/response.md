# Qdrant Slow Memory Growth: Diagnosis and Resolution

## Short Answer

This is almost certainly not a classic memory leak in the software engineering sense. The pattern you describe (10-12 MB/day growth, immediate drop on restart, slow re-accumulation) is consistent with well-understood Qdrant behaviors related to OS page cache accumulation from memory-mapped files, jemalloc allocator fragmentation, and background optimizer activity. Each of these is addressable. A true allocator-level leak would not drop cleanly on restart; the fact that it does suggests the memory is being accounted for correctly by the OS and is reclaimed when the process exits.

---

## What Is Actually Happening

### 1. mmap Page Cache Accumulation (Most Likely Cause)

Qdrant stores vectors and indices in memory-mapped files. The Linux kernel uses "page cache" to satisfy reads from those files, and this page cache is counted as resident memory (RSS) for the Qdrant process by tools like `htop`, `top`, and `docker stats`. Every search query causes the kernel to load more pages from disk into the page cache. Over days of query traffic, even light query traffic, the page cache fills with frequently-touched pages.

This is by design. The [Qdrant documentation](https://qdrant.tech/documentation/faq/database-optimization/) explicitly states: "Unused RAM is wasted RAM." Qdrant intentionally lets the kernel cache as much data as possible to minimize search latency.

When you restart the process, the OS-level page cache associated with that process is released, which explains the immediate drop. The cache then rebuilds as queries resume.

**How to confirm this is the cause:** Run the following on the host before and after dropping the page cache:

```bash
# Record current Qdrant RSS
cat /proc/$(pgrep qdrant)/status | grep VmRSS

# Drop only the page/slab cache (safe on a running system)
sync; echo 1 > /proc/sys/vm/drop_caches

# Record Qdrant RSS again immediately after
cat /proc/$(pgrep qdrant)/status | grep VmRSS
```

If the RSS drops significantly after dropping caches (without restarting Qdrant), page cache accumulation is confirmed as the dominant factor.

### 2. jemalloc Allocator Fragmentation

Qdrant uses jemalloc as its allocator. jemalloc can retain "dirty pages" (deallocated memory that has not yet been returned to the OS) in thread-local caches and arena free lists. This causes the process RSS to grow slowly above what is strictly in active use, even with no incoming data. This fragmentation accumulates gradually.

Qdrant exposes jemalloc internals through its `/metrics` endpoint (added in the [PR #5266](https://github.com/qdrant/qdrant/pull/5266)):

- `app_info_memory_active` - bytes in active jemalloc pages
- `app_info_memory_allocated` - bytes actually allocated to live objects
- `app_info_memory_resident` - bytes in physically resident pages

**Fragmentation ratio:** `(memory_active - memory_allocated) / memory_active`

If this ratio is above 20-30% and growing, fragmentation is a contributor. A ratio climbing over weeks without stabilizing is a sign jemalloc is not returning dirty pages to the OS quickly enough.

### 3. Background Optimizer Activity

Even with no new ingestion, Qdrant's background optimizers can be active. The Vacuum Optimizer runs when deleted-point ratios exceed thresholds (default: 20% of a segment). Optimization involves creating new segments, building indices, and temporarily holding both old and new segment data in memory simultaneously. If your collection sees any deletes or updates (which internally are delete-then-insert), the optimizer will periodically rebuild segments. Each rebuild creates temporary memory pressure that does not always fully resolve before the next cycle.

Additionally, WAL (Write-Ahead Log) segments accumulate on disk and in memory until flushed. The default `flush_interval_sec` controls how aggressively WAL is cleared. If WAL segments are not being flushed promptly, they contribute to slow RSS growth.

### 4. Known Cache Hygiene Issue (Addressed in Later Versions)

A specific bug tracked in [PR #6323](https://github.com/qdrant/qdrant/pull/6323) ("disk cache hygiene") identified that delayed mmap population was leaving pages in the OS cache even when the corresponding segments were dropped during optimization. This caused cache pages to accumulate without bound. The fix introduced explicit `populate()` and `clear_cache()` (using `posix_fadvise(POSIX_FADV_DONTNEED)`) to properly release pages when segments are closed. If this fix is not present in your specific 1.13 patch version, it is a direct cause of the growth you are seeing.

Check whether [PR #6396](https://github.com/qdrant/qdrant/pull/6396) ("Clear disk cache after read") is included in your exact patch release. Both PRs address the same class of cache pollution.

---

## Diagnostic Steps (No Cluster Connection Required)

Work through these in order:

1. **Check your exact version.** `GET /` on any node returns the version. Confirm the full semver (e.g., 1.13.2 vs 1.13.6). Earlier 1.13 patches may not include the cache hygiene fixes.

2. **Check jemalloc metrics.** `GET /metrics` and look for `app_info_memory_*` fields. Calculate fragmentation. If allocated is well below active/resident, fragmentation is a factor.

3. **Check optimizer activity.** `GET /telemetry` returns optimizer statistics per collection. Look at `optimizations.optimized_segments_count` over time. Active optimization during your growth window points to optimizer-driven memory pressure.

4. **Check WAL config.** Review `storage.wal.wal_capacity_mb` (default 32) and `storage.optimizers.flush_interval_sec` in your `config.yaml`. Large WAL capacity with a long flush interval means more data buffered in memory.

5. **Drop the page cache and observe.** If RSS drops immediately and the rate of re-growth matches your query rate, the behavior is entirely normal page cache accumulation, not a bug.

6. **Check collection optimizer thresholds.** `GET /collections/{collection_name}` and inspect `config.optimizer_config`. If `deleted_threshold` is low or collections have frequent soft-deletes, optimizer churn is contributing.

---

## Remediation Options

### If page cache accumulation is the primary cause (expected behavior)

This is not a problem to eliminate - it is a feature. The memory is being used productively to speed up queries and will be reclaimed by the OS if other processes need it. However, if you are operating close to node memory limits:

- Configure `on_disk: true` in `hnsw_config` for each collection to stop the HNSW graph from being held in RAM.
- Set `on_disk: true` in vector parameters to push raw vectors to mmap storage.
- Apply memory limits at the Docker/Kubernetes level. Qdrant respects OS memory pressure and will not OOM-kill itself; it will allow the kernel to evict page cache pages as needed.

```yaml
# Collection-level config (per-collection update)
hnsw_config:
  on_disk: true

vectors:
  size: 1536
  distance: Cosine
  on_disk: true
```

### If jemalloc fragmentation is a significant factor

Qdrant 1.13 does not expose a built-in way to force jemalloc to return dirty pages to the OS on a schedule. Options:

- **Upgrade to a newer version.** Later releases (1.15+) include improvements to memory pressure handling and more aggressive dirty page returns.
- **Tune the restart cadence.** A scheduled weekly restart (during off-peak hours) is a legitimate operational strategy for fragmentation cleanup in the interim.
- **Set `MALLOC_CONF`** environment variable to configure jemalloc dirty page retention: `MALLOC_CONF=dirty_decay_ms:1000,muzzy_decay_ms:1000` will cause jemalloc to return dirty pages to the OS within 1 second of deallocation rather than holding them in arena free lists. This is safe to apply at the container/pod level.

### If optimizer churn is contributing

```yaml
# config.yaml optimizer settings
storage:
  optimizers:
    flush_interval_sec: 5        # more frequent WAL flushes
    vacuum_min_vector_number: 1000  # don't vacuum tiny segments
    deleted_threshold: 0.3       # raise threshold to reduce vacuum frequency
```

### If you are on an early 1.13 patch

Upgrade to the latest 1.13.x patch release. The [v1.13.6 release](https://github.com/qdrant/qdrant/releases/tag/v1.13.6) includes several performance and correctness fixes. If the cache hygiene PRs landed in a mid-cycle patch, upgrading within the 1.13 series may resolve the growth without a major version upgrade.

---

## What This Is Not

- **Not a data leak or corruption risk.** Memory growth of this kind does not indicate data integrity problems.
- **Not a Rust memory safety issue.** Qdrant is written in safe Rust; the growth mechanisms are all expected OS/allocator behavior.
- **Not likely to cause an OOM crash** unless you are running with very tight memory limits relative to your dataset size, in which case the proper fix is to configure `on_disk` storage rather than to fight the page cache.

---

## Summary Table

| Cause | Rate | Drops on Restart? | Requires Fix? |
|---|---|---|---|
| mmap page cache accumulation | Proportional to query rate | Yes (OS reclaims) | No (expected behavior) |
| jemalloc fragmentation | Slow, unpredictable | Yes | Optional (MALLOC_CONF tuning) |
| Background optimizer segment churn | Bursty | Yes | Only if causing OOM |
| WAL accumulation | Steady until flush | Yes | Only if flush_interval is too high |
| Cache hygiene bug (pre-fix) | Slow, steady | Yes | Yes (upgrade patch version) |

---

## Sources

- [Memory Leak using Qdrant in a concurrent scenario - Issue #5250](https://github.com/qdrant/qdrant/issues/5250)
- [disk cache hygiene - Pull Request #6323](https://github.com/qdrant/qdrant/pull/6323)
- [Clear disk cache after read - Pull Request #6396](https://github.com/qdrant/qdrant/pull/6396)
- [Report memory usage in metrics and telemetry - PR #5266](https://github.com/qdrant/qdrant/pull/5266)
- [RAM usage is incorrect in v1.12.1 - Issue #5268](https://github.com/qdrant/qdrant/issues/5268)
- [High RAM Usage with Large Collection - Discussion #4826](https://github.com/orgs/qdrant/discussions/4826)
- [Minimal RAM you need to serve a million vectors - Qdrant](https://qdrant.tech/articles/memory-consumption/)
- [Database Optimization FAQ - Qdrant](https://qdrant.tech/documentation/faq/database-optimization/)
- [Storage documentation - Qdrant](https://qdrant.tech/documentation/concepts/storage/)
- [Capacity Planning - Qdrant](https://qdrant.tech/documentation/guides/capacity-planning/)
- [Optimizer documentation - Qdrant](https://qdrant.tech/documentation/concepts/optimizer/)
- [Memory usage is not reduced by deleting points - Issue #3273](https://github.com/qdrant/qdrant/issues/3273)
- [Qdrant v1.13.6 Release Notes](https://github.com/qdrant/qdrant/releases/tag/v1.13.6)
- [Monitoring and Telemetry - Qdrant](https://qdrant.tech/documentation/guides/monitoring/)
