# Fixing Qdrant OOM Crashes on K8s (96GB Nodes, 80GB HNSW)

Your HNSW index consuming 80GB out of 96GB leaves almost no headroom for the OS, payload indexes, or query-time allocations. The OOM killer is doing exactly what it should: your working set exceeds node capacity. Here is the fix path, in priority order.

## Step 1: Enable mmap storage immediately (stops the crashes)

This is the emergency fix. Switch vector storage from in-RAM to memory-mapped files. The OS will manage which pages stay resident in RAM based on access patterns, and the OOM killer stops firing because the process RSS stays bounded.

```python
from qdrant_client import QdrantClient

client = QdrantClient(url="https://your-qdrant-host:6333")

client.update_collection(
    collection_name="your_collection",
    vectors_config={
        "": {  # default vector name
            "on_disk": True  # enables mmap for vectors
        }
    },
    hnsw_config={
        "on_disk": True  # moves HNSW graph to mmap as well
    }
)
```

This alone should stop the crashes. Latency may increase from low-ms to 50-500ms range depending on your access patterns, but the node stays alive.

Docs: https://qdrant.tech/documentation/concepts/storage/

**Important:** mmap does not mean "full disk." With mmap, the OS caches hot pages in RAM automatically. Full disk storage would give you 2-5 second latencies. mmap typically stays under 500ms.

## Step 2: Apply scalar quantization (4x memory reduction)

This is the real fix. Scalar quantization compresses each float32 element (4 bytes) down to int8 (1 byte), cutting vector memory by 4x. Accuracy loss is typically under 1%.

```python
from qdrant_client.models import ScalarQuantization, ScalarQuantizationConfig, ScalarType

client.update_collection(
    collection_name="your_collection",
    quantization_config=ScalarQuantization(
        scalar=ScalarQuantizationConfig(
            type=ScalarType.INT8,
            quantile=0.99,
            always_ram=True  # CRITICAL: keeps quantized vectors in RAM for speed
        )
    )
)
```

The `always_ram=True` setting is critical. It keeps the small quantized vectors in RAM for fast initial search while full-resolution vectors stay on disk (via mmap). Without this flag, you lose the speed benefit and both representations compete for memory.

**Memory math for your situation:**

Your HNSW is eating 80GB. Using the formula:

```
RAM = vectors * dimensions * bytes_per_element * 1.5 (HNSW overhead)
```

Working backward from 80GB, you have roughly one of these scenarios:
- ~8.7M vectors at 1536 dims (OpenAI-class embeddings): 80GB checks out
- ~17.4M vectors at 768 dims: also 80GB

With scalar quantization applied:
- 8.7M vectors at 1536 dims: ~20GB instead of 80GB
- 17.4M vectors at 768 dims: ~20GB instead of 80GB

That puts you at roughly 20GB on a 96GB node. Plenty of headroom.

Docs: https://qdrant.tech/documentation/guides/quantization/#scalar-quantization

## Step 3: Consider binary quantization if your model supports it (32x reduction)

If you are using OpenAI, Cohere, Jina, or Gemini embeddings, binary quantization compresses 32x instead of 4x. That would drop your 80GB down to about 2.5-3.8GB.

**Compatible models (verified):**
- OpenAI text-embedding-3-small, text-embedding-3-large, text-embedding-ada-002
- Cohere embed-english-v3.0, embed-multilingual-v3.0
- Jina embeddings v2+
- Gemini text-embedding-004

**Not compatible:**
- Most open-source models without normalization
- Models with fewer than 384 dimensions
- Models not trained with cosine similarity

If you use binary quantization, you MUST enable oversampling (3-5x) and rescoring against full vectors. Without rescoring, recall drops to around 70%. With rescoring, it recovers to 95-98%.

```python
from qdrant_client.models import BinaryQuantization, BinaryQuantizationConfig

client.update_collection(
    collection_name="your_collection",
    quantization_config=BinaryQuantization(
        binary=BinaryQuantizationConfig(
            always_ram=True
        )
    )
)

# When searching, always use oversampling + rescoring
results = client.query_points(
    collection_name="your_collection",
    query=[0.1, 0.2, ...],  # your query vector
    search_params={
        "quantization": {
            "rescore": True,
            "oversampling": 3.0
        }
    },
    limit=10
)
```

Docs: https://qdrant.tech/documentation/guides/quantization/#binary-quantization

## Step 4: Set up proper alerting (prevent future crashes)

Do not wait for OOM kills. Set Prometheus alerts at 75-80% memory utilization so your SRE team gets warned before crashes happen.

Qdrant exposes metrics at the `/metrics` endpoint. Key metrics to alert on:
- Container memory RSS approaching node limits
- Vector count growth rate
- Query latency percentiles (to catch mmap-related degradation)

Docs: https://qdrant.tech/documentation/guides/monitoring/

## What NOT to do

- **Do not shard before trying quantization + mmap.** Sharding adds operational complexity and is only warranted when data genuinely cannot fit on a single node after optimization, or when QPS exceeds single-node capacity (typically 200-500+ QPS). With scalar quantization, your 80GB drops to ~20GB on a 96GB node. Sharding is unnecessary here.
- **Do not use full disk storage.** It gives 2-5 second latencies per query. Use mmap instead.
- **Do not use binary quantization with incompatible models.** Accuracy will degrade significantly.
- **Do not skip rescoring when using binary quantization.** Recall drops to ~70% without it.

## Recommended action plan for your SRE team

| Step | Action | Impact | Downtime |
|------|--------|--------|----------|
| 1 | Enable mmap for vectors and HNSW | Stops OOM kills immediately | Rolling restart |
| 2 | Apply scalar quantization with `always_ram=true` | 4x memory reduction (80GB to ~20GB) | Optimization runs in background |
| 3 | Verify with monitoring | Confirm RSS stays under 75% of 96GB | None |
| 4 | Set Prometheus alerts at 75-80% memory | Prevent future surprises | None |
| 5 | Evaluate binary quantization if model is compatible | Additional 8x reduction on top of scalar | Optimization runs in background |

## Troubleshooting: "I enabled quantization but memory didn't decrease"

Two common causes:
1. `always_ram` is not set, so both original and quantized vectors compete for memory. Verify `always_ram=true` is configured.
2. The collection was not optimized after the config change. Qdrant needs to rebuild segments. Check the collection info endpoint to see if optimization is still running.

## Troubleshooting: "Memory keeps growing even though vector count is stable"

Payload indexes on high-cardinality fields consume RAM. Remove indexes on fields you do not filter by. Use keyword indexes instead of full-text indexes for high-cardinality strings.

Docs: https://qdrant.tech/documentation/concepts/indexing/#payload-index

## Troubleshooting: "Qdrant restarts fine but crashes again after a few hours"

This is normal mmap behavior when your dataset is larger than available RAM. As queries come in, the OS loads pages into memory. RSS grows until the OOM killer fires. The fix is quantization to shrink the working set so it fits comfortably in RAM, combined with alerting at 75-80% memory utilization.
