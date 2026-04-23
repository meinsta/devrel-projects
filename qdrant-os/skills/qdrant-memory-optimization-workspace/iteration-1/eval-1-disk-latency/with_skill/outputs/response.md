# Fixing disk-based Qdrant latency: from 3-4 seconds back to usable speeds

## What went wrong

You almost certainly switched to **full disk storage**, not **mmap**. These are fundamentally different:

- **Full disk**: Every query reads directly from disk. HNSW graph traversal requires 200-250 random reads per query. Each read hits disk cold. That is where the 3-4 second latency comes from.
- **mmap (memory-mapped files)**: Data lives on disk, but the OS transparently caches frequently accessed pages in RAM. Hot vectors and graph nodes stay in memory automatically. Cold data gets paged in on demand. Typical latency: 50-500ms.

The key insight: HNSW graph traversal is what dominates latency. If the graph is in RAM (even via mmap caching), each hop is nearly free. If every hop hits disk, you pay milliseconds per hop across 200+ hops, which compounds to seconds.

## The fix: a three-step approach

### Step 1: Switch from full disk to mmap storage

Instead of `on_disk: true` with no mmap, configure your collection to use memory-mapped storage. This tells Qdrant to memory-map the data files so the OS kernel manages the RAM-vs-disk tradeoff automatically.

```http
PUT /collections/{collection_name}
{
  "vectors": {
    "size": 1536,
    "distance": "Cosine",
    "on_disk": true
  },
  "optimizers_config": {
    "memmap_threshold": 20000
  }
}
```

Setting `memmap_threshold` controls when segments switch to mmap. With this configuration, the OS will keep your HNSW graph and frequently queried vectors in the page cache while letting rarely accessed data stay on disk.

Reference: [Storage configuration docs](https://qdrant.tech/documentation/concepts/storage/)

### Step 2: Add scalar quantization with `always_ram=true`

This is the real performance unlock. Scalar quantization compresses each float32 element to int8, giving a 4x memory reduction. Setting `always_ram=true` forces the quantized vectors into RAM so the initial approximate search is extremely fast. Full-resolution vectors stay on disk and are only loaded for the final rescoring step on the small set of top candidates.

```http
PUT /collections/{collection_name}
{
  "vectors": {
    "size": 1536,
    "distance": "Cosine",
    "on_disk": true
  },
  "quantization_config": {
    "scalar": {
      "type": "int8",
      "quantile": 0.99,
      "always_ram": true
    }
  }
}
```

When searching, enable rescoring to recover accuracy:

```http
POST /collections/{collection_name}/points/query
{
  "query": [0.1, 0.2, ...],
  "limit": 10,
  "params": {
    "quantization": {
      "rescore": true
    }
  }
}
```

Reference: [Quantization with rescoring](https://qdrant.tech/documentation/guides/quantization/#setting-up-quantization-in-qdrant)

### Step 3: Verify the HNSW index is using mmap (not full disk)

Make sure the HNSW graph itself is memory-mapped. The graph structure is relatively small compared to vector data, and keeping it accessible in RAM (via mmap page cache) is what makes the difference between milliseconds and seconds.

```http
PATCH /collections/{collection_name}
{
  "hnsw_config": {
    "on_disk": false
  }
}
```

If your machine has enough RAM to hold the HNSW graph, keep `hnsw_config.on_disk` set to `false` (the default). Only move the graph to disk if you are truly out of memory, and even then, mmap is preferable to raw disk reads.

## Expected results

| Configuration | Typical latency | RAM usage |
|---|---|---|
| Full RAM (your original setup) | ~15ms | Very high |
| Full disk (your current setup) | 3-4 seconds | Very low |
| mmap + scalar quantization with `always_ram` | 50-200ms | Moderate (quantized vectors + HNSW in RAM, full vectors on disk) |

For a chatbot, 50-200ms search latency is completely workable. You save most of the memory that was causing problems, and your users will not notice the difference from 15ms.

## Memory math to confirm this fits

Use this formula to estimate how much RAM the quantized vectors need:

```
RAM for quantized vectors = num_vectors * dimensions * 1 byte (int8)
HNSW overhead             = ~1.5x the quantized vector size
Total RAM (approx)        = num_vectors * dimensions * 1 * 1.5
```

For example, with 10M vectors at 1536 dimensions:
- Full float32 in RAM: ~92 GB
- Scalar quantized with `always_ram`: ~23 GB
- Full vectors stay on disk, loaded only during rescoring

## What NOT to do

- **Do not go back to full RAM.** You switched to disk for a reason. The middle ground exists.
- **Do not leave quantized vectors on disk.** If `always_ram` is not set, the quantized vectors compete with the OS page cache and you lose the speed benefit.
- **Do not skip rescoring.** Without rescoring, quantized search has slightly lower recall. With rescoring enabled, accuracy recovers to within 1% of the full-precision search.

## Further reading

- [Storage configuration](https://qdrant.tech/documentation/concepts/storage/)
- [Quantization guide](https://qdrant.tech/documentation/guides/quantization/)
- [Optimization settings](https://qdrant.tech/documentation/guides/optimize/)
