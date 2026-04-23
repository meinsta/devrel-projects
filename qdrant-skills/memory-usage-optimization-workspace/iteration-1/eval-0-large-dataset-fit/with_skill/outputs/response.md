# Fitting 50M x 1536-dim OpenAI Embeddings into 32GB RAM

## Memory Estimation First

Using the standard formula:

```
memory_size = number_of_vectors * vector_dimension * 4 bytes * 1.5
```

**Raw float32 storage:**
```
50,000,000 * 1536 * 4 * 1.5 = 460,800,000,000 bytes = ~429 GB
```

That is roughly 13x your available RAM. You cannot hold the raw vectors in memory. You need a combination of on-disk storage and quantization.

---

## The Right Strategy for Your Setup

Given 50M vectors at 1536 dimensions with only 32GB RAM, the recommended approach is:

**Binary quantization with `always_ram=True` + vectors and HNSW on disk.**

OpenAI embeddings (1536-dim) are well-suited for binary quantization. The skill's own benchmark data shows OpenAI ada-002 at 1536d achieves **0.98 recall@100 with 4x oversampling**. That is excellent quality for most production use cases.

Here is the RAM breakdown under this configuration:

| Component | Calculation | RAM |
|---|---|---|
| Binary-quantized vectors (1-bit per dim) | 50M * 1536 / 8 bytes | ~9.6 GB |
| OS page cache budget for hot HNSW pages | remaining after quantized vectors | ~20 GB |
| Qdrant process overhead, payload indexes | estimated | ~2 GB |
| **Total** | | **~12 GB active + page cache** |

The binary-quantized index comfortably fits in 32GB. The full-precision vectors live on disk and are only read during rescoring for top candidates.

---

## Collection Creation

```python
from qdrant_client import QdrantClient, models

client = QdrantClient(url="http://localhost:6333")

client.create_collection(
    collection_name="openai_embeddings",
    vectors_config=models.VectorParams(
        size=1536,
        distance=models.Distance.COSINE,
        on_disk=True,          # full float32 vectors go to disk
    ),
    hnsw_config=models.HnswConfigDiff(
        on_disk=True,          # HNSW graph also on disk
        m=16,                  # set to 0 during bulk upload, re-enable after
        ef_construct=100,
    ),
    quantization_config=models.BinaryQuantization(
        binary=models.BinaryQuantizationConfig(
            always_ram=True,   # binary index stays in RAM for fast candidate selection
        ),
    ),
    on_disk_payload=True,      # payload off RAM unless you have room to spare
)
```

If you have payload fields you filter on, always create indexes for them:

```python
# example: filtering by document category
client.create_payload_index(
    collection_name="openai_embeddings",
    field_name="category",
    field_schema=models.KeywordIndexParams(type="keyword"),
)
```

---

## Bulk Upload: Disable Indexing First

With 50M vectors, you must disable HNSW during ingestion or Qdrant will continuously rebuild the index as data arrives, which is extremely slow.

```python
# step 1: create collection with indexing disabled
client.create_collection(
    collection_name="openai_embeddings",
    vectors_config=models.VectorParams(
        size=1536,
        distance=models.Distance.COSINE,
        on_disk=True,
    ),
    hnsw_config=models.HnswConfigDiff(
        m=0,                         # disables HNSW index building
        on_disk=True,
    ),
    optimizers_config=models.OptimizersConfigDiff(
        indexing_threshold=0,        # prevents optimizer from triggering
    ),
    quantization_config=models.BinaryQuantization(
        binary=models.BinaryQuantizationConfig(always_ram=True),
    ),
    on_disk_payload=True,
)

# step 2: upload all 50M vectors in batches
# (use upsert with batch_size=256 or larger depending on your network)

# step 3: re-enable indexing after upload completes
client.update_collection(
    collection_name="openai_embeddings",
    hnsw_config=models.HnswConfigDiff(
        m=16,
        on_disk=True,
    ),
    optimizers_config=models.OptimizersConfigDiff(
        indexing_threshold=20000,
        memmap_threshold=20000,      # set equal to indexing_threshold for single-pass optimization
    ),
)
```

Qdrant will then build the HNSW graph in the background. Monitor collection status until it shows `green` / `ok`.

---

## Search Configuration

Use `rescore=True` with `oversampling=4.0` for OpenAI embeddings. This is the configuration that achieves 0.98 recall@100 per Qdrant's own benchmarks.

