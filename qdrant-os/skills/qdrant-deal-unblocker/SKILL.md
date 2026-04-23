---
name: qdrant-deal-unblocker
description: Handles technical objections that block Qdrant deals
  and provides proven response playbooks. Use when a deal is
  stalled due to pricing concerns, missing features, performance
  issues, or competitive pressure. Triggers on "deal blocked",
  "customer concerned about cost", "proposal too expensive",
  "missing feature blocking production", "latency issues on call",
  "why not use pinecone", "customer built workaround", or
  "champion lost budget battle". Do NOT use for general product
  questions, documentation lookups, or technical implementation.
metadata:
  author: thierry
  version: 1.0.0
  category: sales
  tags: [deals, objections, pricing, competitive, sales]
---

# What to do when a deal is blocked by a technical objection

## Why this happens

Technical objections are the #1 deal killer. They follow four patterns:
cost sticker shock, missing feature blockers, performance concerns,
and competitive pressure. Each requires a specific response playbook.

The common thread: the customer has a real need, likes Qdrant, but
something specific is stopping them from signing. Your job is to
identify the blocker type and run the right playbook.

## Decision Tree

### Step 1: Identify the objection type

Listen for these signals:

**Cost objection signals:**
- "Too expensive" / "Over budget"
- "Need to justify ROI" / "CFO won't approve"
- "Competitor is cheaper"
- "Can't spend $X on one use case"
-> Go to Step 2: Cost Playbook

**Missing feature signals:**
- "We need X but Qdrant doesn't have it"
- "Blocking our security review"
- "Can't go to production without X"
- "Built a workaround for now"
-> Go to Step 3: Feature Gap Playbook

**Performance signals:**
- "Latency is too high"
- "Timeouts during ingestion"
- "Can't handle our scale"
- "Works in dev but not in production"
-> Go to Step 4: Performance Playbook

**Competitive signals:**
- "Why not use Pinecone/Weaviate/PGvector?"
- "Our team prefers X"
- "Competitor offered us a deal"
-> Go to Step 5: Competitive Playbook

### Step 2: Cost Objection Playbook
See `references/cost-objections.md` for the full pricing conversation framework.

**Quick response framework:**

1. **Acknowledge the concern.** Never dismiss it.
   "I understand $X feels high. Let me break down what is driving that."

2. **Explain the pricing components.**
   - 50% memory, 35% compute, 15% disk
   - FDE ($200k) and Premium support are optional, can be removed
   - Initial proposals are sized for maximum performance, not optimized

3. **Ask the diagnostic questions.**
   - What is your actual QPS requirement?
   - What latency is acceptable? (sub-100ms? sub-500ms? 1-2s okay?)
   - Have you tested quantization?
   - What accuracy threshold is acceptable?

4. **Present the optimized path.**
   Run the qdrant-cost-optimization skill or use the cost formula
   in `references/cost-formula.md` to generate three scenarios:
   - Current proposal (the number causing sticker shock)
   - Optimized config (mmap + scalar quantization)
   - Aggressive config (mmap + binary, if model is compatible)

5. **Offer proof.**
   "Let's run a POC with the optimized config to validate performance."

**Real example reframe:**
- Original PointClickCare proposal: $600k (full RAM, FDE, Premium)
- Optimized: $150-200k (mmap + scalar, standard support)
- Trade-off: minimal latency impact, 95%+ accuracy maintained
- Result: 60-70% cost reduction while meeting requirements

### Step 3: Feature Gap Playbook
See `references/feature-gap-playbook.md`

**Quick response framework:**

1. **Identify the exact missing feature.** Get specific.
   Not "security features" but "audit logging for SOC2 compliance."

2. **Check the roadmap.** Is it planned? When?
   If yes: share the timeline, offer early access or beta.
   If no: escalate to product with ARR-at-risk quantification.

