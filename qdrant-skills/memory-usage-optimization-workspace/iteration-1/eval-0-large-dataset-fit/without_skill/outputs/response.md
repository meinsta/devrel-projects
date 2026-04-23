# Fitting 50M x 1536-dim OpenAI Embeddings in 32GB RAM with Qdrant

## The Core Problem: Raw Memory Requirements

Before any optimization, let's understand the baseline memory requirement.

**Raw vector storage:**
- 50,000,000 vectors x 1536 dimensions x 4 bytes (float32) = **307.2 GB**

That is roughly 10x more than the available 32GB RAM. This means you cannot load all vectors into RAM simultaneously. Qdrant has several mechanisms to make this workable.

---

## Strategy Overview

The approach combines three techniques, each contributing significantly to reducing RAM usage:

1. **Scalar Quantization (SQ8)** -- reduces vector size by 4x
2. **Memory-mapped (mmap) storage** -- keeps most data on disk, only hot data in RAM
3. **On-disk payload and vector storage** -- avoids loading everything eagerly

With all three applied, the in-RAM footprint can be reduced to roughly 10-15 GB for the quantized index plus operating overhead, which fits within 32GB.

---

## Step 1: Quantization (Critical)

### Scalar Quantization (SQ8) -- Recommended

SQ8 converts each float32 (4 bytes) to uint8 (1 byte), achieving a 4x compression.

**Memory after SQ8:**
- 50M x 1536 x 1 byte = **76.8 GB** (still too large for RAM alone, but much more manageable with mmap)

**Search quality impact:** Minimal. SQ8 typically loses 1-3% recall compared to exact float32 search, which is acceptable for most production use cases.

```python
from qdrant_client import QdrantClient, models

client = QdrantClient(host="localhost", port=6333)

client.create_collection(
    collection_name="openai_embeddings",
    vectors_config=models.VectorParams(
        size=1536,
        distance=models.Distance.COSINE,
        on_disk=True,  # store raw vectors on disk
    ),
    quantization_config=models.ScalarQuantization(
        scalar=models.ScalarQuantizationConfig(
            type=models.ScalarType.INT8,
            quantile=0.99,   # clip outliers for better quantization range
            always_ram=True, # keep quantized vectors in RAM for fast search
        ),
    ),
    hnsw_config=models.HnswConfigDiff(
        on_disk=False,   # keep HNSW graph in RAM for fast traversal
        m=16,
        ef_construct=100,
    ),
    optimizers_config=models.OptimizersConfigDiff(
        memmap_threshold=20000,  # segments with >20k vectors use mmap
    ),
)
```

### Product Quantization (PQ) -- Alternative for Extreme Compression

If 32GB is still tight after SQ8 + mmap, consider Product Quantization. PQ can achieve 8x-32x compression but with more noticeable quality loss (typically 5-10% recall drop).

```python
client.create_collection(
    collection_name="openai_embeddings_pq",
    vectors_config=models.VectorParams(
        size=1536,
        distance=models.Distance.COSINE,
        on_disk=True,
    ),
    quantization_config=models.ProductQuantization(
        product=models.ProductQuantizationConfig(
            compression=models.CompressionRatio.X16,  # 16x compression
            always_ram=True,
        ),
    ),
)
```

---

## Step 2: Memory-Mapped (mmap) Vector Storage

mmap lets the OS manage which pages of vector data stay in physical RAM vs. disk. Only the data that is actively being read lives in RAM at any given moment.

**Key configuration: `memmap_threshold`**

This controls the minimum segment size (in vectors) before mmap kicks in. Set it low to force mmap for all large segments:

```python
# Via collection creation (shown above) or update:
client.update_collection(
    collection_name="openai_embeddings",
    optimizers_config=models.OptimizersConfigDiff(
        memmap_threshold=10000,  # segments over 10k vectors use mmap
    ),
)
```

You can also set this globally in `config.yaml`:

```yaml
storage:
  # All segments above this threshold will use mmap
  memmap_threshold_kb: 1048576  # 1GB per segment before forcing mmap

  # Or per-collection via API as shown above
```

---

## Step 3: On-Disk Vector and Payload Storage

