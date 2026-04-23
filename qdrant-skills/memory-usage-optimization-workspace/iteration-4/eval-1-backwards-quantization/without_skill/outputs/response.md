# Diagnostic Report: Scalar Quantization Not Reducing Memory in `embeddings-archive`

## Cluster Inspection Results

**Cluster:** `https://94214c31-6930-4f9f-9f33-ec90c15a76c0.eu-west-2-0.aws.cloud.qdrant.io:6333`
**Collection:** `embeddings-archive`
**Qdrant version:** 1.16.3
**Inspection date:** 2026-03-03

### Raw Collection Config (from `/collections/embeddings-archive`)

```json
{
  "status": "green",
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
      "on_disk_payload": true
    },
    "optimizer_config": {
      "deleted_threshold": 0.2,
      "vacuum_min_vector_number": 1000,
      "default_segment_number": 0,
      "max_segment_size": null,
      "memmap_threshold": null,
      "indexing_threshold": 10000,
      "flush_interval_sec": 5,
      "max_optimization_threads": null
    },
    "quantization_config": {
      "scalar": {
        "type": "int8",
        "always_ram": false
      }
    }
  }
}
```

---

## Root Cause Analysis

Two compounding problems are visible directly in the collection config.

### Problem 1: Vectors are not indexed (the critical issue)

The collection reports:

```
indexed_vectors_count: 0
points_count: 200
segments_count: 2
```

`indexed_vectors_count` is `0` despite `points_count` being `200`. This means no HNSW index has been built, and therefore no quantized index exists. Scalar quantization in Qdrant is applied at index build time. The quantized vectors are stored as part of indexed segments. If the optimizer has not yet built the index, the collection operates entirely on plain float32 vectors in unindexed (appendable) segments.

The reason the index was never built is directly visible in the optimizer config:

```json
"indexing_threshold": 10000
```

The `indexing_threshold` is set to `10000` vectors. The collection has only `200` points. Qdrant will not trigger the indexing optimizer (which builds HNSW and applies quantization) until the number of vectors in a segment crosses this threshold. With only 200 points, the optimizer never fires, so the data sits in raw float32 segments indefinitely.

This is the primary cause of the memory not dropping. The quantization config exists in metadata, but it has never been applied because no quantized index has ever been built.

### Problem 2: Original vectors are still kept in RAM

Even if the index were built, the default behavior keeps the original float32 vectors in memory for rescoring (to improve accuracy after the approximate quantized search pass). The collection has `on_disk: false` on the vector params, meaning those float32 originals are held in RAM, not memory-mapped from disk.

For maximum memory reduction you need both:
1. The quantized index to actually be built (fix Problem 1).
2. The float32 originals stored on disk rather than in RAM, so only the compact int8 index lives in memory.

---

## How Scalar Quantization Works in Qdrant

Scalar quantization converts each float32 component to int8. For a 1536-dim vector:

- Before quantization: `1536 dims x 4 bytes = 6,144 bytes per vector`
- After quantization: `1536 dims x 1 byte = 1,536 bytes per vector`

This is a 4x reduction in the quantized representation. However, by default Qdrant retains the float32 originals for rescoring. If those originals are also in RAM (`on_disk: false`), the net RAM reduction is much smaller because you are storing both copies.

---

## How to Fix It

### Fix 1: Lower the indexing threshold so the optimizer builds the index

Patch the collection's optimizer config to allow indexing at the current dataset size:

```http
PATCH /collections/embeddings-archive
{
  "optimizers_config": {
    "indexing_threshold": 100
  }
}
```

Or with the Python client:

```python
from qdrant_client import QdrantClient
from qdrant_client.models import OptimizersConfigDiff

client = QdrantClient(
    url="https://94214c31-6930-4f9f-9f33-ec90c15a76c0.eu-west-2-0.aws.cloud.qdrant.io:6333",
    api_key="<your-api-key>",
)

client.update_collection(
    collection_name="embeddings-archive",
    optimizer_config=OptimizersConfigDiff(
        indexing_threshold=100,
    ),
)
```

Setting `indexing_threshold` to `100` (below the current 200 points) causes the optimizer to detect that existing segments exceed the threshold, rebuild them as indexed segments, and apply the int8 scalar quantization. Monitor progress by polling the collection info until `indexed_vectors_count` equals `points_count` (200) and `optimizer_status` is `"ok"`.

### Fix 2: Move original vectors to disk to free RAM

Update the vector config to memory-map the float32 originals from disk instead of holding them in RAM:

```http
PATCH /collections/embeddings-archive
{
  "vectors": {
    "on_disk": true
  }
}
```

Combined with the quantized int8 index in RAM, this gives you the full memory benefit: searches run against the small in-memory int8 index, and float32 originals are loaded from disk only for the final rescoring step.

### Fix 3 (optional, maximum memory reduction): Disable rescoring

If a small accuracy trade-off is acceptable, you can tell Qdrant not to keep float32 originals at all for rescoring. Pass `"rescore": false` in your search params at query time:

```json
{
  "vector": [...],
  "limit": 10,
  "params": {
    "quantization": {
      "rescore": false
    }
  }
}
```

This means only int8 vectors are used for the entire search, with no float32 lookup. RAM footprint is minimized at the cost of approximate result accuracy.

---

## Expected Memory Savings After Fix

For 1536-dimensional vectors with 200 points:

| Configuration | Memory per vector | Total for 200 vectors |
|---|---|---|
| float32, no quantization (current) | 6,144 bytes | ~1.2 MB |
| int8 quantized index + float32 on disk | 1,536 bytes in RAM | ~0.3 MB in RAM |
| int8 quantized index, no rescoring | 1,536 bytes | ~0.3 MB |

The 4x reduction is theoretical for the vector data alone. HNSW graph storage adds overhead on top, so real-world RAM reduction is somewhat less. With only 200 points the absolute numbers are small, but the same misconfiguration at 10M vectors would mean 60 GB of wasted RAM instead of the expected 15 GB.

---

## Summary Table

| Finding | Value | Impact |
|---|---|---|
| `indexed_vectors_count` | 0 out of 200 | No quantized index built at all |
| `indexing_threshold` | 10,000 | Optimizer never triggers at 200 points |
| `on_disk` (vectors) | false | Float32 originals held in RAM |
| `quantization_config` | scalar int8 configured | Config present but completely inactive |
| `always_ram` on quantization | false | Correct, not an issue |

The quantization config is correctly defined. The failure is entirely operational: the optimizer never ran because the collection sits far below the `indexing_threshold`, so the quantized index was never built, and memory usage is identical to an unquantized collection.

Immediate action: patch `indexing_threshold` to `100`, wait for the optimizer to complete, and set `on_disk: true` on vectors to achieve the expected memory reduction.
