Yes, there is absolutely a middle ground. Going from fully in-RAM to fully on-disk is the most extreme trade-off, and Qdrant provides several intermediate configurations that can dramatically reduce memory usage while keeping latency in the low tens of milliseconds range. Here is the progression from most memory-hungry (fastest) to least memory-hungry (slowest), along with the sweet spot most people land on.

## 1. Use memmap (mmap) for vectors instead of pure RAM

In your collection config, set the vector storage to use memory-mapped files:

```json
{
  "vectors": {
    "on_disk": true
  },
  "optimizers_config": {
    "memmap_threshold": 20000
  }
}
```

Or via the API when creating/updating a collection:

```python
from qdrant_client import QdrantClient, models

client = QdrantClient(url="http://localhost:6333")

client.update_collection(
    collection_name="my_collection",
    vectors_config=models.VectorsConfigDiff(
        on_disk=True
    )
)
```

With mmap, the OS manages a page cache. Vectors live on disk but frequently accessed pages stay in the OS page cache (RAM). This alone can cut your memory footprint significantly while keeping latency close to in-RAM performance, especially if you have enough free RAM for the OS to cache hot pages. Expect latency in the 20-80ms range depending on your dataset size vs. available RAM.

## 2. Keep the HNSW index in RAM, put vectors on disk

This is the most common "middle ground" configuration and likely what you want. The HNSW graph index is relatively small compared to the raw vectors. By keeping the index in RAM and only putting vectors on disk (with mmap), the graph traversal happens at full speed and only the final vector comparisons hit disk.

```python
client.update_collection(
    collection_name="my_collection",
    vectors_config=models.VectorsConfigDiff(
        on_disk=True  # vectors on disk via mmap
    ),
    hnsw_config=models.HnswConfigDiff(
        on_disk=False  # keep HNSW index in RAM
    )
)
```

The HNSW index typically uses 1-2 KB per point (depending on `m` and `ef_construct` settings), while vectors themselves use `dim * 4 bytes` per point. For 1536-dimensional OpenAI embeddings, that is about 6 KB per vector vs. roughly 1-2 KB for the index entry. So you save around 70-80% of RAM while the graph traversal (the expensive part of search) stays fast.

Expected latency: 20-100ms range, which is perfectly usable for a chatbot.

## 3. Quantization (the biggest win for your use case)

Qdrant supports scalar quantization and product quantization, which compress vectors in RAM and use the full-precision vectors on disk only for rescoring.

### Scalar Quantization

This compresses each float32 component to uint8 (a 4x reduction in vector memory):

```python
client.update_collection(
    collection_name="my_collection",
    quantization_config=models.ScalarQuantization(
        scalar=models.ScalarQuantizationConfig(
            type=models.ScalarType.INT8,
            quantile=0.99,
            always_ram=True  # keep quantized vectors in RAM
        )
    ),
    vectors_config=models.VectorsConfigDiff(
        on_disk=True  # full vectors on disk for rescoring
    )
)
```

Then at search time, enable rescoring:

```python
results = client.query_points(
    collection_name="my_collection",
    query=[0.1, 0.2, ...],  # your query vector
    search_params=models.SearchParams(
        quantization=models.QuantizationSearchParams(
            rescore=True,       # rescore top candidates with full vectors
            oversampling=1.5    # fetch 1.5x candidates before rescoring
        )
    ),
    limit=10
)
```

How this works: the search traverses the HNSW graph using the small quantized vectors (which are in RAM), finds the top candidates, then rescores only those candidates using the full-precision vectors from disk. Since you are only reading a handful of full vectors from disk (not thousands), the disk access is minimal.

Expected latency: 15-50ms. Memory savings: ~75% of vector storage.

### Binary Quantization

If you are using OpenAI, Cohere, or other high-dimensional embeddings (1536+), binary quantization gives an even more aggressive compression (32x):

```python
client.update_collection(
    collection_name="my_collection",
    quantization_config=models.BinaryQuantization(
        binary=models.BinaryQuantizationConfig(
            always_ram=True
        )
    ),
    vectors_config=models.VectorsConfigDiff(
        on_disk=True
    )
)
```

Use a higher oversampling factor (2.0-3.0) since binary quantization is less precise:

```python
results = client.query_points(
    collection_name="my_collection",
    query=query_vector,
    search_params=models.SearchParams(
        quantization=models.QuantizationSearchParams(
            rescore=True,
            oversampling=2.5
        )
    ),
    limit=10
)
```

Expected latency: 10-30ms. Memory savings: ~97% of vector storage.

Note: binary quantization works well with normalized high-dimensional embeddings (OpenAI ada-002, text-embedding-3-small/large, Cohere embed-v3). It does not work well with lower-dimensional embeddings or embeddings that are not well-distributed.

## 4. Put the payload index on disk too (additional savings)

If your payload data is large, you can also move payload storage to disk:

```python
client.update_collection(
    collection_name="my_collection",
    vectors_config=models.VectorsConfigDiff(on_disk=True),
    hnsw_config=models.HnswConfigDiff(on_disk=False),
    quantization_config=models.ScalarQuantization(
        scalar=models.ScalarQuantizationConfig(
            type=models.ScalarType.INT8,
            always_ram=True
        )
    ),
    params=models.CollectionParamsDiff(
        on_disk_payload=True
    )
)
```

## Recommended configuration for your chatbot

Given that you need sub-100ms latency and want to minimize RAM, here is the configuration I would recommend:

1. **Vectors**: on disk (mmap)
2. **HNSW index**: in RAM
3. **Quantization**: scalar (INT8) with `always_ram=True`
4. **Search**: rescore enabled with oversampling 1.5
5. **Payload**: on disk if large, in RAM if small

This should give you:
- ~75-85% memory reduction compared to full RAM
- 15-60ms search latency (very usable for a chatbot)
- Minimal accuracy loss (scalar quantization + rescoring preserves >99% recall)

## Why full disk mode was so slow

When you set everything to disk without mmap or quantization, Qdrant has to read the HNSW graph from disk during traversal. Each hop in the graph is a random disk read. A typical search visits hundreds of nodes, and each random read on an SSD takes 50-200 microseconds. Multiply that by hundreds of hops and you get your 3-4 second latency. With the HNSW index in RAM and quantized vectors in RAM, the graph traversal and initial distance comparisons are all in-memory operations, and only the final rescoring step touches disk (sequentially, for a small number of candidates).

## Quick diagnostic

Before changing config, check what is actually on disk vs. RAM in your current setup:

```bash
# Check collection info
curl -s http://localhost:6333/collections/my_collection | python -m json.tool
```

Look at the `optimizer_status`, `vectors_count`, and the storage config to confirm what is currently on disk. Also check if your disk is an SSD. Spinning disks will be unusable for any vector search workload regardless of configuration.