Set `on_disk=True` in `VectorParams` (shown above). This ensures raw float32 vectors are never loaded fully into RAM. Only the quantized copies (much smaller) live in RAM.

For payloads (metadata), also configure on-disk storage:

```python
client.update_collection(
    collection_name="openai_embeddings",
    vectors_config={
        "": models.VectorParamsDiff(
            on_disk=True,
        )
    },
)
```

Set payload indexing on disk in config:

```yaml
storage:
  on_disk_payload: true
```

---

## Step 4: HNSW Graph Configuration

The HNSW index graph itself consumes RAM. For 50M vectors:

- Default `m=16`: graph uses roughly ~25-30 GB (too much on its own)
- `on_disk=True` for HNSW: graph moves to disk, saving RAM at cost of higher latency

**Recommendation: keep HNSW in RAM if possible, but tune `m` down.**

```python
hnsw_config=models.HnswConfigDiff(
    m=8,              # reduce from default 16, saves ~50% graph RAM
    ef_construct=80,  # slightly lower build quality, much faster
    on_disk=False,    # keep in RAM for speed
)
```

**HNSW RAM estimate with m=8:**
- Roughly 8 bytes per edge x m edges x 2 layers x 50M vectors = ~6.4 GB

This is manageable within 32GB alongside quantized vectors.

If even that is too much, set `on_disk=True` for HNSW:

```python
hnsw_config=models.HnswConfigDiff(
    on_disk=True,  # HNSW graph on disk, ~2-3x slower search
    m=16,
    ef_construct=100,
)
```

---

## Complete Recommended Configuration

Here is the full recommended setup balancing memory and search quality:

```python
from qdrant_client import QdrantClient, models

client = QdrantClient(host="localhost", port=6333)

client.create_collection(
    collection_name="openai_embeddings",
    vectors_config=models.VectorParams(
        size=1536,
        distance=models.Distance.COSINE,
        on_disk=True,        # raw float32 vectors go to disk
    ),
    quantization_config=models.ScalarQuantization(
        scalar=models.ScalarQuantizationConfig(
            type=models.ScalarType.INT8,
            quantile=0.99,   # handles outliers cleanly
            always_ram=True, # quantized index lives in RAM
        ),
    ),
    hnsw_config=models.HnswConfigDiff(
        m=8,                 # balance graph size vs. quality
        ef_construct=80,
        on_disk=False,       # keep HNSW graph in RAM
    ),
    optimizers_config=models.OptimizersConfigDiff(
        memmap_threshold=20000,      # mmap segments above 20k vectors
        indexing_threshold=20000,    # build HNSW after 20k vectors
        default_segment_number=4,    # tune based on CPU cores
    ),
)
```

**Expected RAM usage breakdown:**

| Component | Size |
|-----------|------|
| Quantized vectors (SQ8, in RAM) | ~76.8 GB / 4 = **19.2 GB** |
| Wait -- SQ8 is 1 byte, so: 50M x 1536 x 1 = 76.8 GB? |  |

Let me recalculate clearly:

- SQ8 quantized vectors: 50M x 1536 x 1 byte = **76.8 GB**

That is still too large for 32GB RAM if `always_ram=True`. Two options:

**Option A: Set `always_ram=False` for quantized vectors (use mmap for quantized too)**

```python
quantization_config=models.ScalarQuantization(
    scalar=models.ScalarQuantizationConfig(
        type=models.ScalarType.INT8,
        quantile=0.99,
        always_ram=False,  # quantized vectors also use mmap
    ),
),
```

With mmap, only "hot" quantized data lives in RAM. Working set for typical queries is much smaller. Expect 8-16 GB RAM usage under moderate load.

**Option B: Use Product Quantization for greater compression**

PQ with X32 compression: 50M x 1536 / 32 = ~2.4 GB for compressed vectors (fits easily in RAM).

```python
quantization_config=models.ProductQuantization(
    product=models.ProductQuantizationConfig(
        compression=models.CompressionRatio.X32,
        always_ram=True,   # 2.4 GB, fits in RAM
    ),
),
```

---

## Final Recommended Setup for 32GB RAM

