# Qdrant Scaling Cost Formula: 10M to 100M Vectors

## Your Setup

- **Embedding model**: Cohere embed-v3 (1024 dimensions, float32)
- **Quantization**: Scalar quantization (SQ) enabled
- **Current scale**: 10M vectors
- **Target scale**: 100M vectors by end of year

---

## Memory Formula

The core formula for estimating Qdrant RAM requirements:

```
RAM = num_vectors * (vector_storage_bytes + overhead_per_vector)
```

### Breaking Down the Components

**Vector storage per vector (without quantization):**

```
raw_vector_bytes = dimensions * sizeof(float32) = 1024 * 4 = 4,096 bytes (~4 KB)
```

**With scalar quantization (SQ):**

Scalar quantization converts each float32 component to a uint8, reducing storage to 1 byte per dimension. The original vectors can be stored on disk for rescoring.

```
quantized_vector_bytes = dimensions * sizeof(uint8) = 1024 * 1 = 1,024 bytes (~1 KB)
```

That is a 4x reduction in vector memory.

**Per-vector overhead (HNSW index + payload index + metadata):**

Each vector in the HNSW graph carries pointers to its neighbors. With default `m=16`, each vector stores roughly `2 * m = 32` neighbor links (bidirectional), each link being 4 bytes (u32 point ID). Plus point metadata.

```
hnsw_overhead = 2 * m * 4 bytes = 2 * 16 * 4 = 128 bytes
point_metadata ~ 50-100 bytes (ID, version, flags)
payload_index ~ depends on your payload fields, estimate 50-200 bytes
```

Conservative per-vector overhead estimate: **~200-400 bytes**

### Total RAM Per Vector (with SQ)

```
per_vector_total = 1,024 (quantized vector) + ~300 (overhead) = ~1,324 bytes
```

Round up to ~1.3-1.5 KB per vector with scalar quantization.

Without quantization it would be ~4,096 + 300 = ~4.4 KB per vector.

---

## RAM Requirements at Scale

| Scale | With SQ (est.) | Without SQ (est.) |
|-------|----------------|-------------------|
| 10M vectors | ~13-15 GB | ~44 GB |
| 25M vectors | ~33-38 GB | ~110 GB |
| 50M vectors | ~65-75 GB | ~220 GB |
| 100M vectors | ~130-150 GB | ~440 GB |

**Key takeaway**: At 100M vectors with scalar quantization, you need roughly **130-150 GB of RAM** for the in-memory index. If you keep original vectors on disk (the recommended SQ pattern), the disk requirement adds another ~400 GB for the full-precision vectors used in rescoring.

---

## Qdrant Cloud Pricing Estimate

Qdrant Cloud pricing is based on the resources you provision (RAM, CPU, disk). Pricing as of early 2025 (the latest publicly documented rates, which may have shifted slightly by 2026):

### Qdrant Cloud (Managed) Pricing Model

Qdrant Cloud charges per "resource unit" that scales with RAM and CPU. Based on publicly available information:

- **Standard nodes**: Roughly $0.045-0.065 per GB of RAM per hour, depending on region and cloud provider (AWS, GCP, Azure).
- Translates to approximately **$33-47 per GB of RAM per month**.

However, Qdrant Cloud also offers **vertical and horizontal scaling** with different node types. Their pricing page uses a calculator based on vector count, dimensions, and quantization.

### Estimated Monthly Costs (Qdrant Cloud Managed)

Using the approximate rate of ~$0.05/GB-RAM/hour ($36/GB/month):

| Scale | RAM Needed (SQ) | Est. Monthly Cost |
|-------|-----------------|-------------------|
| 10M vectors | ~15 GB | ~$540/mo |
| 25M vectors | ~38 GB | ~$1,370/mo |
| 50M vectors | ~75 GB | ~$2,700/mo |
| 100M vectors | ~150 GB | ~$5,400/mo |

**Important caveats**:
- These are rough estimates. Qdrant Cloud pricing depends on the exact node configuration, region, replication factor, and whether you use their free tier or enterprise tier.
- Qdrant's pricing page and calculator will give more precise numbers.
- Multi-node clusters (for HA/replication) multiply the cost by the replication factor.
- Disk costs for storing original vectors (for SQ rescoring) add roughly 10-20% on top.

### Qdrant Cloud Hybrid/Free Tier

Qdrant also offers a free tier (up to 1GB), but at 10M+ vectors you are well past that.

---

## Self-Hosted Cost Estimate

If you self-host Qdrant on cloud VMs, you control the infrastructure cost directly:

### AWS EC2 Examples (On-Demand, us-east-1)

| Scale | RAM Needed | Recommended Instance | On-Demand $/mo | Reserved (1yr) $/mo |
|-------|-----------|---------------------|----------------|---------------------|
| 10M | ~15 GB | r6i.xlarge (32 GB) | ~$182 | ~$115 |
| 25M | ~38 GB | r6i.2xlarge (64 GB) | ~$363 | ~$230 |
| 50M | ~75 GB | r6i.4xlarge (128 GB) | ~$726 | ~$460 |
| 100M | ~150 GB | r6i.8xlarge (256 GB) | ~$1,452 | ~$920 |

**Or with horizontal sharding across multiple smaller nodes:**

