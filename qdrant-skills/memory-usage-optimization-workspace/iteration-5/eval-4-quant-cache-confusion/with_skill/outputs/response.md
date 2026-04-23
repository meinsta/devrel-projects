# Scalar Int8 Quantization: Why Memory Didn't Go Down

## Quick Routing

Your symptom maps directly to Phase 3C: "Quantization didn't reduce memory." The optimizer shows `ok`, which rules out the most common cause (optimization still in progress). This points to a measurement problem, not a configuration problem.

---

## The Core Issue: You Are Reading the Wrong Number

Scalar int8 quantization reduces **forced-resident data memory** by approximately 4x. It does **not** reduce OS page cache.

Tools like `htop`, `top`, and `docker stats` report data memory plus OS page cache combined. Your node almost certainly shows a high combined number, but the actual Qdrant data memory may have already dropped substantially after quantization.

**Your configuration is correct:**

- `always_ram=true` for quantized vectors: correct. This keeps the small int8 vectors resident for fast candidate selection.
- `on_disk=true` for original float32 vectors: correct. This moves the large originals to disk, only read during rescoring.

The optimizer status `ok` confirms quantization and optimization completed successfully.

---

## How to Verify: Check Telemetry, Not htop

Call the telemetry endpoint on your cluster:

```
GET /telemetry
```

Look at two numbers:

- `app.memory_usage`: total process memory (data + OS page cache combined)
- `collections.{name}.memory_usage`: actual Qdrant data memory for the collection

If `collections.{name}.memory_usage` dropped after quantization but `app.memory_usage` did not, quantization worked. The unchanged total is OS page cache filling available RAM. This is expected and healthy behavior.

---

## Memory Accounting for Your Collection

For 5 million vectors at 768 dimensions with scalar int8 quantization and `always_ram=true` on originals set to `on_disk=true`:

**What stays in RAM (forced-resident data):**

| Component | Calculation | Approximate size |
|---|---|---|
| Quantized vectors (int8) | 5M x 768 x 1 byte | ~3.8 GB |
| HNSW graph | included in 1.5x multiplier | part of base estimate |
| ID tracker | 5M x 16 bytes (UUID) | ~80 MB |
| Collection overhead | fixed | ~14 MB |

**What moves to disk (mmap'd, OS-cached opportunistically):**

| Component | Size |
|---|---|
| Original float32 vectors | 5M x 768 x 4 bytes = ~15.3 GB |

The OS will cache as much of the mmap'd original vector file as fits in available RAM. This is why total reported memory looks unchanged: the OS is caching the on-disk originals in the page cache. The critical difference is that page cache is evictable under memory pressure. Data memory is not.

---

## What Could Actually Still Be Wrong

If telemetry confirms data memory did NOT drop, work through this checklist:

1. **Optimizer still running during your check.** Even though current status is `ok`, did you check immediately after enabling quantization? The optimizer may have just finished. Check again now.

2. **Config applied to the wrong collection or shard.** Confirm `quantization_config` is present in `GET /collections/{name}` and shows `scalar` type with `always_ram: true`.

3. **Segments not yet re-optimized.** The optimizer re-writes segments to apply quantization. Check `segments_count` in collection info. If many small segments exist (greater than 20 per shard), the optimizer may still be merging them.

4. **HNSW graph is still in RAM.** By default, HNSW is always in RAM. At 768 dimensions with 5M vectors, the HNSW graph alone can consume 4-8 GB. If you need to reduce this further, set `hnsw_config.on_disk=true`. Be aware this trades memory for query latency.

5. **Payload indexes consuming RAM.** Check `payload_schema` in collection info. Full-text indexes are especially large (2-5x the indexed text size). Keyword indexes on UUID fields can be GBs. If you have indexes on fields not used in filters, remove them. For infrequently filtered fields, use per-index `on_disk=true`.

6. **Payload data in RAM.** If you have large payloads and have not set `on_disk_payload=true`, payload data sits in RAM. This is separate from quantization.

---

## Do Not Do This

Do not set `always_ram=false` on the quantization config to try to save additional RAM. This forces the quantized vectors to be read from disk on every search candidate evaluation. The result is extreme disk I/O, high CPU usage, and query performance collapse. The quantized vectors are small (about 3.8 GB for your collection) and must stay in RAM to be useful.

---

## Summary

| What you see | What it means |
|---|---|
| `htop` or `docker stats` unchanged | OS page cache filling available RAM after originals moved to disk. Normal. |
| Optimizer status `ok` | Quantization completed successfully. |
| Configuration correct | `always_ram=true` on quantized, `on_disk=true` on originals is the right setup. |

**Next step:** Call `GET /telemetry` and compare `app.memory_usage` vs `collections.{name}.memory_usage`. If data memory dropped ~4x, quantization is working. If data memory did not drop, check HNSW config, payload indexes, and segment count.
