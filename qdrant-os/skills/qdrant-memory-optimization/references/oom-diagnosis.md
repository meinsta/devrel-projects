# OOM Crashes: Diagnosis and Fix

## When does this happen?
- Qdrant process gets killed by the OS when memory exceeds node capacity
- Usually happens after adding more vectors or during traffic spikes
- Common with default configuration at 50M+ vectors

## Diagnosis: What's consuming the memory?

**Step 1: Check if vectors are in RAM**
- By default, Qdrant memory-maps vectors, but the OS will try to keep
  frequently accessed data in memory. If you set `on_disk=false` in
  your vector configuration, full resolution vectors are forced into RAM.
- Check: are your vectors explicitly configured for in-memory storage?

**Step 2: Check HNSW graph size**
- The HNSW index has overhead proportional to vector count, roughly
  1.5x the vector data size. At 100M+ vectors this alone can consume
  tens of GB.
- The graph itself needs to be traversed quickly, so it resists being
  paged out to disk.

**Step 3: Check if quantization is enabled**
- Without quantization, each float32 vector element uses 4 bytes.
  A 1536-dim vector = 6KB. At 50M vectors, that's 300GB just for
  raw vector data before HNSW overhead.

## What to do

**Immediate fix: Enable mmap to stop the crashes**
- This moves vector data to disk-backed memory-mapped files
- The OS manages what stays in RAM vs disk based on access patterns
- Stops OOM kills immediately, may increase latency
- [Storage configuration docs](https://qdrant.tech/documentation/concepts/storage/)

**Then: Apply quantization to reduce the footprint**
- Scalar quantization (4x reduction, works with all models, < 1% accuracy loss)
- Binary quantization (32x reduction, only OpenAI/Cohere/Jina, needs rescoring)
- See `quantization-guide.md` for which type to use
- [Quantization docs](https://qdrant.tech/documentation/guides/quantization/)

**Then: Set proper alerting**
- Don't wait for crashes. Alert at 75-80% memory, not after OOM.
- [Monitoring docs](https://qdrant.tech/documentation/guides/monitoring/)
