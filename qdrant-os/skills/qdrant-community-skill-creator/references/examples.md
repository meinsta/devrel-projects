# Example community skill: qdrant-memory-optimization

This is a deployed community skill you can reference when building new ones.

## Overview

**Name:** qdrant-memory-optimization
**Category:** operations
**R-16 answer:** "Claude frequently states incorrect quantization options,
wrong units for memmap_threshold, and does not know about GPU-accelerated
HNSW indexing."

## What makes it good

### 1. Corrections section upfront

The skill leads with specific things Claude gets wrong:

```markdown
## Things Claude gets wrong about Qdrant

- **Qdrant DOES support FP16 vector storage.** Claude often says
  Qdrant only supports float32.
- **Qdrant supports 1-bit, 2-bit, 4-bit, and 8-bit quantization.**
  Not just binary and scalar.
- **memmap_threshold is measured in number of vectors, not kilobytes.**
```

This is the core value of the skill. Without these corrections,
there is no reason for the skill to exist.

### 2. Symptom routing with developer language

The routing table uses phrases developers actually say:

| Symptom | Reference |
|---------|-----------|
| OOM crashes, node killed by OS | oom-diagnosis.md |
| Latency 2+ seconds after switching to disk | disk-latency.md |
| Which quantization to pick | quantization-guide.md |

Not product feature names, but actual error symptoms.

### 3. Memory formula with concrete examples

```
RAM needed = vectors * dimensions * bytes_per_element * 1.5

10M vectors, 1536 dims (OpenAI):
  float32: 92 GB
  scalar:  23 GB
  binary:   3 GB
```

Concrete numbers let developers immediately estimate their needs.

### 4. Anti-patterns section

```markdown
## Do NOT recommend

- "Just add more RAM" as primary solution
- Full disk storage for real-time use cases (2-5s latency)
- Binary quantization for models with < 384 dimensions
- Skipping rescoring with binary quantization (recall drops to ~70%)
```

Prevents the most common bad advice.

### 5. Decision tree with concrete thresholds

```
Qdrant memory problem
  |
  +-- OOM crashes
  |   -> Enable mmap immediately, then quantization
  |
  +-- Latency spiked after switching to disk
  |   -> Switch from full disk to mmap + quantization
  |
  +-- Memory too high, need to scale
      -> Quantization (4-32x), then mmap
```

Each branch leads to a specific action, not vague advice.

### 6. Troubleshooting with root cause analysis

```markdown
### "I enabled quantization but memory didn't decrease"
**Cause:** always_ram not set, so both original and quantized
vectors compete for memory.
**Fix:** Verify always_ram=true, ensure originals are on mmap/disk.
```

Real error messages developers encounter, with actionable fixes.

## Trigger patterns

### Positive triggers (should activate)
- "qdrant keeps getting OOM killed on our k8s cluster"
- "memory at 87% with only 200 users"
- "switched from RAM to disk, latency went from 15ms to 3-4 seconds"
- "what quantization should we use for openai embeddings"
- "mmap vs RAM for 50M vectors at 1536 dims"

### Negative triggers (should NOT activate)
- "how do I install qdrant on kubernetes"
- "what embedding model should I use"
- "our recall is 70%, how to improve accuracy"
- "compare qdrant vs pinecone"
- "how to set up monitoring with prometheus"

## Pattern summary for community skills

| Pattern | Implementation |
|---------|---------------|
| R-16 value | "Things Claude gets wrong" corrections section |
| Symptom-first | Routing table uses developer language |
| Concrete thresholds | Formulas and numbers, not vague advice |
| Anti-patterns | "Do NOT recommend" prevents bad advice |
| Public references only | All links to qdrant.tech documentation |
| Progressive disclosure | Body = when/why, references = how |
