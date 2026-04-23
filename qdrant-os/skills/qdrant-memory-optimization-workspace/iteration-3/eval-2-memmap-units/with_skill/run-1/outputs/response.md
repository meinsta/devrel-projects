# Complete Picture of Qdrant Quantization and Vector Storage Options

## The Short Answer

Qdrant supports **six** levels of vector precision, not just two or three. The confusion comes from older documentation and outdated information circulating online. Here is the full list:

| Method | Bits per Element | Compression vs Float32 | Bytes per Dimension |
|--------|-----------------|----------------------|---------------------|
| Float32 (default, no quantization) | 32 | 1x (baseline) | 4.0 |
| **Float16 (FP16)** | 16 | 2x | 2.0 |
| Scalar (int8) | 8 | 4x | 1.0 |
| **4-bit quantization** | 4 | 8x | 0.5 |
| **2-bit quantization** | 2 | 16x | 0.25 |
| Binary (1-bit) | 1 | 32x | 0.125 |

On top of these, Qdrant also supports **product quantization**, which is a configurable compression method with tunable parameters.

---

## Float16 (FP16) Storage

Yes, Qdrant supports storing vectors as float16. This halves storage compared to float32 with negligible recall impact for retrieval tasks.

**When to use it:** Consider this as a baseline optimization for every collection. If you are already using quantized vectors (int8 or smaller) in RAM for search, the full vectors stored on disk do not need float32 precision. FP16 is sufficient for rescoring.

**Key insight:** FP16 stacks with quantization. You can store FP16 full vectors on disk while keeping scalar-quantized (int8) vectors in RAM. This saves disk space and reduces I/O during rescoring.

Docs: https://qdrant.tech/documentation/concepts/vectors/

---

## Scalar Quantization (int8, 8-bit)

Compresses each float32 value (4 bytes) down to int8 (1 byte). 4x memory reduction.

**This is your starting point.** It works with every embedding model and causes less than 1% accuracy loss in typical scenarios. Only move to smaller bit-widths after confirming scalar quantization is insufficient for your memory target.

**Configuration essentials:**
- Set `always_ram: true` so the quantized vectors stay in memory while full vectors live on disk. Without this, you lose the speed benefit.
- Enable rescoring against full vectors for best accuracy.

Docs: https://qdrant.tech/documentation/guides/quantization/#scalar-quantization

---

## 4-bit and 2-bit Quantization

These sit between scalar and binary. They provide a middle ground that many people miss:

- **4-bit** gives 8x compression with 1-3% accuracy impact
- **2-bit** gives 16x compression with 3-5% accuracy impact

**When to use:** When scalar (4x) is not enough compression but binary (32x) is too aggressive or your model is not compatible with binary quantization.

Docs: https://qdrant.tech/documentation/guides/quantization/

---

## Binary Quantization (1-bit)

The most aggressive built-in quantization: 32x memory reduction. Each float32 dimension gets reduced to a single bit.

**Critical constraint:** Only works well with specific models. You MUST use oversampling (3-5x) and rescoring, otherwise recall drops to roughly 70%. With proper rescoring, recall recovers to 95-98%.

**Compatible models (verified):**
- OpenAI text-embedding-3-small / text-embedding-3-large
- OpenAI text-embedding-ada-002
- Cohere embed-v3 (embed-english-v3.0, embed-multilingual-v3.0)
- Jina embeddings v2+
- Gemini text-embedding-004

**Not compatible (significant accuracy loss):**
- Most open-source models without normalization
- Models with fewer than 384 dimensions
- Models not trained with cosine similarity

Docs: https://qdrant.tech/documentation/guides/quantization/#binary-quantization

---

## Product Quantization

Yes, Qdrant does support product quantization. It provides configurable compression (typically 8-16x) and is more complex to tune than scalar or binary.

**When to use:** When scalar quantization is not enough reduction but binary is not compatible with your model. Product quantization is essentially the "last resort" option for models that cannot use binary quantization but need more than 4x compression.

Docs: https://qdrant.tech/documentation/guides/quantization/#product-quantization

---

## Concrete Memory Estimates

Using the formula: `RAM = vectors * dimensions * bytes_per_element * 1.5` (the 1.5x accounts for HNSW index overhead).

For 10 million vectors at 1536 dimensions (OpenAI):

| Method | RAM Required |
|--------|-------------|
| Float32 (no quantization) | ~92 GB |
| Float16 | ~46 GB |
| Scalar (int8) | ~23 GB |
| 4-bit | ~12 GB |
| 2-bit | ~6 GB |
| Binary (1-bit) | ~3 GB |

---

## Recommended Order of Operations

1. **Start with FP16 on disk.** Free 2x disk savings with no accuracy cost.
2. **Add scalar quantization in RAM.** 4x compression on top of FP16 for the in-memory working set.
3. **If not enough, try 4-bit or 2-bit quantization.**
4. **If your model is compatible, try binary with rescoring.**
5. **Product quantization as a last resort** for incompatible models that need high compression.

The best practice for most production deployments is **mmap + scalar quantization**: quantized vectors in RAM for fast initial search, full vectors on disk via mmap for rescoring. This delivers near-RAM latency (50-500ms p95) at roughly 4-5x lower memory usage than keeping everything in RAM.

---

## Summary

The confusion you are seeing comes from incomplete information. Qdrant supports scalar (int8), 4-bit, 2-bit, binary (1-bit), and product quantization, plus FP16 as a storage datatype. The answer "only scalar and binary" is outdated. The complete compression spectrum ranges from 2x (FP16) all the way to 32x (binary), with several options in between.
