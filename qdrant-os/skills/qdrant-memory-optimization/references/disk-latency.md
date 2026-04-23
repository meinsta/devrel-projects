# Disk Latency: "I switched to disk but latency is 2+ seconds"

## When does this happen?
- Developer moved from RAM to disk to reduce memory usage
- Latency jumped from milliseconds to multiple seconds
- Common reaction: "guess I have to go back to RAM"

## Diagnosis: What went wrong?

The issue is almost always that you switched to **full disk**, not
**mmap**. These are different things:

- **Full disk:** Every query reads from disk. 200-250 disk reads per
  HNSW traversal. Each read incurs cold-start latency. Result: seconds.
- **mmap:** Data lives on disk but the OS caches hot pages in memory
  automatically. Frequently accessed vectors stay in RAM, cold ones
  on disk. Result: 50-500ms.

## What to do

**Do NOT go back to full RAM.** There is a middle ground.

1. Switch from full disk to mmap storage
   - [Storage configuration](https://qdrant.tech/documentation/concepts/storage/)
2. Apply scalar quantization with `always_ram=true`
   - Keeps the small quantized vectors in RAM for fast initial search
   - Full vectors stay on disk, loaded only for rescoring
   - [Quantization with rescoring](https://qdrant.tech/documentation/guides/quantization/#setting-up-quantization-in-qdrant)
3. Expected result: 2+ seconds drops to under 500ms

The key insight: keeping the HNSW graph in memory is what matters most
for latency. Graph traversal in RAM is nearly instantaneous (low ms).
On disk, each of the 200+ hops hits disk, pushing into hundreds of ms
or seconds.

See `storage-tiers.md` for the full latency comparison table.