```python
results = client.query_points(
    collection_name="openai_embeddings",
    query=your_query_vector,   # list of 1536 floats
    search_params=models.SearchParams(
        hnsw_ef=128,           # increase for better recall, decrease for speed
        quantization=models.QuantizationSearchParams(
            rescore=True,      # fetch full-precision vectors from disk to rerank candidates
            oversampling=4.0,  # fetch 4x candidates before rescoring; key for recall with binary quantization
        ),
    ),
    limit=10,
)
```

Rescoring reads full-precision vectors from disk. On a good NVMe SSD this adds a few milliseconds. On a spinning disk or network volume it will be very slow. You need local SSD with 50k+ IOPS.

---

## Alternative: Scalar Int8 If You Want Higher Recall with Less Tuning

If binary quantization recall does not meet your requirements after tuning oversampling, scalar int8 is the fallback. It uses 4x less RAM than float32 instead of 32x, so the numbers are:

```
50M * 1536 * 1 byte * 1.5 = ~107 GB
```

That still exceeds 32GB. You would need scalar quantization with `always_ram=True` AND on-disk vectors. Only the int8 quantized index stays in RAM:

```
50M * 1536 / 4 bytes * 1.5 = ~27 GB
```

That just fits in 32GB, but leaves almost nothing for the OS, payload indexes, and HNSW graph overhead. Binary quantization is safer for your RAM budget.

```python
# scalar int8 alternative (tighter RAM fit, better recall than binary)
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
            always_ram=True,
        ),
    ),
    hnsw_config=models.HnswConfigDiff(on_disk=True),
    on_disk_payload=True,
)
```

Search with scalar int8:

```python
results = client.query_points(
    collection_name="openai_embeddings",
    query=your_query_vector,
    search_params=models.SearchParams(
        quantization=models.QuantizationSearchParams(
            rescore=True,
            oversampling=2.0,  # 2x is usually sufficient for int8
        ),
    ),
    limit=10,
)
```

---

## Comparison Table for Your Scenario

| Config | RAM for quantized index | Recall (OpenAI 1536d) | Latency impact |
|---|---|---|---|
| float32, all in RAM | ~429 GB | baseline | fastest |
| scalar int8, RAM + disk | ~27 GB (tight) | ~99%+ | low (rescoring adds ms) |
| binary quantization, RAM + disk | ~9.6 GB (comfortable) | ~98% @ 4x oversampling | moderate (more disk reads) |
| binary quantization, all disk | ~9.6 GB on disk | ~98% but slower | high (every search reads disk) |

**Recommendation: binary quantization with `always_ram=True`, full vectors and HNSW on disk.** Your 32GB RAM comfortably holds the binary index (~9.6 GB) with room for the OS, page cache, payload indexes, and Qdrant overhead. Search quality is 0.98 recall@100 with 4x oversampling, which is production-viable for most retrieval workloads.

---

## Infrastructure Requirements

- **Local NVMe SSD** with 50k+ IOPS is mandatory. Network-attached storage (EFS, NFS, typical cloud network disks) runs at 6k-10k IOPS and will cause search timeouts under load.
- **Disk space**: Full float32 vectors = `50M * 1536 * 4 bytes` = ~307 GB raw, plus HNSW graph (roughly 30-40% on top). Plan for at least 450-500 GB of SSD capacity.
- **RAM headroom**: Keep 4-6 GB free for the OS and Qdrant process. Do not configure `always_ram=True` for components that push you above ~26 GB of Qdrant-owned RAM.

---

## Common Mistakes to Avoid

- Do not use `on_disk=True` for vectors without also setting `always_ram=True` for the quantized index. If both are on disk, candidate selection requires disk I/O on every query, which is very slow.
- Do not skip `rescore=True` with binary quantization. Without rescoring, Qdrant only uses the binary index for ranking, and recall drops significantly.
- Do not run HNSW build during ingestion of 50M vectors. Always set `m=0` and `indexing_threshold=0` during bulk load.
- Do not store payload on disk without payload indexes for filtered fields. Filtered queries will scan raw payloads from disk otherwise.
- Do not measure RAM with `htop` or `top`. RSS includes OS page cache from mmap files. Use Docker memory limits or `/proc/meminfo` `MemAvailable` to measure true working set.
