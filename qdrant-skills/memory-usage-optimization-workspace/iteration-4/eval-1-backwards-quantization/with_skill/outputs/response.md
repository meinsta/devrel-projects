# Diagnostic Report: Scalar Quantization Not Reducing Memory in embeddings-archive

## Cluster Inspection Results

Connected to `https://94214c31-6930-4f9f-9f33-ec90c15a76c0.eu-west-2-0.aws.cloud.qdrant.io:6333` and pulled the full collection config via `GET /collections/embeddings-archive`.

**Raw collection info (actual response from cluster):**

```json
{
  "status": "green",
  "optimizer_status": "ok",
  "indexed_vectors_count": 0,
  "points_count": 200,
  "segments_count": 2,
  "config": {
    "params": {
      "vectors": {
        "size": 1536,
        "distance": "Cosine",
        "on_disk": false
      },
      "shard_number": 1,
      "replication_factor": 1,
      "on_disk_payload": true
    },
    "hnsw_config": {
      "m": 16,
      "ef_construct": 100,
      "full_scan_threshold": 10000,
      "on_disk": false
    },
    "optimizer_config": {
      "deleted_threshold": 0.2,
      "vacuum_min_vector_number": 1000,
      "default_segment_number": 0,
      "memmap_threshold": null,
      "indexing_threshold": 10000,
      "flush_interval_sec": 5
    },
    "quantization_config": {
      "scalar": {
        "type": "int8",
        "always_ram": false
      }
    }
  },
  "payload_schema": {}
}
```

**Cluster version:** 1.16.3 (confirmed via `/telemetry`)

**Collections on this cluster:** 12 total (embeddings-archive plus 11 products-{locale} collections)

## What Went Wrong: Two Problems

### Problem 1 (primary): `always_ram: false` on quantized vectors

The quantization config has `always_ram: false`. This is the core misconfiguration.

Scalar quantization compresses float32 vectors (4 bytes per dimension) into int8 (1 byte per dimension), achieving a 4x size reduction. But quantization alone does not control what lives in RAM. That is controlled by two separate flags working together:

- `quantization_config.scalar.always_ram: true` forces the quantized (small) vectors to stay pinned in RAM for fast candidate selection during HNSW search.
- `params.vectors.on_disk: true` moves the original float32 vectors off-RAM. They are read from disk only during rescoring.

With `always_ram: false` (the current setting), the quantized vectors are treated like any other mmap'd file. The OS decides whether to keep them in RAM. No memory is guaranteed to be freed. The original float32 vectors are also still on-RAM (`on_disk: false`). Both the originals and the quantized copies compete for the same page cache. Net result: memory footprint is the same or larger than before quantization was enabled, because now there are two copies of the data.

The reduction only happens when the small quantized copy is pinned in RAM (`always_ram: true`) and the large original is pushed off-RAM (`on_disk: true`). These two settings must be applied together.

### Problem 2 (secondary): `indexed_vectors_count: 0` means quantization has not run yet

The collection has 200 points. The `indexing_threshold` in the optimizer config is 10,000. Qdrant applies quantization during the HNSW indexing step. Indexing only triggers when a segment exceeds `indexing_threshold` points.

With 200 points and a threshold of 10,000, the optimizer will never trigger indexing. `indexed_vectors_count: 0` confirms no vectors have been quantized. The quantization config exists in the collection schema but has not been applied to any actual data on disk yet.

This means there are two problems stacked: even if `always_ram` were set correctly, the quantized vectors do not exist yet because the optimizer has not run indexing.

## Phase 2 Classification

This matches the "Quantization no-op" pattern (Phase 3C in the diagnostic skill):

- Optimizer is not running (confirmed: `optimizer_status: ok`, zero running optimizations via `/metrics`)
- Data memory has not dropped because: (a) `always_ram: false` means no forced-resident savings, and (b) `indexed_vectors_count: 0` means quantization has not been applied to any segment
- Original vectors are not on disk (`on_disk: false`), so the OS caches the full float32 data

## How to Fix

Two changes are required. Apply both together.

### Change 1: Fix the quantization config

Set `always_ram: true` so quantized vectors are pinned in RAM:

```http
PATCH /collections/embeddings-archive
Content-Type: application/json
api-key: <your-api-key>

{
  "quantization_config": {
    "scalar": {
      "type": "int8",
      "always_ram": true
    }
  }
}
```

### Change 2: Move original vectors to disk

Set `on_disk: true` on the vector params so the large float32 originals are read from disk only during rescoring:

```http
PATCH /collections/embeddings-archive
Content-Type: application/json
api-key: <your-api-key>

{
  "vectors": {
    "on_disk": true
  }
}
```

### Change 3: Lower indexing_threshold so quantization actually runs

The collection has 200 points and will never exceed 10,000. Lower the threshold below the current point count so the optimizer triggers indexing and applies quantization:

```http
PATCH /collections/embeddings-archive
Content-Type: application/json
api-key: <your-api-key>

{
  "optimizer_config": {
    "indexing_threshold": 100
  }
}
```

After applying all three changes, the optimizer will rebuild segments with quantization applied. Monitor via:

```http
GET /collections/embeddings-archive
```

Wait until `optimizer_status` returns to `"ok"` and `indexed_vectors_count` matches `points_count`. Then check actual memory impact via `/telemetry`, not `htop` or `docker stats`. Those tools show data memory plus OS page cache combined, which is misleading.

## What to Expect After the Fix

For this specific collection (200 points, 1536 dimensions):

- Current float32 footprint: 200 * 1536 * 4 bytes = 1.2 MB vector data
- After fix: quantized int8 vectors pinned in RAM at ~300 KB, originals on disk
- Effective reduction: ~4x on vector data

At 200 points, the absolute numbers are small. The same misconfiguration at millions of vectors leaves GBs of float32 data in RAM despite quantization being enabled. The pattern is identical regardless of scale.

## What NOT to Do

Do not keep `always_ram: false` as a way to save additional RAM beyond what quantization provides. When `always_ram: false`, searches must load quantized vectors from disk for candidate scoring. Every search query triggers page faults. Search latency and CPU overhead spike. This is one of the most damaging misconfigurations in Qdrant.

Do not assume the quantization config in the schema means quantization has run. Always check `indexed_vectors_count`. If it is 0, the optimizer has not applied quantization to any data yet.

## Summary of Findings

| Field | Current value | Correct value | Impact of current |
|---|---|---|---|
| `quantization_config.scalar.always_ram` | `false` | `true` | No forced-resident savings; quantized vectors not pinned |
| `params.vectors.on_disk` | `false` | `true` | Original float32 vectors stay in RAM/page cache |
| `indexed_vectors_count` | `0` | should equal `points_count` | Quantization has not been applied to any data |
| `optimizer_config.indexing_threshold` | `10000` | `100` (or below point count) | Indexing never triggers at 200 points |

All four issues must be addressed. The quantization config is correct in type (`int8`) but wrong in `always_ram`. The optimizer has never run indexing. The original vectors are not on disk. Together these three deficiencies explain why enabling scalar quantization produced no observable memory reduction.
