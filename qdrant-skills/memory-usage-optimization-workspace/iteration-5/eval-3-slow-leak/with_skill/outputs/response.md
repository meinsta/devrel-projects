# Memory Growth Analysis: 10-12 MB/day on Qdrant v1.13

## Short Answer

This is almost certainly not a memory leak in the traditional sense, and v1.13 is relevant context. Before drawing conclusions, you need to distinguish between data memory and OS page cache. The pattern you describe (slow growth, drops on restart, resumes after) is consistent with two separate phenomena that look identical from the outside. One of them requires action; the other does not.

## What the Symptom Pattern Tells Us

Memory growing slowly then dropping on restart does NOT prove a leak. Restart flushes both actual data memory and the OS page cache. You cannot tell them apart from restart behavior alone.

Tools like `htop`, `top`, and `docker stats` report both combined. A node showing 95% memory usage might be 15% actual data and 80% cache. The growth you are seeing could be:

1. OS page cache accumulating as mmap'd vector files get accessed over time (normal and expected)
2. Actual data memory growing slowly due to a known pre-v1.13 issue (patched)
3. Both happening simultaneously

The restart behavior is consistent with all three. It does not narrow this down on its own.

## The One Call That Will Answer This

Run the telemetry endpoint on your nodes:

```
GET /telemetry
```

This is the only tool that separates data memory from OS page cache. Look at two fields:

- `app.memory_usage`: total process memory (data + cache combined, same as what htop shows)
- `collections.{name}.memory_usage`: actual data memory per collection

If the sum of collection data memory values is stable over days, and only `app.memory_usage` is climbing, the growth is OS page cache. That is normal behavior and not a problem. Cache will be evicted automatically when the OS needs the RAM for something else.

If the per-collection data memory values are themselves climbing with zero ingestion, that is the pattern to escalate.

## What v1.13 Changes

The skill documentation is explicit on this point:

> "If data memory grows with zero traffic (1-12 MB/day): known issue in versions before v1.13. Upgrade to latest. If persists on latest version, report to support with telemetry data."

The rate you describe, 10-12 MB/day, is exactly the range documented as a known pre-v1.13 slow-growth issue. You are already on v1.13, which means one of two things:

- You are seeing OS page cache growth (not the leak), and the telemetry will confirm this
- The issue persists on your specific workload or configuration, in which case Qdrant support needs your telemetry data to investigate further

Neither conclusion can be reached without running the telemetry endpoint first.

## What to Collect Before Concluding Anything

Run these in sequence and record the output at two points in time, at least 48 hours apart with no restarts in between:

**Step 1: Telemetry (data vs cache split)**
```
GET /telemetry
```

**Step 2: Collection list and count**
```
GET /collections
```
Each collection carries 12-14 MB of baseline overhead regardless of data. If you have dozens of collections, the collection overhead alone could explain the growth pattern if collections are being created and not cleaned up.

**Step 3: Per-collection config for any suspect collections**
```
GET /collections/{name}
```
Look at: segment count (`segments_count`), optimizer status, payload schema (indexes), and vector config.

**Step 4: Node metrics over time**
```
GET /metrics
```
Watch `qdrant_collections_total` over time if collection count is changing.

## Most Likely Explanations in Priority Order

1. OS page cache filling as mmap'd vector data gets accessed. Normal. Telemetry will show stable data memory with rising total memory.

2. A small number of payload indexes or full-text indexes growing in memory. Full-text indexes are a common hidden consumer at 2-5x the size of the indexed text fields. If you have indexed text fields on a collection that receives background updates (even non-vector metadata changes), this index grows in memory.

3. The pre-v1.13 slow-growth behavior persisting in your deployment. Less likely since you are on v1.13, but possible if the fix did not cover your specific case. This requires a support report with telemetry data.

4. Segment fragmentation. If a collection had past write activity and the optimizer has not finished merging segments, each segment carries its own HNSW graph and ID tracker overhead. Check `segments_count` per shard: more than 20 segments per shard suggests the optimizer is not converging.

## What to Do Now

1. Do not restart until you have captured telemetry data showing the elevated state. A clean baseline reading when memory is high is more diagnostic than one taken immediately after a restart.

2. Run `GET /telemetry` and record `app.memory_usage` alongside the sum of all `collections.{name}.memory_usage` values.

3. If data memory is stable and only total memory grows: this is cache. No action required. The node is operating correctly.

4. If data memory itself is growing on v1.13 with confirmed zero ingestion: collect the full telemetry output, version string, and collection configs, then open a report with Qdrant support. This is the documented escalation path for this exact pattern on the current version.

## What Not to Do

Do not treat the restart as evidence of a problem or a fix. It is a valid operational tool, but it masks the distinction between cache and data memory. Keep the node running in the elevated state long enough to capture the telemetry split before the next restart.

Do not tune configuration (quantization, on_disk settings, memmap thresholds) before confirming via telemetry what is actually consuming memory. Changes made without this baseline may have no effect or introduce performance regressions.
