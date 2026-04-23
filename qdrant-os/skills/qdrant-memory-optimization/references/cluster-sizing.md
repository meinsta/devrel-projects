# Cluster Sizing Guide

## When to shard

Sharding splits a collection across multiple nodes. More nodes means
more total memory, but also more overhead.

**Shard when:**
- Single node cannot hold the data (even with quantization)
- QPS exceeds single node capacity (typically > 200-500 QPS)
- You need horizontal scaling for availability

**Do NOT shard when:**
- Data fits on a single node with quantization
- QPS is low (< 100)
- Sharding "just in case" without current need

## Right-sizing checklist

Run through this in order. Each step may eliminate the need for the next:

1. **Is quantization applied?** If not, apply it first (4-32x reduction).
2. **Is mmap enabled?** If not, enable it (70-80% memory reduction).
3. **Does the data fit on a single node now?** If yes, use one node.
4. **Is QPS exceeding single-node capacity?** If yes, add shards.
5. **Is replication factor higher than your SLA requires?**
   - Factor 1: no redundancy (dev/staging only)
   - Factor 2: survives single node failure (recommended for production)
   - Factor 3: survives two failures (strict SLA only)
6. **Are there unused collections?** Delete them.

## Memory math by node count

```
Memory per shard = total_vector_memory / num_shards
Each replica doubles the memory for that shard

Total memory = shards * replicas * per_shard_memory
```

Before adding nodes, always try:
1. Quantization (reduces data 4-32x)
2. mmap storage (reduces resident memory)
3. Larger single node (often more efficient than multiple small nodes)

Docs: https://qdrant.tech/documentation/guides/distributed_deployment/
