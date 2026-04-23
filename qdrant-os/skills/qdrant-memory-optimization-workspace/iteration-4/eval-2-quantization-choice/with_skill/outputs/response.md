# Quantization Recommendation for 80M Vectors at 1536 Dims (OpenAI text-embedding-3-small)

## Your current memory footprint

Using the memory formula:

```
RAM = vectors * dimensions * bytes_per_element * 1.5 (HNSW overhead)
```

At float32 with no quantization:
```
80,000,000 * 1536 * 4 * 1.5 = 737 GB
```

That is 737 GB of RAM needed. This is almost certainly why you are looking at quantization.

## What Qdrant supports

Qdrant supports more quantization levels than you might expect. Not just scalar (int8) and binary (1-bit), but also float16, 4-bit, and 2-bit:

| Method | Bits | Compression | RAM for 80M vectors at 1536d | Accuracy impact |
|---|---|---|---|---|
| Float32 (current) | 32 | 1x | 737 GB | Baseline |
| Float16 | 16 | 2x | 369 GB | Negligible |
| **Scalar (int8)** | **8** | **4x** | **184 GB** | **< 1%** |
| **4-bit** | **4** | **8x** | **92 GB** | **1-3%** |
| 2-bit | 2 | 16x | 46 GB | 3-5% |
| Binary (1-bit) | 1 | 32x | 23 GB | 2-5% with rescoring |

## Recommendation: start with scalar, then consider binary

### Step 1: Scalar quantization (start here)

Scalar (int8) is always the right starting point, even when your model supports binary. It works with every embedding model, has less than 1% accuracy loss, and gives you 4x compression.

```http
PUT /collections/{collection_name}
{
  "quantization_config": {
    "scalar": {
      "type": "int8",
      "always_ram": true
    }
  }
}
```

This brings your footprint from 737 GB down to 184 GB for the quantized vectors in RAM. Combine this with mmap for the full vectors on disk, and your actual RAM usage drops to the quantized portion only.

Docs: https://qdrant.tech/documentation/guides/quantization/#scalar-quantization

### Step 2: Evaluate if you need more compression

At 80M vectors with scalar quantization, you still need ~184 GB of RAM for quantized vectors alone. If your hardware budget is smaller than that, you have excellent options because OpenAI text-embedding-3-small is compatible with aggressive quantization:

**4-bit quantization (8x, ~92 GB):** Good middle ground. 1-3% accuracy impact. Works with all models.

**Binary quantization (32x, ~23 GB):** Your model (text-embedding-3-small) is on the verified compatible list for binary quantization. This is the most aggressive option and would bring 80M vectors down to roughly 23 GB, which fits comfortably on a single modern server.

```http
PUT /collections/{collection_name}
{
  "quantization_config": {
    "binary": {
      "always_ram": true
    }
  }
}
```

**Critical settings for binary quantization:**
- You MUST use oversampling (3-5x) and rescoring. Without rescoring, recall drops to around 70%. With rescoring, it recovers to 95-98%.
- Set `always_ram: true` so the binary vectors stay in memory.
- Full-precision vectors should stay on mmap/disk for rescoring.

Docs: https://qdrant.tech/documentation/guides/quantization/#binary-quantization

### Step 3: Stack with FP16 on-disk storage

Regardless of which quantization you choose for the in-RAM vectors, you can store the on-disk full vectors as float16 instead of float32. This halves disk storage and reduces rescoring I/O. The precision difference is negligible for retrieval tasks.

This stacks with quantization: FP16 on disk, quantized vectors (int8 or binary) in RAM.

Docs: https://qdrant.tech/documentation/concepts/vectors/

## Decision matrix for your specific case

| Your constraint | Best quantization | Result |
|---|---|---|
| Need to fit on 256 GB node | Scalar (int8) + mmap | ~184 GB RAM for quantized, full vecs on disk |
| Need to fit on 128 GB node | 4-bit + mmap | ~92 GB RAM for quantized, full vecs on disk |
| Need to fit on 64 GB node | 2-bit + mmap | ~46 GB RAM for quantized, full vecs on disk |
| Need to fit on 32 GB node | Binary + mmap | ~23 GB RAM for quantized, full vecs on disk |

Since you are using OpenAI text-embedding-3-small, all of these options are viable. The model is well-suited for binary quantization with rescoring, which gives you the most aggressive compression.

## Recommended order of implementation

1. Enable mmap storage for full vectors (stops any OOM risk)
2. Apply scalar quantization with `always_ram: true` (4x reduction, safe baseline)
3. Benchmark accuracy on your queries to establish a baseline
4. If you need more compression, try binary quantization with oversampling 3-5x and rescoring enabled
5. Compare accuracy to your scalar baseline
6. Switch on-disk vectors to FP16 for disk savings and faster rescoring
7. Set memory alerting at 75-80% utilization

Keep RAM utilization under 80% for headroom during traffic spikes and segment optimization.
