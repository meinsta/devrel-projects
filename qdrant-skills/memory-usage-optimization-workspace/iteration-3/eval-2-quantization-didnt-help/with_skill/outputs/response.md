# Advisory: Scalar Quantization Enabled but RAM Usage Unchanged

## Short Answer

Nothing went wrong with the quantization itself. What you are seeing in your node-level metrics is almost certainly OS page cache, not data memory. Quantization reduces forced-resident data memory. It does not flush the OS page cache, and it was never designed to.

## What Is Actually Happening

Qdrant stores vectors on disk using memory-mapped files. The operating system caches those mmap pages in whatever RAM is not otherwise occupied. This is standard OS behavior and it is intentional. The cache makes queries fast by keeping hot vector data in memory. The OS evicts those cache pages automatically when something actually needs the memory.

When you enabled scalar quantization:

1. Qdrant created compressed int8 copies of your vectors.
2. The original full-precision vectors remained on disk, still accessible via mmap.
3. The OS page cache that existed before quantization is still sitting in RAM. It was not evicted. There was no memory pressure to force eviction.
4. Any queries running after quantization that trigger rescoring will read original vectors from disk, and those pages get cached again.

So the node-level metrics (htop, docker stats, Prometheus node exporter `node_memory_*`) are reporting data memory plus page cache combined. That combined number does not drop just because quantization reduced the data-resident portion.

## How to Verify This Is the Cause

Check the Qdrant-specific metrics, not the OS-level metrics. Qdrant's `/metrics` endpoint and the web dashboard separate actual data memory from cache. Look for:

- `qdrant_collections_vectors_bytes` or equivalent data usage metrics
- Compare that to the total memory reported by your monitoring tool

If data usage dropped after enabling quantization but total node memory stayed flat, quantization worked correctly. The remaining memory is page cache, which is healthy and expected.

## What "Working Correctly" Looks Like

With scalar int8 quantization and the correct configuration:

- Quantized vectors (1 byte per dimension) are kept in RAM for fast candidate selection
- Original full-precision vectors (4 bytes per dimension) sit on disk and are only read during rescoring
- Total forced-resident data memory drops by roughly 4x for the vector component
- OS page cache may still fill available RAM with mmap pages from query activity

This is the intended behavior. The node is not in a degraded state.

## Check Your Quantization Configuration

One common misconfiguration that causes quantization to have no real effect: `always_ram` set to `False` on the quantization config, or the original vectors left in RAM instead of on disk.

The correct pattern is:

```python
client.update_collection(
    collection_name="my_collection",
    vectors_config=models.VectorParamsDiff(on_disk=True),
    quantization_config=models.ScalarQuantization(
        scalar=models.ScalarQuantizationConfig(
            type=models.ScalarType.INT8,
            always_ram=True,
        ),
    ),
)
```

- `on_disk=True` on the vectors config moves original full-precision vectors to disk
- `always_ram=True` on the quantization config keeps compressed vectors in RAM

If you set `always_ram=False`, Qdrant reads quantized vectors from disk on every search. This eliminates the performance benefit of quantization and causes heavy CPU and I/O load without meaningful memory savings. Do not do this.

If `on_disk` was not explicitly set to `True` on your vectors config when you enabled quantization, the original vectors may still be memory-resident, which would explain why data memory itself did not drop.

## Other RAM Consumers to Check

If you verify that data memory (from the Qdrant metrics endpoint) is also still high after quantization, the issue is not cache. In that case, check:

- **HNSW graph**: always kept in RAM unless `hnsw_config.on_disk=True` is set explicitly. For large collections this can be significant.
- **ID tracker**: the bidirectional mapping from external to internal point IDs is always in RAM. This is not configurable.
- **Payload data**: if `on_disk_payload` is not set to `True`, all payload data lives in RAM.
- **Payload indexes**: each indexed field consumes RAM. Only index fields you actually filter on.
- **Full-text indexes**: frequently overlooked and can consume substantially more RAM than expected.

## Summary

| What you observed | What it means |
|---|---|
| Node-level metrics show no change | OS page cache is still filling available RAM. This is normal. |
| Quantization was enabled | Forced-resident data memory should have dropped. |
| No crash, no errors | The node is functioning correctly. |

Check the Qdrant `/metrics` endpoint to see the actual data memory figure. If that number dropped, quantization worked and the cache you are seeing is benign. If data memory is also unchanged, verify that `on_disk=True` was set on the vectors config alongside the quantization config.
