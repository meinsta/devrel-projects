## Qdrant Quantization and Vector Storage Options: The Complete Picture

Qdrant supports **three** quantization methods and also offers datatype-level control over how vectors are stored. Here is the full breakdown.

---

### 1. Scalar Quantization

Scalar quantization converts each float32 vector component into an int8 (unsigned 8-bit integer). This reduces memory usage by roughly 4x (from 4 bytes per dimension down to 1 byte per dimension).

Key details:
- **Type parameter**: `scalar`
- **Quantile parameter**: Controls what range of values maps to the 0-255 int8 range. A typical value is 0.99, which clips the top and bottom 0.5% of outlier values. This improves accuracy by not wasting resolution on rare extremes.
- **Always_ram**: You can force the quantized vectors to stay in RAM even when the original vectors are on disk (mmap). This is a common pattern for fast approximate search followed by re-scoring with full-precision vectors from disk.
- Accuracy loss is generally small (1-4% on recall benchmarks), and the 4x memory reduction is significant.

Configuration example:
```json
{
  "quantization_config": {
    "scalar": {
      "type": "int8",
      "quantile": 0.99,
      "always_ram": true
    }
  }
}
```

---

### 2. Binary Quantization

Binary quantization is the most aggressive option. Each vector component is reduced to a single bit: 1 if the value is positive, 0 if negative. This yields a 32x memory reduction compared to float32.

Key details:
- **Type parameter**: `binary`
- Works extremely well with high-dimensional models that produce normalized embeddings, particularly OpenAI's embeddings (e.g., `text-embedding-ada-002`, `text-embedding-3-large`) and Cohere's embeddings. These models tend to have roughly balanced distributions around zero, which is what binary quantization needs.
- For lower-dimensional or non-normalized embeddings, binary quantization can cause significant accuracy loss.
- **Always_ram**: Same option as scalar, keeps quantized vectors in RAM.
- Typically used with **oversampling and re-scoring**: you search the binary index with a large oversampling factor (e.g., 3x-5x), then re-rank the candidates using the original full-precision vectors.

Configuration example:
```json
{
  "quantization_config": {
    "binary": {
      "always_ram": true
    }
  }
}
```

---

### 3. Product Quantization (PQ)

Yes, Qdrant **does** support product quantization. This is the one people often miss or are confused about. It was added later than scalar and binary quantization.

Product quantization works by splitting each vector into sub-vectors (segments), then clustering each segment independently using k-means, and storing only the cluster ID for each segment. This allows for configurable compression ratios.

Key details:
- **Type parameter**: `product`
- **Compression ratio**: Configurable. Options include `x4`, `x8`, `x16`, `x32`, `x64`. This controls how aggressively the vectors are compressed.
- **Always_ram**: Same option as the other methods.
- PQ requires a **training phase** where Qdrant runs k-means clustering on a sample of your data. This means it needs a sufficient number of vectors already uploaded before the quantization can be trained.
- Accuracy-memory tradeoff falls between scalar and binary quantization. With moderate compression (x4, x8), accuracy is close to scalar quantization. With aggressive compression (x32, x64), you get closer to binary quantization territory.

Configuration example:
```json
{
  "quantization_config": {
    "product": {
      "compression": "x16",
      "always_ram": true
    }
  }
}
```

---

### 4. Vector Datatype (float16 / uint8 storage)

Separately from quantization, Qdrant also supports specifying the **datatype** of your vectors at the collection level. This is not quantization in the traditional sense. Instead, it controls how the original vectors are stored.

Available datatypes:
- **`float32`**: Default. Standard 32-bit floating point. 4 bytes per dimension.
- **`float16`**: Half-precision floating point. 2 bytes per dimension. Gives a 2x memory reduction with minimal accuracy loss for most use cases. The vectors are stored in float16 format on disk and in memory.
- **`uint8`**: Unsigned 8-bit integer. 1 byte per dimension. Useful when your vectors are already in uint8 format (e.g., from certain image feature extractors or custom pipelines). Similar storage savings to scalar quantization, but this is the raw storage format rather than a learned quantization.

The datatype is set when creating the collection:
```json
{
  "vectors": {
    "size": 1536,
    "distance": "Cosine",
    "datatype": "float16"
  }
}
```

**You can combine datatype with quantization.** For example, you could store your vectors as float16 (2x savings) and also apply scalar quantization (further 2x savings on the quantized copy), giving you the full-precision-ish vectors in float16 for re-scoring while the quantized int8 copies sit in RAM for fast search.

---

### Summary Table

| Method | Memory per Dimension | Reduction vs float32 | Accuracy Impact | Best For |
|--------|---------------------|----------------------|-----------------|----------|
| float32 (default) | 4 bytes | 1x (baseline) | None | Maximum accuracy |
| float16 (datatype) | 2 bytes | 2x | Negligible | Easy savings, minimal tradeoff |
| Scalar (int8) | 1 byte | 4x | Small (1-4%) | General purpose compression |
| Product (PQ) | Configurable | 4x-64x | Moderate | Tunable compression |
| Binary | 1 bit | 32x | High (varies by model) | High-dim normalized embeddings |

---

### Practical Recommendations

- **Start with scalar quantization.** It is the safest option with good compression and minimal accuracy loss.
- **Use float16 datatype** if you want a no-brainer 2x reduction with almost zero accuracy cost.
- **Use binary quantization** only with compatible embedding models (OpenAI, Cohere) and always with oversampling + re-scoring enabled.
- **Use product quantization** when you need a compression ratio between scalar and binary, or when you want fine-grained control over the compression-accuracy tradeoff.
- **Combine approaches**: store original vectors as float16 on disk (with mmap), keep scalar-quantized copies in RAM, and use re-scoring. This gives you fast search with good accuracy and significant memory savings.

### Re-scoring Configuration

All quantization methods benefit from re-scoring with the original (or float16) vectors. This is configured in the search request:

```json
{
  "params": {
    "quantization": {
      "ignore": false,
      "rescore": true,
      "oversampling": 2.0
    }
  }
}
```

The `oversampling` factor controls how many extra candidates are fetched from the quantized index before re-ranking with full-precision vectors. Higher values improve accuracy but increase latency.
