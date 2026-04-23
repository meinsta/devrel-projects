# Reducing Qdrant Memory Usage for an Existing 5M-Vector Collection

You have 5 million vectors consuming 20GB of RAM and want to reduce that without recreating the collection or losing data. The good news: Qdrant exposes several memory management knobs you can adjust on a live collection. The bad news: the most impactful technique (quantization) requires a re-indexing pass on existing data, which Qdrant can do in the background without downtime or data loss.

---

## 1. Enable Scalar Quantization (Biggest Win, No Data Loss)

Scalar quantization (SQ8) compresses each float32 dimension (4 bytes) down to an int8 (1 byte), giving you a 4x reduction in vector memory. For 5M vectors at 1536 dimensions (OpenAI ada-002 size), that drops the vector data alone from ~30GB to ~7.5GB.

You can enable quantization on an existing collection via the update API. Qdrant will re-index in the background.

```python
from qdrant_client import QdrantClient
from qdrant_client.models import ScalarQuantization, ScalarQuantizationConfig, ScalarType

client = QdrantClient(url="http://localhost:6333")  # or your host

client.update_collection(
    collection_name="your_collection",
    quantization_config=ScalarQuantization(
        scalar=ScalarQuantizationConfig(
            type=ScalarType.INT8,
            quantile=0.99,   # ignore top 1% outliers for better quantization bounds
            always_ram=True  # keep quantized vectors in RAM for fast search
        )
    )
)
```

After this, the original float32 vectors can be offloaded to disk while the compressed int8 vectors stay in RAM. To do that, also update the vector config:

```python
from qdrant_client.models import VectorParamsDiff

client.update_collection(
    collection_name="your_collection",
    vectors_config={
        "": VectorParamsDiff(
            on_disk=True  # original full-precision vectors go to disk
        )
    }
)
```

If your collection uses named vectors, replace `""` with the vector name.

**Expected RAM savings: 60-75% reduction in vector memory.**

---

## 2. Enable Product Quantization (More Aggressive Compression)

If 4x is not enough, product quantization (PQ) can compress vectors by 8x-32x at the cost of some recall accuracy.

```python
from qdrant_client.models import ProductQuantization, ProductQuantizationConfig, CompressionRatio

client.update_collection(
    collection_name="your_collection",
    quantization_config=ProductQuantization(
        product=ProductQuantizationConfig(
            compression=CompressionRatio.X16,  # options: X4, X8, X16, X32, X64
            always_ram=True
        )
    )
)
```

Use `X4` or `X8` for minimal accuracy loss. `X16` and above will degrade recall noticeably unless you tune `oversampling` at search time.

---

## 3. Move the HNSW Index to Disk

The HNSW graph itself consumes significant RAM (often 2-5GB for 5M vectors). You can tell Qdrant to memory-map it instead of loading it fully into RAM:

```python
from qdrant_client.models import HnswConfigDiff

client.update_collection(
    collection_name="your_collection",
    hnsw_config=HnswConfigDiff(
        on_disk=True  # memory-map the HNSW index
    )
)
```

This trades some latency (first access to a cold page causes a disk read) for large RAM savings. On NVMe SSDs the latency increase is often acceptable (single-digit milliseconds).

---

## 4. Move Payload to Disk

Payloads (the metadata stored alongside each vector) can also be moved to disk. If your payloads are large or infrequently accessed, this can free several gigabytes:

```python
client.update_collection(
    collection_name="your_collection",
    optimizers_config={"indexing_threshold": 20000},  # optional tuning
    params={"on_disk_payload": True}
)
```

Or using the model directly:

```python
from qdrant_client.models import CollectionParamsDiff

client.update_collection(
    collection_name="your_collection",
    params=CollectionParamsDiff(
        on_disk_payload=True
    )
)
```

---

## 5. Tune the Optimizer to Reduce Segment Fragmentation

