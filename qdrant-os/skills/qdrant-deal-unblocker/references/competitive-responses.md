# Competitive Response Playbook

## General rules
1. Never trash competitors. Win on your strengths.
2. Get specific about what matters to THIS customer.
3. Use proof points from similar customers.
4. Always offer a TCO comparison with real numbers.

## vs Pinecone

**Qdrant advantages:**
- Open source: inspect the code, no vendor lock-in
- Hybrid cloud: data stays in your infrastructure (compliance)
- Richer quantization options (scalar, binary, product)
- Payload filtering: more powerful filtering on metadata
- Self-host option: zero egress costs, full control
- Price: typically 30-50% less at comparable scale

**When customers mention Pinecone:**
- "Pinecone doubled their prices" (Allbuyone pattern)
  Response: Calculate TCO for both. Show the savings over 2-3 years.
  Highlight that Qdrant's open-source base prevents lock-in.

- "Our team already knows Pinecone"
  Response: Migration is straightforward. Qdrant client libraries
  follow similar patterns. Offer migration support.

**Proof point:** ServiceNow evaluated Pinecone, PGvector, and Qdrant.
Chose Qdrant for documentation quality and performance.

## vs Weaviate

**Qdrant advantages:**
- Performance: faster at scale (especially with quantization)
- Simpler architecture: no GraphQL dependency
- Better quantization options
- Lighter resource footprint

**When to use:** Customer is evaluating both for production deployment.
Focus on operational simplicity and performance benchmarks.

## vs PGvector

**Qdrant advantages:**
- Purpose-built for vector search (not bolted onto PostgreSQL)
- Horizontal scaling (PGvector is limited to single node for vectors)
- HNSW parameters are tunable (PGvector has limited tuning)
- Quantization support (PGvector has none or limited)
- Dedicated filtering and payload support

**When to use:** Customer has PostgreSQL and thinks adding pgvector
is "free." It is free until they hit scale, then they face major
re-architecture.

**Proof point:** ServiceNow chose Qdrant over PGvector for this reason.

## vs Elasticsearch/OpenSearch vector search

**Qdrant advantages:**
- Purpose-built architecture (not a text search engine with vectors added)
- Better recall at same latency
- Lower resource usage per vector
- Simpler to operate for vector-only workloads

**When to use:** Customer already uses Elasticsearch and thinks they
can "just add" vector search. Works for simple cases, breaks at scale.

## TCO comparison template

For any competitor comparison, calculate:

| Factor | Qdrant | Competitor |
|--------|--------|-----------|
| Base infrastructure cost/month | $ | $ |
| Egress costs (if cloud) | $ | $ |
| Support costs | $ | $ |
| Migration cost (one-time) | $ | N/A |
| Lock-in risk (qualitative) | Low (open source) | High/Medium |
| 1-year total | $ | $ |
| 3-year total | $ | $ |

Always show the 3-year number. Qdrant's advantage compounds over time
because: no surprise price increases (open source), optimization
reduces cost over time, no egress fees with hybrid cloud.