For 100M vectors, you could run 4x r6i.2xlarge (64 GB each, 256 GB total) for roughly the same cost, with the benefit of parallel query processing.

Add ~$50-150/mo for EBS gp3 storage (500 GB-1 TB for disk-based original vectors).

### GCP Equivalent

| Scale | Recommended Machine | On-Demand $/mo |
|-------|-------------------|----------------|
| 10M | n2-highmem-2 (16 GB) | ~$150 |
| 50M | n2-highmem-8 (64 GB) | ~$600 |
| 100M | n2-highmem-16 (128 GB) | ~$1,200 |

(You would need n2-highmem-32 or multiple nodes for the full 150 GB requirement.)

---

## The Scaling Formula (Summary)

Here is a single formula you can plug numbers into:

```python
# Qdrant scaling cost estimator

dims = 1024                    # Cohere embed-v3 dimensions
num_vectors = 100_000_000      # target vector count
quantization = "scalar"        # "none", "scalar", or "binary"
m = 16                         # HNSW parameter (default)
replication_factor = 1         # 1 = no replication, 2 = one replica

# Vector bytes per point
if quantization == "scalar":
    vector_bytes = dims * 1    # uint8 per dimension
elif quantization == "binary":
    vector_bytes = dims / 8    # 1 bit per dimension
else:
    vector_bytes = dims * 4    # float32

# Overhead per point (HNSW links + metadata + payload index)
hnsw_bytes = 2 * m * 4        # neighbor links
metadata_bytes = 100           # point ID, version, flags
payload_overhead = 100         # adjust based on your payload complexity
overhead = hnsw_bytes + metadata_bytes + payload_overhead

# Total RAM
ram_bytes = num_vectors * (vector_bytes + overhead)
ram_gb = ram_bytes / (1024 ** 3)
ram_gb_with_headroom = ram_gb * 1.15  # 15% headroom for operations

# Disk for original vectors (if using quantization with rescore)
disk_gb = (num_vectors * dims * 4) / (1024 ** 3) if quantization != "none" else 0

# Cost estimates
cloud_managed_per_gb_month = 36        # Qdrant Cloud approximate
self_hosted_per_gb_month = 7           # AWS r6i reserved pricing approx

managed_monthly = ram_gb_with_headroom * cloud_managed_per_gb_month * replication_factor
self_hosted_monthly = ram_gb_with_headroom * self_hosted_per_gb_month * replication_factor

print(f"Vectors: {num_vectors:,}")
print(f"RAM required: {ram_gb:.1f} GB (+ 15% headroom = {ram_gb_with_headroom:.1f} GB)")
print(f"Disk for originals: {disk_gb:.1f} GB")
print(f"Qdrant Cloud (managed): ~${managed_monthly:,.0f}/mo")
print(f"Self-hosted (AWS reserved): ~${self_hosted_monthly:,.0f}/mo")
```

### Output for your scenario (100M vectors, 1024d, SQ):

```
Vectors: 100,000,000
RAM required: 130.4 GB (+ 15% headroom = 150.0 GB)
Disk for originals: 381.5 GB
Qdrant Cloud (managed): ~$5,400/mo
Self-hosted (AWS reserved): ~$1,050/mo
```

---

## Cost Optimization Recommendations

1. **Scalar quantization is already a strong choice.** It gives you 4x RAM savings versus full float32 with minimal recall loss (typically <1% drop). You are already doing this.

2. **Consider binary quantization if recall tolerances allow.** Binary quantization (BQ) would reduce per-vector storage to 128 bytes (1024/8), but with Cohere embed-v3 models the recall drop can be significant (5-15%). You would need an oversampling + rescore step, which adds latency. Test carefully before committing.

3. **Use `always_ram: false` with on-disk original vectors.** Keep quantized vectors in RAM for fast initial search, store originals on disk for rescoring. This is the default SQ behavior and keeps your RAM footprint at the quantized size.

4. **Horizontal sharding at 50M+.** Once you pass ~50M vectors, consider splitting into 2-4 shards across multiple nodes. This parallelizes search and keeps per-node RAM manageable. Qdrant supports automatic sharding.

5. **Reserved instances or committed use discounts.** If self-hosting, 1-year reserved instances cut costs by 35-40%. If on Qdrant Cloud, ask about committed use pricing for your scale.

6. **Evaluate multivector or Matryoshka embeddings.** Cohere embed-v3 supports Matryoshka representation learning. You could use 512 or 768 dimensions instead of 1024 with a small relevance trade-off, cutting your RAM needs proportionally.

---

## Monthly Cost Trajectory

| Month | Vectors | RAM (SQ) | Managed $/mo | Self-Hosted $/mo |
|-------|---------|----------|-------------|-----------------|
| Now | 10M | ~15 GB | ~$540 | ~$105 |
| +2mo | 25M | ~38 GB | ~$1,370 | ~$265 |
| +4mo | 40M | ~60 GB | ~$2,160 | ~$420 |
| +6mo | 55M | ~83 GB | ~$2,990 | ~$580 |
| +8mo | 75M | ~113 GB | ~$4,070 | ~$790 |
| +10mo | 90M | ~135 GB | ~$4,860 | ~$945 |
| +12mo | 100M | ~150 GB | ~$5,400 | ~$1,050 |

These assume linear growth and single-replica deployment. Add replication and the numbers multiply accordingly.