3. **Find a workaround.** Can existing features cover the gap?
   - Missing audit logging? External audit proxy as interim solution.
   - Missing range-bound search? Payload filtering + post-processing.
   - Missing alerting customization? Grafana + Qdrant metrics endpoint.

4. **Quantify the business impact for product team.**
   "PointClickCare: $500k+ deal blocked by audit logging.
   April 10th production deadline. Estimated 3 more customers
   need this in Q2."

5. **Bridge the gap with professional services.**
   Offer interim architecture using existing features + custom
   integration work while the feature ships.

**Real example:**
- PointClickCare needed audit logging for security review
- Feature was missing, blocking April 10th production rollout
- Customer built in-house workaround instead of purchasing
- Money lost: $500k+ deal delayed indefinitely

### Step 4: Performance Playbook
See `references/performance-objections.md`

**Quick response framework:**

1. **Get specific numbers.** "Slow" is not actionable.
   - What latency are they seeing? (p50, p95, p99)
   - What is acceptable?
   - When does it happen? (all the time? during ingestion? at scale?)

2. **Diagnose the root cause.**
   - Latency spikes during ingestion? -> deferred indexing
   - Consistent high latency? -> check HNSW ef parameter, quantization
   - Timeouts at scale? -> sharding, instance sizing
   - 2+ second latency? -> probably full disk, need mmap + quantization

3. **Provide the fix with expected results.**
   Always give concrete numbers: "Changing ef from 512 to 128 should
   reduce p95 from 600ms to under 100ms with minimal accuracy impact."

4. **Offer managed service or FDE for complex cases.**
   If the fix requires significant architectural changes, position
   managed service or FDE as the path to resolution.

**Real examples:**
- DocketAI: 600ms to 1min spikes. Root cause: unoptimized HNSW params.
  Fix: tune ef, add quantization. Resolved with $29k managed service.
- CareerFlow: 20-30s during 4M daily job ingestion. Root cause: indexing
  not deferred during bulk loads. Fix: deferred indexing.
- Worldline: timeouts with 200 upserts/5min on 2M points. Root cause:
  instance undersized for write throughput.

### Step 5: Competitive Playbook
See `references/competitive-responses.md`

**Quick response framework:**

1. **Never trash competitors.** Win on your strengths.

2. **Identify what matters to THIS customer.**
   Not generic "Qdrant is better" but specific: "For your 4M daily
   ingestion use case, Qdrant's deferred indexing means you won't
   hit the write throughput ceiling Pinecone has."

3. **Lead with differentiators relevant to their use case:**
   - Open source: no vendor lock-in, inspect the code, self-host option
   - Hybrid cloud: data stays in your infrastructure
   - Price-performance: quantization options competitors don't offer
   - Documentation quality: ServiceNow chose Qdrant for this reason
   - Payload filtering: richer filtering than most competitors

4. **Use proof points from similar customers.**
   - ServiceNow: chose Qdrant over Pinecone and PGvector
   - Allbuyone: switching from Pinecone after price doubled

5. **Provide TCO comparison.**
   Use `references/cost-formula.md` to calculate Qdrant cost, then
   compare against competitor's published or quoted pricing.

## Common Patterns

### Customer already built a workaround
Acknowledge their investment. Do NOT tell them it was wrong.
Position Qdrant as replacing the maintenance burden:
"You have already solved the immediate problem. The question is
whether maintaining that solution long-term costs more than the
managed service. Let's calculate the total cost of ownership for both."

### Champion lost the internal budget battle
Provide ROI ammunition the champion can present to leadership:
- Competitor cost comparison (show savings)
- Infrastructure cost reduction from optimization
- Time-to-production estimates (faster = cheaper)
- Risk reduction (managed service vs self-hosted maintenance)
See `references/roi-framework.md`

### Customer wants to "start small and grow"
This is a buying signal, not an objection. Respond with:
- Managed Cloud (lowest commitment, pay-as-you-go)
- Start with one use case, prove value, expand
- Provide scaling cost projections so they can plan budget
