# Scaling Memory: "Memory at 85-90% and I haven't scaled yet"

## When does this happen?
- Running fine in dev with a small dataset
- Deployed to production, memory usage immediately high
- Worried about what happens at 10x the data

## Diagnosis: What's the growth math?

Without quantization, memory scales linearly with vector count:
- 10M vectors at 1536 dims = ~92 GB RAM (with HNSW overhead)
- 100M vectors = ~920 GB RAM
- That's a 10x data increase requiring 10x hardware

With scalar quantization, the math changes:
- 10M vectors at 1536 dims = ~23 GB RAM
- 100M vectors = ~230 GB RAM
- Same 10x data, but starting from a 4x lower baseline

## What to do

1. Apply quantization first (immediate 4x headroom)
   - [Quantization guide](https://qdrant.tech/documentation/guides/quantization/)
2. Enable mmap so the OS manages what stays in RAM
   - [Storage optimization](https://qdrant.tech/documentation/guides/optimize/)
3. Then estimate: does your target vector count fit on current hardware?

Use the memory formula from the main SKILL.md to calculate.

See `quantization-guide.md` for which quantization type to use.
See `cluster-sizing.md` if you still need more capacity after optimizing.
