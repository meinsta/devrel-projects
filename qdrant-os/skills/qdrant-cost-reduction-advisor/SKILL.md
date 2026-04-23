---
name: qdrant-cost-reduction-advisor
description: Diagnoses when and why to recommend specific cost
  optimization techniques for Qdrant customers. Use when a customer
  or SA says "too expensive", "need to reduce cost", "pricing too
  high", "how to lower price", "sticker shock", or asks about scaling
  costs. Also trigger when a deal is blocked by pricing, a customer
  compares competitor pricing, a startup says the quote is too high,
  or someone needs a formula to predict costs at scale. This skill
  answers "when should I recommend scalar vs binary quantization?" not
  "how to configure quantization." Do NOT use for general Qdrant setup,
  feature requests, or implementation how-tos.
license: Apache-2.0
metadata:
  author: thierry
  version: 1.0.0
  category: sales
  tags: [cost, pricing, quantization, deals, scaling, ram]
---

# When and why to recommend cost reduction techniques

This skill converts SA knowledge into a navigation system over Qdrant
documentation. It answers "when?" and "why?" for cost reduction, not "how?"
Every solution links to docs for implementation details.

## Symptom routing

| Customer signal | Go to | Load reference |
|----------------|-------|----------------|
| "Too expensive", sticker shock on proposal | Symptom 1 below | `references/cost-formula.md` |
| "How much will it cost at X scale?" | Symptom 2 below | `references/cost-formula.md` |
| "Competitor is cheaper" | Symptom 3 below | `references/competitive-pricing.md` |
| Startup, budget-constrained | Symptom 4 below | `references/cost-formula.md` |

## Do NOT recommend

- Do NOT lead with "Qdrant is cheaper than competitors." Lead with optimization.
- Do NOT quote specific dollar amounts without running the formula in `references/cost-formula.md` first.
- Do NOT recommend binary quantization without confirming model compatibility.
- Do NOT dismiss the customer's cost concern. Acknowledge it, then optimize.
- Do NOT include FDE ($200k) or Premium support in proposals unless the customer explicitly needs them.

## Symptom 1: Customer says "pricing is too expensive"

### When does this happen?
- Customer states "the price is killing us" if they have to scale using RAM
- Wants to reduce projected monthly cost from $500,000 to $50,000-$60,000
- Current pricing proposal is too expensive for seed-stage startup

### Diagnosis: What's driving the cost?

**Step 1: Check what's in memory**
- By default, Qdrant stores vectors on disk then memory-maps to keep
  everything within memory. If someone explicitly sets `on_disk=false`
  in vector configuration, that brings full resolution vectors into memory.
- RAM is the number that drives the core unit cost. That's where most of
  the operational and compute work happens with Qdrant.

**Step 2: Check embedding dimensions**
- Higher dimensions = more RAM = higher cost
- The dimension model itself doesn't change Qdrant infrastructure pricing,
  but it determines how much RAM each vector consumes

**Step 3: Check quantization status**
- "Where are you at right now in the strategy around quantization and
  trying to understand your real cutoff for accuracy as you compress
  further? That right there is the single biggest driver of the RAM."

### Solutions (ordered by impact)

#### Option 1: Apply scalar quantization (4x RAM reduction)
- **When to recommend:** Default first step. "We recommend our customers
  to use scalar if they want to try that first just to see what the
  improvement is going to be in terms of cost."
- **Best for:** "90% of our customers that are using quantization are
  usually using scalar. We very rarely offload vectors to disk just
  because quantization works so well."
- **Trade-off:** "We're cutting our costs with quantization, but our
  precision is lower than we would like."
- **Mitigation:** Rescore against original vectors on disk. "But now our
  latency is 2 seconds instead of 1 second."
- **Example:** "You can go to product quantization with a 64x compression
  ratio and then you would lower your cost. If I gave you a number of
  like 42k, with product quantization you could go to like 36."
