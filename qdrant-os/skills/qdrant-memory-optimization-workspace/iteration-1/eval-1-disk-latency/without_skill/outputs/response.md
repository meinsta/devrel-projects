# Fixing Disk-Based Storage Latency in Qdrant

Yes, there is a middle ground. Going from full RAM to fully on-disk is the most extreme trade-off, and the 200x latency increase you're seeing (15ms to 3-4s) is expected when every vector read hits disk. Here are several strategies to get latency back into an acceptable range while still saving significant memory.

## 1. Use Memmap (mmap) Storage Instead of Pure On-Disk

Qdrant supports `mmap` as a storage option, which memory-maps vector data from disk. The OS kernel manages a page cache, keeping frequently accessed vectors in RAM automatically while allowing less-used data to spill to disk. This is the most common "middle ground" configuration.

In your collection config:

```json
{
  "vectors": {
    "on_disk": true
  },
  "optimizers_config": {
    "memmap_threshold": 20000
  }
}
```

With `memmap_threshold`, segments smaller than the threshold stay in RAM, while larger segments use mmap. The OS page cache will keep hot vectors in memory. If you have enough RAM to hold ~30-50% of your vectors in cache, you should see latencies much closer to the 15ms range for most queries.

## 2. Enable Quantization (Scalar or Product)

Quantization compresses vectors, dramatically reducing memory usage while keeping them in RAM. This is often the best first step before moving anything to disk.

**Scalar Quantization** reduces each float32 dimension to uint8, cutting memory by ~4x with minimal accuracy loss (typically <1% recall drop):

```json
{
  "quantization_config": {
    "scalar": {
      "type": "int8",
      "always_ram": true
    }
  }
}
```

**Binary Quantization** is even more aggressive (32x compression) but works best with certain embedding models (OpenAI, Cohere models tend to work well):

```json
{
  "quantization_config": {
    "binary": {
      "always_ram": true
    }
  }
}
```

The key parameter is `always_ram: true`. This keeps the quantized vectors in memory for fast initial candidate selection, while full-precision vectors can live on disk for rescoring.

## 3. Combine Quantization with On-Disk Vectors (Recommended Approach)

This is likely your best option. The pattern is:

- Store quantized vectors in RAM (small footprint)
- Store original full-precision vectors on disk
- Search uses quantized vectors for fast candidate retrieval, then rescores top candidates from disk

```json
{
  "vectors": {
    "on_disk": true
  },
  "quantization_config": {
    "scalar": {
      "type": "int8",
      "always_ram": true
    }
  }
}
```

When searching, configure rescoring:

```json
{
  "params": {
    "quantization": {
      "rescore": true,
      "oversampling": 1.5
    }
  }
}
```

With this setup, you might use only ~25% of the original RAM while getting latencies in the 20-80ms range, which is perfectly usable for a chatbot.

## 4. Put the HNSW Index in RAM, Vectors on Disk

The HNSW graph index is what guides the search. If it gets pushed to disk along with the vectors, every graph traversal step requires a disk read, which is the main reason you're seeing multi-second latencies. Make sure the index stays in RAM:

```json
{
  "hnsw_config": {
    "on_disk": false
  }
}
```

The HNSW index is much smaller than the vectors themselves (typically 5-15% of vector data size), so keeping it in RAM is a good trade-off.

## 5. Use Payload Indexes to Reduce Search Scope

If your chatbot queries can be filtered (by user, by document category, by date range), adding payload indexes lets Qdrant skip large portions of the dataset entirely:

```json
{
  "field_name": "category",
  "field_schema": "keyword"
}
```

Searching fewer vectors means fewer disk reads, which directly reduces latency even with on-disk storage.

## 6. Tune Search Parameters

Lower `ef` (the HNSW search beam width) to reduce the number of vectors that need to be read:

```json
{
  "params": {
    "hnsw_ef": 64
  }
}
```

The default is 128. Dropping to 64 halves the number of disk reads per query at the cost of some recall. For a chatbot, this trade-off is usually acceptable.

## Recommended Configuration for Your Case

Combining the most impactful options:

```json
{
  "vectors": {
    "on_disk": true
  },
  "hnsw_config": {
    "on_disk": false
  },
  "quantization_config": {
    "scalar": {
      "type": "int8",
      "always_ram": true
    }
  },
  "optimizers_config": {
    "memmap_threshold": 20000
  }
}
```

Search requests:

```json
{
  "params": {
    "hnsw_ef": 64,
    "quantization": {
      "rescore": true,
      "oversampling": 1.5
    }
  }
}
```

This keeps the HNSW index and quantized vectors in RAM (roughly 25-30% of your original memory usage) while full vectors stay on disk for rescoring only the top candidates. Expected latency should drop to 30-100ms depending on dataset size and hardware, which is fine for chatbot use.

## Quick Summary

| Strategy | Memory Savings | Expected Latency | Complexity |
|---|---|---|---|
| Full RAM (original) | 0% | ~15ms | None |
| Mmap only | 30-70% (OS managed) | 20-200ms | Low |
| Scalar quantization in RAM | ~75% | 20-40ms | Low |
| Quantization in RAM + vectors on disk | ~75-85% | 30-100ms | Medium |
| Full on-disk (current) | ~95% | 3-4s | None |

Start with scalar quantization plus on-disk vectors. That alone should solve your problem.
