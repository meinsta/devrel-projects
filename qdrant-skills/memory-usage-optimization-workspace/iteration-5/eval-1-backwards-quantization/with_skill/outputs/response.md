# Diagnostic: embeddings-archive Quantization Not Reducing Memory

## Cluster

- URL: `https://94214c31-6930-4f9f-9f33-ec90c15a76c0.eu-west-2-0.aws.cloud.qdrant.io:6333`
- Qdrant version: `1.16.3`

## Phase 1: Collected Facts

### Collections (12 total)

```
products-it-it, embeddings-archive, products-en-gb, products-de-de,
products-fr-fr, products-us, products-ko-kr, products-zh-cn,
products-pt-br, products-nl-nl, products-ja-jp, products-es-es
```

Each collection carries 12-14 MB of baseline overhead. With 12 collections, that is roughly 144-168 MB of fixed overhead beyond vectors.

### embeddings-archive Config (verbatim)

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
      "on_disk_payload": true
    },
    "hnsw_config": {
      "on_disk": false
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

## Phase 2: Classification

Symptom: "enabled scalar quantization but memory usage didn't drop."

This maps to **Phase 3C: Quantization no-op** -- the config is inverted from what is required for quantization to reduce memory.

## Phase 3: Root Cause

The collection has two problems with its quantization config, both discovered in Phase 1.

### Problem 1: `always_ram: false` on quantized vectors (primary cause)

The quantized int8 vectors are configured with `always_ram: false`. This means Qdrant does NOT load the quantized vectors into RAM. Instead, they are memory-mapped from disk just like the original vectors.

When `always_ram: false`, the quantized vectors provide no forced-resident memory reduction. The OS page cache may still hold them in RAM opportunistically, but there is no guarantee, and the point of scalar quantization is to keep a small, fast representation in RAM for candidate selection. Without `always_ram: true`, that purpose is defeated.

### Problem 2: `on_disk: false` on original vectors (secondary cause)

The original float32 vectors have `on_disk: false`. This means the full-precision vectors remain accessible in RAM (not pushed to disk). The correct quantization workflow is:

- Quantized vectors: `always_ram: true` -- small int8 representation stays in RAM for candidate selection
- Original vectors: `on_disk: true` -- large float32 representation goes to disk, only read during rescoring

With `always_ram: false` on quantization and `on_disk: false` on originals, the collection behaves as if no quantization was configured at all from a memory perspective. Both representations compete for RAM.

### Secondary observation: `indexed_vectors_count: 0`

With 200 points and `indexing_threshold: 10000`, the optimizer has not built an HNSW index (the collection is too small to cross the threshold). This is expected for a small collection, but it means the optimizer also has not applied quantization to a dedicated indexed segment. The scalar quantization config exists in the collection config, but may not yet be reflected in segment-level storage if the optimizer has not run a full optimization pass.

## Phase 4: Recommendations

Fix the quantization config by correcting both flags:

```http
PATCH /collections/embeddings-archive
Content-Type: application/json

{
  "vectors": {
    "on_disk": true
  },
  "quantization_config": {
    "scalar": {
      "type": "int8",
      "quantile": 0.99,
      "always_ram": true
    }
  }
}
```

After applying, verify the optimizer runs by polling `GET /collections/embeddings-archive` and checking `optimizer_status`. Once the optimizer finishes, check telemetry to confirm data memory dropped.

### Expected outcome after fix

- Quantized int8 vectors (200 vectors x 1536 dims x 1 byte = ~300 KB) stay in RAM
- Original float32 vectors (200 vectors x 1536 dims x 4 bytes = ~1.2 MB) move to disk, read only during rescoring
- For larger collections at this dimension, the memory reduction from float32 to int8 is 4x on the vector data itself

### What NOT to do

Do not set `always_ram: false` to "save even more RAM." This causes disk thrashing on every search because the quantized candidates must be loaded from disk on every query, leading to extreme latency and CPU overhead.

## Summary Table

| Config field | Current value | Correct value | Effect of current |
|---|---|---|---|
| `quantization_config.scalar.always_ram` | `false` | `true` | Quantized vectors not pinned in RAM, no memory savings |
| `vectors.on_disk` | `false` | `true` | Original float32 vectors remain in RAM, not offloaded |
| `indexed_vectors_count` | `0` | should match `points_count` after fix | Optimizer has not indexed; quantization not yet applied at segment level |

The config is effectively backwards: the component that should be in RAM (`always_ram: true`) is set to not be pinned, and the component that should be on disk (`on_disk: true`) is set to stay in RAM. Correcting both flags will allow scalar quantization to reduce memory as expected.