Fragmented segments (many small segments that haven't been merged) waste memory. Force a merge to reduce overhead:

```python
from qdrant_client.models import OptimizersConfigDiff

client.update_collection(
    collection_name="your_collection",
    optimizer_config=OptimizersConfigDiff(
        max_segment_size=500000,      # target ~500k vectors per segment
        memmap_threshold=50000,       # segments above this size use mmap
        indexing_threshold=20000,     # build HNSW index above this size
        flush_interval_sec=30,
        max_optimization_threads=2
    )
)
```

The `memmap_threshold` setting is important: segments with more than this many vectors will use memory-mapped files instead of loading fully into RAM. Lowering this value forces more of the index to mmap.

---

## 6. Configure Qdrant's Global Memory Settings

In your `config.yaml` (or environment variables), you can set global memory behavior:

```yaml
storage:
  on_disk_payload: true          # default payloads to disk for new collections

performance:
  max_search_threads: 4

# Force mmap for large segment files
storage:
  mmap_threshold_kb: 1024        # files larger than 1MB use mmap
```

If using Docker, set via environment:

```bash
docker run \
  -e QDRANT__STORAGE__ON_DISK_PAYLOAD=true \
  -e QDRANT__STORAGE__MMAP_THRESHOLD_KB=1024 \
  qdrant/qdrant
```

---

## 7. Use the REST API Directly (Alternative to Python Client)

All of the above can be done via REST if you prefer:

```bash
# Enable scalar quantization
curl -X PATCH "http://localhost:6333/collections/your_collection" \
  -H "Content-Type: application/json" \
  -d '{
    "quantization_config": {
      "scalar": {
        "type": "int8",
        "quantile": 0.99,
        "always_ram": true
      }
    }
  }'

# Move vectors to disk
curl -X PATCH "http://localhost:6333/collections/your_collection" \
  -H "Content-Type: application/json" \
  -d '{
    "vectors": {
      "": {
        "on_disk": true
      }
    }
  }'

# Move HNSW index to disk
curl -X PATCH "http://localhost:6333/collections/your_collection" \
  -H "Content-Type: application/json" \
  -d '{
    "hnsw_config": {
      "on_disk": true
    }
  }'
```

---

## Recommended Strategy (Ordered by Impact)

Apply these in order and measure after each step:

| Step | Technique | Expected RAM Reduction | Latency Impact |
|------|-----------|------------------------|----------------|
| 1 | Scalar quantization (INT8) + `on_disk=True` for originals | ~60-75% of vector memory | Minimal (1-5%) |
| 2 | HNSW index on disk | 2-5 GB | Low on NVMe, higher on HDD |
| 3 | Payloads on disk | Varies (payload size) | Low for search |
| 4 | Lower `memmap_threshold` | Prevents future bloat | Low |
| 5 | Product quantization if still over budget | Additional 2-4x | Moderate recall loss |

For a 20GB collection at 1536 dimensions with 5M vectors, applying steps 1-3 should bring RAM usage down to the 4-8GB range depending on payload size and HNSW parameters.

---

## Monitoring Progress

After applying changes, check the collection's actual memory usage:

```python
info = client.get_collection("your_collection")
print(info.result.optimizer_status)
print(info.result.segments_count)
print(info.result.vectors_count)

# Check indexed vs unindexed
for segment in client.get_collection("your_collection").result.config.params.vectors:
    print(segment)
```

You can also monitor the optimization progress via:

```bash
curl "http://localhost:6333/collections/your_collection" | jq '.result.optimizer_status'
```

The optimizer runs asynchronously. Large collections (5M vectors) may take 30-60 minutes to fully re-quantize. The collection remains queryable the entire time.

---

## Important Notes

- Quantization re-indexing happens in the background. Do not restart Qdrant mid-optimization or you may need to re-trigger it.
- `always_ram=True` on the quantization config keeps the compressed vectors in RAM (fast) while the originals go to disk. This is the recommended setting.
- If you need to rescore results with original vectors for high-precision use cases, set `rescore=True` in your search params. This uses the disk-stored originals for final ranking.
- Product quantization with high compression ratios requires tuning `oversampling` at search time (e.g., `oversampling=3.0`) to maintain recall.

```python
# Search with rescore for highest accuracy after quantization
results = client.search(
    collection_name="your_collection",
    query_vector=[...],
    limit=10,
    search_params=SearchParams(
        quantization=QuantizationSearchParams(
            ignore=False,
            rescore=True,       # rescore top candidates with original vectors
            oversampling=2.0    # fetch 2x candidates before rescoring
        )
    )
)
```
