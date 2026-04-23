# Diagnosis: Scalar Quantization Enabled But RAM Didn't Decrease

## Root Cause

Enabling quantization does not evict the OS page cache. The cache that built up from your original float32 vectors is still resident in RAM, and Qdrant does nothing to forcibly flush it. You are measuring OS-level memory (which includes cache), not the actual working set that Qdrant keeps permanently resident.

There is also a second, more critical configuration issue that is almost certainly present: your original float32 vectors are still set to be memory-mapped without `on_disk=True`, which means every time a search runs rescoring (or vectors are read for any reason), those original vectors get pulled back into the page cache. Quantization reduced what Qdrant *forces* into RAM, but it did not change the fact that the originals are still being cached on access.

## What Quantization Actually Changes

Quantization affects the permanently-resident in-RAM footprint: the quantized vectors are stored in a separate compressed representation that Qdrant keeps in memory for fast candidate selection. The original full-resolution vectors are still on disk and still get cached by the OS when accessed (e.g., during rescoring).

So the split is:

- Quantized vectors (INT8): small, in RAM permanently via `always_ram=True` (the good part)
- Original float32 vectors: on disk, but cached by the OS in the page cache when accessed

If you enabled quantization but left the original vectors without an explicit `on_disk=True`, the originals are still being read during rescoring and cached in the page cache. Node-level metrics that include page cache will show high memory. This is the scenario you are in.

## How to Verify

Check the current collection configuration:

```python
info = client.get_collection("your_collection")

# Check vector storage config
print(info.config.params.vectors)
# If on_disk is False or not set, this is the problem

# Check quantization config
print(info.config.quantization_config)
# Check if always_ram is set
```

If `on_disk` on the vector config is `False` or absent, the originals are not being intentionally kept off disk. The OS is caching them opportunistically.

## The Fix

The correct configuration for quantization to actually reduce observed memory is:

1. Original vectors: `on_disk=True` (they stay on disk, only cached when accessed during rescoring, not permanently resident)
2. Quantized vectors: `always_ram=True` (small INT8 copies stay in RAM for fast candidate selection)

Apply this update:

```python
client.update_collection(
    collection_name="your_collection",
    vectors_config=models.VectorParamsDiff(on_disk=True),
    quantization_config=models.ScalarQuantization(
        scalar=models.ScalarQuantizationConfig(
            type=models.ScalarType.INT8,
            always_ram=True,
        ),
    ),
)
```

After applying this, the optimizer will reindex segments. Once optimization completes, restart the node (or wait for cache pressure) to allow the OS to evict stale page cache from the old float32 mmap files. At that point, you should see the working set drop to approximately the INT8 footprint (4x reduction vs float32) plus HNSW graph metadata.

## Why "Just Disabling always_ram" Is the Wrong Fix

Some operators try to set `always_ram=False` on the quantization config to save RAM. This causes the quantized vectors themselves to be read from disk during every search, which collapses search performance. The quantized vectors need to be in RAM for the performance benefit of quantization to materialize. Do not do this.

## Search Configuration After the Fix

When originals are on disk, configure searches to use rescoring so quality is preserved:

```python
client.query_points(
    collection_name="your_collection",
    query=embedding,
    search_params=models.SearchParams(
        quantization=models.QuantizationSearchParams(
            rescore=True,
            oversampling=2.0,
        )
    ),
    limit=10,
)
```

`rescore=True` fetches the top N candidates from the quantized search, then re-ranks them using the original float32 vectors. This recovers most of the recall lost from quantization. The originals are only read for the small rescore candidate set, so cache pressure from rescoring is minimal compared to full vector loads.

## Expected Memory After Fix

Using INT8 scalar quantization with originals on disk:

| Component | Memory |
|---|---|
| Quantized INT8 vectors (always_ram) | ~1 byte/dim per vector |
| HNSW graph + metadata | ~1.5x multiplier on top of quantized size |
| Original float32 vectors | On disk, page-cached on access only |

For a 1536-dim collection with 10M vectors:
- float32 baseline: ~92 GB
- After this fix: ~14-15 GB working set (before OS cache adds back some float32 pages on access)

## Summary

The issue is not that quantization failed. The issue is that quantization only controls what Qdrant forces into RAM. The OS page cache independently caches whatever files get read from disk, including the original float32 mmap files. Setting `on_disk=True` on the original vectors ensures they are not treated as primary resident data, limiting their cache footprint to only what rescoring touches. That is the missing half of the configuration.
