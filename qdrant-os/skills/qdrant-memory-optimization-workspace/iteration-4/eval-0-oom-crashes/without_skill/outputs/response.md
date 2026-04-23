# Addressing OOM Crashes on Your 96GB K8s Nodes

With HNSW consuming 80GB out of 96GB, you are running dangerously close to the limit. Here are your options beyond adding more RAM.

## Option 1: Enable memory-mapped (mmap) storage

Instead of keeping all vectors in RAM, switch to mmap-based storage. This moves vector data to disk-backed memory-mapped files. The OS manages caching, keeping frequently accessed data in memory and paging out the rest.

This is the fastest way to stop OOM kills. Latency may increase somewhat (from single-digit ms to tens or hundreds of ms), but the process will no longer be killed.

You can configure this in Qdrant's storage settings by adjusting `memmap_threshold`.

## Option 2: Apply quantization

Quantization compresses vectors from float32 to smaller representations, reducing memory proportionally.

**Scalar quantization (int8):** Compresses each float32 element (4 bytes) to 1 byte. 4x memory reduction with minimal accuracy loss (typically under 1%). This is the safest starting point.

**Binary quantization:** Compresses each element to 1 bit, giving 32x reduction. However, this only works well with certain models (OpenAI, Cohere embeddings) and requires oversampling and rescoring to maintain acceptable recall.

Configure quantization on your collection and set `always_ram: true` for the quantized vectors so they remain in memory for fast search while full vectors live on disk.

## Option 3: Combination approach (recommended)

The best practice for production is combining mmap with quantization:

1. Store full-resolution vectors on disk via mmap
2. Keep quantized vectors in RAM for the initial search phase
3. Rescore top candidates against full vectors loaded from disk

This gives you near-RAM search speed at a fraction of the memory cost. Your 80GB HNSW footprint could drop to roughly 20GB with scalar quantization.

## Option 4: Shard across multiple nodes

If the data genuinely does not fit on a single node even with quantization, you can shard the collection across multiple Qdrant nodes. Each node holds a portion of the data. But try quantization and mmap first, as sharding adds operational complexity.

## Option 5: Reduce HNSW parameters

You can lower `m` (number of edges per node in the HNSW graph) and `ef_construct` to reduce the index memory footprint. Lower `m` means fewer connections per vector, which reduces both memory and build time. The tradeoff is slightly lower recall at the same `ef` search parameter. Dropping `m` from the default of 16 to 8 or 12 can meaningfully reduce index size.

## Recommended action plan

1. Enable mmap immediately to stop the crashes
2. Apply scalar quantization with `always_ram: true`
3. Monitor memory usage and set alerts at 75-80% utilization
4. If still too tight, consider binary quantization (if your model supports it) or sharding