- [Scalar quantization docs](https://qdrant.tech/documentation/guides/quantization/#scalar-quantization)

#### Option 2: Apply binary quantization (32x RAM reduction)
- **When to recommend:** "If you use OpenAI text embedding 3 small, it
  was trained to be binary quantization compatible. Binary quantization
  allows for a 32x reduction in the storage requirement. We also provide
  1.5 and 2 bit quantization methods that are 16x and 24x reduction."
- **Best for:** "With rescoring we're able to go from like 70% typically
  in terms of the recall to like 98% by rescoring the vectors using the
  full resolution representation from disk."
- **Trade-off:** "There's a cost and that is the accuracy of your results.
  That's something that you would have to test to be certain if that works."
- **Example:** "OpenAI text embeddings perform very well with binary
  quantization with rescoring off disk. You fetch top 50 using binary
  quantization, rank them, then grab the FP16 vectors from disk and
  rescore them."
- [Binary quantization docs](https://qdrant.tech/documentation/guides/quantization/#binary-quantization)

#### Option 3: Move vectors to disk (keep quantization in memory)
- **When to recommend:** "We tested, what about if we just persist the
  vectors in disk and then have a small cache instead of having this
  massive cache? The numbers were still a few seconds to retrieve."
- **Best for:** "The quantization is the one that is much needed, then
  the HNSW and vector sectors can still be on the disk and we can still
  pull them very fast."
- **Trade-off:** "What's slow is going to be the traversal through the
  HNSW graph. Qdrant has to go to disk to fetch the links, the edges.
  The fact that you have to hit disk maybe 200-250 times for a single
  traversal means you're incurring cold start latencies for each fetch."
- **Performance impact:** "If you're traversing the HNSW graph in RAM,
  it's nearly instantaneous, very low milliseconds. On disk, you're
  entering high tens of milliseconds or possibly hundreds. It'll be
  orders of magnitude faster by just keeping the graph in memory."
- [Disk storage configuration](https://qdrant.tech/documentation/concepts/storage/)

#### Option 4: Reduce dimension size
- **When to recommend:** "At that scale, the loss of information from
  binary and scalar quant in particular, you might actually have a bit
  of benefit. You might not get much information loss because those
  vectors are so huge."
- **Example:** Use `text-embedding-3-small` truncated to 512 instead of
  `text-embedding-3-large` at 3072.
- [Embedding model selection](https://qdrant.tech/documentation/guides/quantization/)

#### Option 5: Store vectors as FP16 instead of FP32
- **When to recommend:** "You can truncate the resolution of the vectors
  on disk to be float 16. That way the storage will be half of what
  you're currently doing because you're probably using float 32."
- **Trade-off:** "Lose the precision, but especially if you're going to
  be using the quantized vectors regardless, why would you not do it?
  For retrieval tasks, we find it's often not even measurable in terms
  of the impact on recall."
- [Vector precision configuration](https://qdrant.tech/documentation/concepts/vectors/)

## Symptom 2: Customer asks "how much will it cost to scale?"

### When does this happen?
- Customer needs predictable costing to pass to their client
- Needs transparency: look at a meter, understand consumption, calculate
  unit economics, create predictable forecasts
- Needs a formula to calculate cost based on cluster size (RAM, CPU, disk)

### Diagnosis: What's the scaling pattern?

**Pattern 1: Linear scaling (same configuration)**
- "If you keep everything the same, keep the quantization method the same,
  if you double the data set size, you're doubling your costs. It's just
  like doubling of the storage and the RAM."

**Pattern 2: Optimize at scale**
- "What we see is people don't necessarily fix a percentage of their data
  set in RAM. They will simply keep the same nodes, same RAM config,
  then add more data and put it all on disk until they say 'this is no
  longer meeting my throughput SLAs and I need to increase RAM.'"
- "When I do the calculation I typically try to make sure RAM utilization
  is not above like an 80% threshold. That way there's still enough room
  for the system to operate."

### Solutions

**Provide scaling scenarios:**
- "We have one option with the same quantization strategy and one with a
  more aggressive strategy which we think can still hit your targets.
  That's to be determined when we do some testing. This gives you a
  range of where you might land."
- Example: Show Year 1 (100M vectors, scalar) vs Year 2 (200M vectors, binary)
- See `references/cost-formula.md` for the calculation methodology
- [Capacity planning guide](https://qdrant.tech/documentation/guides/capacity-planning/)

## Symptom 3: Customer compares to competitor pricing

### When does this happen?
- Customer discovered pricing is 5x higher than competitors
- Price difference may be due to quantization methods used by other vendors

### Diagnosis: What are competitors doing?

**Check competitor quantization:**
- "My experience with some competitors is that they'll often price people
  for something like product and binary but then do a scalar in production,
  and there's a discrepancy between the actual spend."
- "The RAM requirement for scalar would be 4x what you're seeing on the
  left. You can imagine 4x the price essentially."

### Solutions

**Show apples-to-apples comparison:**
- "Scalar is the same compression ratio with RQ (rotational quantization).
  What Weaviate does is a linear transformation on the vectors to rotate
  them along an axis to make the variance more uniform, then scalar
  quantize. We truncate to int8 but skip the preprocessing step because
  we know the distribution from immutable segments."
- Example: "Competitor is $200k with binary quantization. We're $150k
  with scalar quantization (better accuracy)."
- See `references/competitive-pricing.md` for specific comparisons

## Symptom 4: Customer is seed-stage startup / budget-constrained

### When does this happen?
- Startup says current pricing is too high for their stage
- Customer did rough calculation, expected 3-5k, actual quote was 6x higher

### Diagnosis: What's the minimum viable configuration?

**Check current scale:**
- What vector count? What growth rate?
- "If you looked into quantization, that's something we should definitely
  check out to keep costs down."

### Solutions

**Start small, scale later:**
- "For 50 million vectors with scalar quantization: $600 a month. If you
  just double it, you're looking at $1,300. For 100 million: $1,370."
- "With binary quantization with rescoring off disk, you're able to
  achieve probably somewhere between 95-98% recall."
- "Let's say we went to binary quantization. That number drops down
  close to $4,000 a month."

## Common Patterns

### "Everything is on disk but cost is still high"
- **Root cause:** "This is very CPU intensive software. Your RAM in that
  case is like 9,000 gigabytes, so 9 terabytes. It's expensive."
- **Fix:** Apply quantization first, then move to disk.

### "Quantization didn't reduce cost enough"
- **Root cause:** "I just had a situation where I told somebody to set
  quantized vectors to be in RAM and full resolution vectors on disk.
  But they did sort of the opposite. People get tripped up on where
  the configuration is."
- **Fix:** Verify RAM configuration is set correctly. Otherwise you
  don't benefit from the efficiency gains of quantization.

### "Need to reduce cost but can't sacrifice accuracy"
- **Root cause:** "We would need to experiment with how important the
  extra accuracy is. Could we get by with binary quantization and take
  a little more noise to save cost, maybe decrease the latency because
  2 seconds starts to become problematic. But if it was 500 milliseconds
  with some decrease in accuracy, that might be where we want to end up."
- **Fix:** Rescore off disk using full precision vectors. Traverse the
  graph in memory using binary quantized vectors, grab top 100 results,
  then fetch full precision vectors off disk for those 100 and re-rank.
  Also oversample: if you want top 100, oversample by a factor of two.

## Decision Tree

```
Customer says "too expensive"
  |
  v
What's driving cost?
  |
  +-- High RAM usage
  |   |
  |   +-- Full resolution vectors in memory?
  |   |   -> Apply scalar quantization (4x reduction)
  |   |   -> https://qdrant.tech/documentation/guides/quantization/#scalar-quantization
  |   |
  |   +-- Already using scalar?
  |   |   -> Apply binary quantization (32x reduction)
  |   |   -> https://qdrant.tech/documentation/guides/quantization/#binary-quantization
  |   |
  |   +-- Already using binary?
  |       -> Move vectors to disk
  |       -> https://qdrant.tech/documentation/concepts/storage/
  |
  +-- High dimension count
  |   -> Reduce embedding dimensions
  |   -> https://qdrant.tech/documentation/guides/quantization/
  |
  +-- Need predictable scaling
      -> Provide scaling scenarios
      -> See references/cost-formula.md
```
