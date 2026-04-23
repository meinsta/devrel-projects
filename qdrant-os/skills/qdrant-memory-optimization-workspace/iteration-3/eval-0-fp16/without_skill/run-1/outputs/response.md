Yes, Qdrant supports float16 (half-precision) vector storage, and for your use case (200M vectors at 1536 dimensions) it is one of the most impactful optimizations you can make.

## How It Works

Qdrant provides a `datatype` parameter in the vector configuration that controls the storage precision of your vectors. The supported options are:

- **`Float32`** (default): standard 32-bit floating point, 4 bytes per dimension
- **`Float16`**: half-precision 16-bit floating point, 2 bytes per dimension
- **`Uint8`**: unsigned 8-bit integer quantization, 1 byte per dimension

You set it when creating a collection:

```json
PUT /collections/my_collection
{
  "vectors": {
    "size": 1536,
    "distance": "Cosine",
    "datatype": "float16"
  }
}
```

Or via the Python client:

```python
from qdrant_client import QdrantClient, models

client = QdrantClient(url="http://localhost:6333")

client.create_collection(
    collection_name="my_collection",
    vectors_config=models.VectorParams(
        size=1536,
        distance=models.Distance.COSINE,
        datatype=models.Datatype.FLOAT16,
    ),
)
```

## Storage Impact for Your Use Case

With 200M vectors at 1536 dimensions:

- **Float32**: 200M x 1536 x 4 bytes = ~1.15 TB of raw vector data
- **Float16**: 200M x 1536 x 2 bytes = ~575 GB of raw vector data

That is roughly a 50% reduction in disk usage for the vector payload storage, which is exactly what you are looking for.

## Search Quality

For 1536-dimensional vectors (typical of OpenAI embeddings like text-embedding-ada-002 or text-embedding-3-small), the quality loss from float16 is negligible. Here is why:

1. **Float16 has ~3 decimal digits of precision.** For high-dimensional vectors where individual components are small floating-point numbers, this is more than sufficient to preserve relative distances between vectors.

2. **Empirically, recall stays at or very near 99.9%+** for cosine similarity searches on embedding vectors at this dimensionality. The rounding error introduced by float16 is effectively noise compared to the actual semantic distances between vectors.

3. **OpenAI and Cohere embeddings are particularly robust** to float16 because their values are already well-distributed within a range that float16 handles accurately.

In short: for 1536-dim dense embeddings, you should not observe any meaningful degradation in search quality with float16.

## Combining with Quantization

Qdrant also supports separate quantization for the HNSW index (the in-memory search structure). You can combine `datatype: float16` for on-disk storage with scalar or binary quantization for the in-memory index:

```json
PUT /collections/my_collection
{
  "vectors": {
    "size": 1536,
    "distance": "Cosine",
    "datatype": "float16"
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

This gives you:

- **Float16 on disk**: halves your storage footprint
- **Int8 scalar quantization in RAM**: reduces memory usage for the search index by ~4x compared to float32

With rescoring enabled (the default), the search uses the quantized vectors for the initial candidate retrieval and then rescores against the float16 vectors on disk, preserving high recall.

## Recommendations for Your Setup

1. **Use `datatype: float16`** for storage. This is the single biggest win for your scenario.
2. **Enable scalar quantization** (`int8`) for the HNSW index to reduce RAM requirements.
3. **Keep rescoring enabled** (it is on by default) so that final results are scored against the higher-precision stored vectors.
4. **If you want to go further**, consider binary quantization with oversampling for even more aggressive memory savings, though this has a larger quality trade-off and works best with certain embedding models.

For 200M vectors at 1536 dims, the combination of float16 storage and int8 scalar quantization is the standard recommendation. You will cut disk usage roughly in half and significantly reduce RAM needs while maintaining search quality that is effectively indistinguishable from full float32.
