# Fixing Disk-Based Qdrant Latency: The Middle Ground

Going from 15ms to 3-4 seconds means every vector read is hitting disk on every query. That is expected when you move everything off RAM, but there are several strategies between "everything in RAM" and "everything on disk" that can get you back to acceptable latency for a chatbot (sub-200ms is a reasonable target).

## 1. Use Memmap Storage Instead of Pure On-Disk

This is the single biggest win. Qdrant supports `mmap` (memory-mapped files) as a storage option, which sits between full RAM and pure disk. With mmap, the OS kernel manages a page cache: hot vectors stay in RAM automatically, cold ones live on disk. You get most of the memory savings without the catastrophic latency.

In your collection config:

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

Or when creating/updating a collection:

```python
from qdrant_client import QdrantClient, models

client = QdrantClient(url="http://localhost:6333")

client.update_collection(
    collection_name="your_collection",
    optimizers_config=models.OptimizersConfigDiff(
        memmap_threshold=20000
    )
)
```

With mmap, the OS will keep frequently accessed vectors in the page cache. If your working set (the vectors you actually query against) fits in available RAM, latency will be close to the full-RAM baseline.

## 2. Put the HNSW Index in RAM, Keep Vectors on Disk

The HNSW graph index is what Qdrant traverses during search. If the index itself is on disk, every graph hop is a disk read, and that is where most of your 3-4 second latency comes from. HNSW traversal touches many random memory locations.

Keep the index in RAM while storing the actual vector data on disk:

```python
client.update_collection(
    collection_name="your_collection",
    hnsw_config=models.HnswConfigDiff(
        on_disk=False  # keep HNSW index in RAM
    )
)
```

The HNSW index is significantly smaller than the raw vector data. For example, if you have 1 million 1536-dimensional vectors (OpenAI embeddings), the vectors take roughly 6 GB, but the HNSW index might only take 200-500 MB. This alone can bring you from 3-4 seconds back down to 50-200ms.

## 3. Use Quantization to Shrink What Lives in RAM

Quantization compresses vectors so more of them fit in memory. Qdrant supports several options.

**Scalar quantization** (simplest, good results):

```python
client.update_collection(
    collection_name="your_collection",
    quantization_config=models.ScalarQuantization(
        scalar=models.ScalarQuantizationConfig(
            type=models.ScalarType.INT8,
            always_ram=True  # keep quantized vectors in RAM
        )
    )
)
```

This compresses float32 vectors to int8 (4x reduction). A 6 GB collection becomes ~1.5 GB. With `always_ram=True`, the quantized vectors stay in memory for fast approximate search, while full-precision vectors remain on disk for rescoring.

**Binary quantization** (aggressive, best for high-dimensional embeddings like OpenAI):

```python
client.update_collection(
    collection_name="your_collection",
    quantization_config=models.BinaryQuantization(
        binary=models.BinaryQuantizationConfig(
            always_ram=True
        )
    )
)
```

This gives 32x compression. A 6 GB collection becomes ~192 MB in RAM. Works well with OpenAI and Cohere embeddings (1536+ dimensions). You lose some recall, but for a chatbot doing RAG, the difference is usually negligible.

**When searching with quantization, use rescoring:**

```python
results = client.query_points(
    collection_name="your_collection",
    query=query_vector,
    search_params=models.SearchParams(
        quantization=models.QuantizationSearchParams(
            rescore=True,       # rescore top candidates with full vectors
            oversampling=2.0    # fetch 2x candidates before rescoring
        )
    ),
    limit=10
)
```

## 4. The Recommended Combined Strategy

For a chatbot use case, here is the configuration that balances memory and latency:

```python
from qdrant_client import QdrantClient, models

client = QdrantClient(url="http://localhost:6333")

# Create collection with optimized settings
client.create_collection(
    collection_name="chatbot_knowledge",
    vectors_config=models.VectorParams(
        size=1536,
        distance=models.Distance.COSINE,
        on_disk=True  # vectors on disk
    ),
    hnsw_config=models.HnswConfigDiff(
        on_disk=False,  # HNSW index in RAM
        m=16,
        ef_construct=100
    ),
    quantization_config=models.ScalarQuantization(
        scalar=models.ScalarQuantizationConfig(
            type=models.ScalarType.INT8,
            always_ram=True  # quantized vectors in RAM
        )
    ),
    optimizers_config=models.OptimizersConfigDiff(
        memmap_threshold=20000
    )
)
```

**Memory footprint compared to full RAM (for 1M vectors at 1536 dims):**

| Strategy | RAM Usage | Approx Latency |
|---|---|---|
| Full RAM | ~6 GB | 10-15ms |
| HNSW in RAM + scalar quantization in RAM + vectors on disk | ~2 GB | 30-80ms |
| HNSW in RAM + binary quantization in RAM + vectors on disk | ~700 MB | 40-100ms |
| Everything on disk (your current setup) | ~100 MB | 2-5 seconds |

## 5. Additional Tuning

**Increase `ef` at search time for better recall if needed:**

```python
results = client.query_points(
    collection_name="chatbot_knowledge",
    query=query_vector,
    search_params=models.SearchParams(
        hnsw_ef=128,  # higher = better recall, slightly slower
        quantization=models.QuantizationSearchParams(
            rescore=True,
            oversampling=1.5
        )
    ),
    limit=10
)
```

**Use payload indexes to narrow search scope.** If your chatbot searches within specific document categories or user contexts, adding a payload index lets Qdrant skip irrelevant vectors entirely:

```python
client.create_payload_index(
    collection_name="chatbot_knowledge",
    field_name="category",
    field_schema=models.PayloadSchemaType.KEYWORD
)

# Then filter at query time
results = client.query_points(
    collection_name="chatbot_knowledge",
    query=query_vector,
    query_filter=models.Filter(
        must=[
            models.FieldCondition(
                key="category",
                match=models.MatchValue(value="product_docs")
            )
        ]
    ),
    limit=10
)
```

## Summary

The key insight: you do not have to choose between "all in RAM" and "all on disk." The practical middle ground is:

1. Keep the HNSW index in RAM (small footprint, huge latency impact).
2. Use scalar or binary quantization with `always_ram=True` (compressed vectors in RAM for initial candidate selection).
3. Store full-precision vectors on disk with mmap (only accessed for final rescoring of top candidates).

This should bring your latency from 3-4 seconds down to 30-100ms while using a fraction of the RAM that full in-memory storage requires. For a chatbot, that latency range is perfectly acceptable since the LLM generation step typically takes 1-3 seconds anyway.