Given the constraints, here is the most practical configuration:

```python
client.create_collection(
    collection_name="openai_embeddings",
    vectors_config=models.VectorParams(
        size=1536,
        distance=models.Distance.COSINE,
        on_disk=True,
    ),
    quantization_config=models.ScalarQuantization(
        scalar=models.ScalarQuantizationConfig(
            type=models.ScalarType.INT8,
            quantile=0.99,
            always_ram=False,  # mmap for quantized -- OS caches hot data
        ),
    ),
    hnsw_config=models.HnswConfigDiff(
        m=8,
        ef_construct=100,
        on_disk=False,       # HNSW graph in RAM (~6-7 GB)
    ),
    optimizers_config=models.OptimizersConfigDiff(
        memmap_threshold=10000,
        indexing_threshold=20000,
        default_segment_number=4,
    ),
)
```

**At search time, boost recall with `oversampling` and `rescore`:**

```python
results = client.search(
    collection_name="openai_embeddings",
    query_vector=query_embedding,
    limit=10,
    search_params=models.SearchParams(
        quantization=models.QuantizationSearchParams(
            ignore=False,
            rescore=True,       # rescore with original vectors for accuracy
            oversampling=2.5,   # fetch 25 candidates per 10 results
        ),
        hnsw_ef=128,            # higher ef = better recall at query time
    ),
)
```

The `rescore=True` flag fetches the top candidates using quantized vectors (fast, low RAM), then re-ranks using the original float32 vectors (reads from disk/mmap). This recovers most of the quality lost to quantization.

---

## Memory Budget Summary

With the final configuration:

| Component | RAM Usage |
|-----------|-----------|
| HNSW graph (m=8, 50M vectors) | ~6-8 GB |
| OS page cache for hot quantized vectors | ~8-12 GB (OS managed) |
| Qdrant process overhead | ~1-2 GB |
| OS + other processes | ~2-4 GB |
| **Total** | **~17-26 GB** |

This fits within 32GB with room for spikes.

---

## Disk Requirements

Make sure you have enough disk space:

- Raw float32 vectors: 307 GB
- Quantized SQ8 vectors: 77 GB
- HNSW graph: ~25 GB
- Payloads: depends on metadata size

**Recommended: SSD with at least 500GB free.** NVMe SSD is strongly preferred since mmap performance is highly sensitive to disk IOPS and latency. A spinning HDD will make search latency unacceptable.

---

## Expected Search Quality

With SQ8 + rescore:
- Recall@10 vs. exact search: typically 95-98%
- Latency: 50-200ms for top-10 results at moderate QPS (depends on disk speed)

With PQ X32 + rescore:
- Recall@10: typically 90-95%
- Latency: similar or slightly faster for initial candidate retrieval

---

## Qdrant Configuration File (config.yaml)

```yaml
storage:
  storage_path: /var/lib/qdrant/storage
  on_disk_payload: true

  performance:
    max_search_threads: 0  # auto-detect CPU cores

  hnsw_index:
    m: 8
    ef_construct: 100
    full_scan_threshold: 10000
    max_indexing_threads: 0
    on_disk: false

  quantization:
    always_ram: false

service:
  max_request_size_mb: 32
  max_workers: 0

optimizers:
  memmap_threshold_kb: 204800  # 200MB per segment before mmap
  indexing_threshold_kb: 204800
```

---

## Summary of Key Decisions

| Decision | Recommendation | Reason |
|----------|---------------|--------|
| Quantization | SQ8 with `always_ram=False` | Best balance of quality and RAM |
| Raw vectors | `on_disk=True` | Never load 307GB into RAM |
| HNSW graph | `on_disk=False` with `m=8` | Keep traversal fast |
| mmap threshold | Low (10k-20k vectors) | Force mmap for all large segments |
| Search params | `rescore=True`, `oversampling=2.5` | Recover quantization quality loss |
| Disk type | NVMe SSD | mmap latency is critical |

This configuration allows Qdrant to serve 50M x 1536-dim OpenAI embeddings from a 32GB RAM machine with decent search quality (95%+ recall) by leveraging the OS page cache, quantization, and mmap to keep only hot data in physical memory.
