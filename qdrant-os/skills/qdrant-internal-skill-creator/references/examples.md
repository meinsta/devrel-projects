# Example internal skills

These are deployed internal skills you can reference when building new ones.

## Example 1: qdrant-cost-reduction-advisor

**Category:** sales
**R-16 answer:** "SA pricing conversation frameworks and real customer
cost reduction scenarios that Claude cannot access from public docs."

### What makes it good

1. **Symptom-first routing:** Starts with what the customer says
   ("too expensive", "need to reduce cost"), not what feature to use.

2. **SA quotes as primary content:**
   ```
   "We recommend our customers to use scalar if they want to try
   that first just to see what the improvement is going to be in
   terms of cost."
   ```

3. **Real numbers from real deals:**
   - PointClickCare: $600k proposal optimized to $150-200k
   - Startup: expected $3-5k, quoted $18k, optimized with quantization

4. **Decision tree with concrete thresholds:**
   ```
   Customer says "too expensive"
     -> High RAM usage?
       -> Full resolution vectors in memory?
         -> Apply scalar quantization (4x reduction)
       -> Already using scalar?
         -> Apply binary quantization (32x reduction)
   ```

5. **Anti-patterns section:**
   - Do NOT lead with "Qdrant is cheaper than competitors"
   - Do NOT quote dollar amounts without running the formula
   - Do NOT recommend binary quantization without confirming model compatibility

### Trigger patterns

Positive: "this $600k proposal is way too expensive", "need to reduce
qdrant cost by 50%", "customer comparing our pricing to pinecone"

Negative: "how do I install qdrant", "what embedding model should I use",
"our search recall is 70%"

---

## Example 2: qdrant-deal-unblocker

**Category:** sales
**R-16 answer:** "Internal objection-handling playbooks with real customer
names, deal values, and proven response frameworks."

### What makes it good

1. **Four objection types with signal detection:**
   - Cost signals: "too expensive", "over budget", "CFO won't approve"
   - Feature signals: "we need X but Qdrant doesn't have it"
   - Performance signals: "latency is too high", "timeouts"
   - Competitive signals: "why not use Pinecone"

2. **Structured playbooks for each type:**
   Each playbook follows: Acknowledge -> Diagnose -> Present fix -> Offer proof

3. **Real customer examples with outcomes:**
   - DocketAI: 600ms to 1min spikes, resolved with $29k managed service
   - CareerFlow: 20-30s during 4M daily ingestion, fixed with deferred indexing
   - PointClickCare: $500k deal delayed by missing audit logging

4. **Common patterns section instead of generic troubleshooting:**
   - "Customer already built a workaround" (do not tell them it was wrong)
   - "Champion lost the budget battle" (provide ROI ammunition)
   - "Start small and grow" (this is a buying signal, not an objection)

---

## Example 3: qdrant-memory-optimization

**Category:** operations
**R-16 answer:** "Memory behavior specifics, quantization bit-width options,
and GPU indexing that Claude frequently states incorrectly."

### What makes it good

1. **Corrections section upfront:**
   - "Qdrant DOES support FP16 vector storage" (Claude often says it does not)
   - "Qdrant supports 1-bit, 2-bit, 4-bit, and 8-bit quantization"
   - "memmap_threshold is measured in number of vectors, not kilobytes"

2. **Memory formula with concrete examples:**
   ```
   10M vectors, 1536 dims:
     float32: 92 GB
     scalar:  23 GB
     binary:   3 GB
   ```

3. **Reference file per symptom:**
   - oom-diagnosis.md, disk-latency.md, quantization-guide.md,
     cluster-sizing.md, scaling-memory.md, storage-tiers.md

4. **Three troubleshooting cases with root cause analysis:**
   - "Enabled quantization but memory didn't decrease" (always_ram not set)
   - "Memory keeps growing with stable vector count" (payload indexes)
   - "Crashes again after a few hours" (mmap page loading behavior)

---

## Pattern summary

All three examples share these characteristics:

| Pattern | How it appears |
|---------|---------------|
| Symptom-first | Routing table maps customer language to references |
| SA quotes | Real conversation snippets, not generic advice |
| Concrete thresholds | "10M vectors", "$600k proposal", "4x reduction" |
| Anti-patterns | Explicit "Do NOT recommend" section |
| Progressive disclosure | Body = when/why, references = how |
| Real examples | Named customers, specific dollar amounts, measurable outcomes |
