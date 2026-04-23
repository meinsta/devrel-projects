# Why the Qdrant Proposal Is Higher Than Pinecone's Quote (and How to Close the Gap)

## First: Acknowledge It

Don't dismiss the concern. A 2.5x difference is real and the customer deserves a straight answer. Here's how to frame the conversation.

## The Most Likely Reason: You're Comparing Different Configurations

Pinecone's $200k quote almost certainly includes aggressive quantization baked into their pricing. From SA experience: competitors often price customers for something like product or binary quantization, then run scalar in production, creating a gap between the quoted cost and the actual spend. Pinecone in particular defaults to aggressive compression methods that reduce their infrastructure cost, and they pass some of that savings into the quoted price.

Meanwhile, our $500k proposal is probably sized for full-resolution vectors in RAM with no quantization, or it includes optional add-ons that inflate the number. This is not an apples-to-apples comparison.

### Check the Proposal for Add-ons

Look at whether the $500k proposal includes either of these:

| Add-on | Typical Cost | Should It Be There? |
|--------|-------------|---------------------|
| Field Dedicated Engineer (FDE) | ~$200k/year | Only if the customer explicitly needs embedded engineering support for complex deployments |
| Premium Support | Variable | Only if they have SLA/24x7 coverage requirements |

If either is bundled in, remove it. That alone could drop the proposal from $500k to $300k or less. Initial proposals often include these by default, and they cause sticker shock.

## How to Build an Apples-to-Apples Comparison

### Step 1: Ask What Quantization Pinecone Is Using

Ask the customer (or check Pinecone's docs for the plan they were quoted): "Do you know what compression or quantization method Pinecone is applying at that price point?" Pinecone's lower tiers use aggressive quantization that reduces accuracy. If they're pricing with binary or product quantization, you need to compare against the same compression level on Qdrant.

### Step 2: Run Our Pricing With Equivalent Quantization

Use the Qdrant cost formula to produce a matching configuration:

**Qdrant pricing breakdown:**
- Base unit: 8GB RAM + 32GB disk = ~$53/month
- Cost is driven by: 50% memory (RAM), 35% compute, 15% disk
- RAM is the single biggest cost driver

**With scalar quantization (4x RAM reduction):**
- This is the default recommendation. 90% of Qdrant customers using quantization use scalar.
- Equivalent to Pinecone's RQ (rotational quantization), which is a linear transformation + scalar quantize. Qdrant skips the preprocessing step because we know the distribution from immutable segments. Same compression ratio.
- Typical cost reduction: 50-60%

**With binary quantization (32x RAM reduction):**
- If the customer uses OpenAI `text-embedding-3-small` or similar binary-compatible models, this is viable.
- With rescoring off disk, recall goes from ~70% to 95-98%.
- Typical cost reduction: 75%

### Step 3: Present the Revised Numbers

Frame it like this:

> "The $500k proposal was sized conservatively with full-resolution vectors. When we apply the same level of compression Pinecone is using, here's what the numbers look like."

Then present two scenarios:

1. **Scalar quantization** (recommended, best accuracy/cost balance): Show the recalculated price. For context, at a PointClickCare-scale deployment (462M vectors), the cost goes from ~$600k/year unoptimized to ~$150-200k/year with mmap + scalar quantization.

2. **Binary quantization** (more aggressive, requires model compatibility check): Show an even lower number. This would likely undercut or match Pinecone's $200k.

## What to Actually Say to the Customer

Here is a talk track:

> "Great question, and I appreciate you sharing the Pinecone number. The reason there's a gap is that our initial proposal was sized conservatively without quantization applied. Pinecone's quote almost certainly assumes aggressive compression on their end.
>
> When we apply equivalent optimization on Qdrant, the pricing comes into the same range or lower. Let me show you two scenarios.
>
> With scalar quantization, which gives you a 4x reduction in RAM with minimal accuracy loss, you'd be looking at [recalculated number]. With binary quantization plus rescoring, which works well if you're using OpenAI embeddings, you'd be at [even lower number].
>
> The difference is we're transparent about what compression is being applied so you can make the accuracy/cost tradeoff intentionally, rather than having it hidden in the pricing."

## Key Talking Points

1. **Transparency over hidden defaults.** Qdrant lets the customer control their quantization strategy. Competitors often apply compression silently, which can lead to unexpected accuracy degradation or cost surprises when actual spend exceeds the quoted number.

2. **Accuracy at the same price point.** At equivalent compression, Qdrant's scalar quantization with rescoring off disk delivers better recall than competitors' binary quantization at a similar or lower cost.

3. **Don't lead with "we're cheaper."** Lead with optimization. Show the customer the levers they have: quantization method, what lives in RAM vs. disk, embedding dimensions, vector precision (FP16 vs FP32). Then let the numbers speak.

4. **Test before committing.** Offer to run a benchmark: "Let's test scalar quantization against your accuracy requirements. If it meets your SLA, the cost comes down to [X]. If we need to go more aggressive with binary, we can test that too and show you exactly what the accuracy/cost tradeoff looks like."

## Quick Reference: Optimization Levers to Reduce the Proposal

| Lever | Impact | Risk |
|-------|--------|------|
| Remove FDE/Premium Support add-ons | Can drop $200k+ immediately | None, if not needed |
| Scalar quantization | 4x RAM reduction (~50-60% cost cut) | Minimal accuracy loss, mitigated by rescoring |
| Binary quantization | 32x RAM reduction (~75% cost cut) | Requires compatible embedding model, test accuracy |
| Vectors on disk (mmap) | Frees RAM for quantized indexes | Higher latency on cold reads |
| FP16 instead of FP32 storage | 2x disk reduction | Negligible precision loss for retrieval |
| Reduce embedding dimensions | Proportional RAM reduction | Depends on model and use case |

## Relevant Docs

- [Scalar quantization](https://qdrant.tech/documentation/guides/quantization/#scalar-quantization)
- [Binary quantization](https://qdrant.tech/documentation/guides/quantization/#binary-quantization)
- [Storage configuration](https://qdrant.tech/documentation/concepts/storage/)
- [Capacity planning](https://qdrant.tech/documentation/guides/capacity-planning/)
- [Vector precision](https://qdrant.tech/documentation/concepts/vectors/)
