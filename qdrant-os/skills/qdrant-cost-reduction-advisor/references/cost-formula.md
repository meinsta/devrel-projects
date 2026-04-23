# Qdrant Cost Formula Reference

## Base Pricing Model

Qdrant managed cloud pricing is based on three components:
- 50% memory (RAM)
- 35% compute
- 15% disk

## Unit Pricing

**RAM unit:** 8GB RAM + 32GB disk = $53/month (approximate)

**Additional disk:** $0.15/GB/month (beyond what is included with RAM units)

## Calculation Formula

```
Total RAM needed = (num_vectors * vector_dimensions * bytes_per_element) / quantization_factor

RAM units = ceil(Total RAM GB / 8)
Included disk = RAM units * 32 GB
Additional disk = max(0, total_disk_needed - included_disk)

Monthly cost = (RAM units * $53) + (additional_disk_GB * $0.15)
```

## Bytes Per Element by Quantization

| Storage Type | Bytes Per Element | Quantization Factor |
|-------------|-------------------|-------------------|
| Float32 (no quantization) | 4 bytes | 1x |
| Scalar (int8) | 1 byte | 4x |
| Binary | 0.125 bytes (1 bit) | 32x |

## Example Calculations

### Example 1: 10M vectors, 1536 dimensions (OpenAI), no quantization
```
Raw size = 10,000,000 * 1536 * 4 bytes = 61.4 GB
HNSW overhead = ~1.5x = 92 GB total RAM needed
RAM units = ceil(92 / 8) = 12 units
Monthly cost = 12 * $53 = $636/month ($7,632/year)
```

### Example 2: Same dataset, scalar quantization + mmap
```
Quantized vectors in RAM = 10,000,000 * 1536 * 1 byte = 15.4 GB
HNSW graph in RAM = ~20 GB
Total RAM = 35.4 GB
RAM units = ceil(35.4 / 8) = 5 units
Disk for full vectors = 61.4 GB (for rescoring)
Included disk = 5 * 32 = 160 GB (sufficient)
Monthly cost = 5 * $53 = $265/month ($3,180/year)
Savings: 58% cost reduction
```

### Example 3: Same dataset, binary quantization + mmap (OpenAI model)
```
Binary vectors in RAM = 10,000,000 * 1536 * 0.125 bytes = 1.9 GB
HNSW graph in RAM = ~20 GB
Total RAM = 21.9 GB
RAM units = ceil(21.9 / 8) = 3 units
Disk for full vectors = 61.4 GB
Included disk = 3 * 32 = 96 GB (sufficient)
Monthly cost = 3 * $53 = $159/month ($1,908/year)
Savings: 75% cost reduction
```

### Example 4: PointClickCare scale (462M vectors, estimated)
```
Without optimization: ~$50k/month ($600k/year)
With mmap + scalar: ~$12-17k/month ($150-200k/year)
Savings: $400-450k/year
```

## Scaling Cost Projections

**Linear scaling (no optimization applied):**
- Double vectors = double cost
- 10x vectors = 10x cost

**Optimized scaling:**
- Same RAM, add disk = cost increases 10-20%
- Add quantization = cost stays flat up to 4x data growth
- Hybrid (quantize + add some RAM) = cost increases 30-50% for 2-3x data

**When to re-evaluate:**
- Latency degrades below SLA
- Disk I/O becomes bottleneck (monitor with Qdrant metrics)
- QPS requirements increase significantly

## Optional Add-ons (can be removed to reduce cost)

| Add-on | Typical Cost | When Needed |
|--------|-------------|-------------|
| Field Dedicated Engineer (FDE) | ~$200k/year | Complex deployments, custom integrations |
| Premium Support | Variable | SLA requirements, 24/7 coverage |
| Hybrid Cloud | Premium over managed | Data residency, compliance requirements |

These are optional. Initial proposals often include them by default.
Remove if the customer doesn't need them to reduce sticker shock.
