# Cost Objection Playbook

## The Pricing Conversation Framework

### Before the conversation
Pull up the customer's known requirements:
- Vector count and dimensions
- Current/expected QPS
- Latency requirements
- Current proposal amount

### Step 1: Acknowledge the sticker shock
"I understand $X feels high. Let me break down what is driving
that number and show you how to optimize it."

Never say: "That is actually a good price" or "Competitors charge more."
The customer's perception of cost is valid.

### Step 2: Break down the pricing model
"Our pricing has three components:"
- 50% of cost is memory (RAM)
- 35% is compute
- 15% is disk

"The proposal you received assumes full in-memory deployment,
which gives maximum performance. But most customers do not need
that configuration."

### Step 3: Identify optimization opportunities
"Let me ask a few questions to see where we can optimize:"

Questions to ask:
1. "What is your actual queries-per-second requirement?"
   (Most customers are < 100 QPS, which does not need full RAM)

2. "What latency is acceptable for your use case?"
   - Chat/conversational: < 1s is fine (mmap works)
   - Real-time autocomplete: < 100ms needed (may need RAM)
   - Batch processing: seconds are fine (disk works)

3. "Have you tested quantization? Which type?"
   (If they haven't, this is the single biggest opportunity)

4. "What accuracy threshold is acceptable?"
   (Most use cases tolerate 95-99% accuracy)

### Step 4: Present the optimized path
"Based on what you have told me, here is what I recommend:"

Present three scenarios:
| Config | Monthly Cost | Latency | Accuracy |
|--------|-------------|---------|----------|
| Current proposal (full RAM) | $X | < 10ms | 100% |
| Optimized (mmap + scalar) | $Y (60-70% less) | < 500ms | 99%+ |
| Aggressive (mmap + binary) | $Z (80-90% less) | < 200ms | 95-98% |

### Step 5: Offer proof
"I recommend we run a 2-week POC with the optimized configuration.
You will see the actual latency and accuracy numbers for your data.
If it meets your requirements, we proceed with the lower price point."

## Common cost objection patterns

### "We need a formula to calculate cost ourselves"
Response: Share the cost formula. Customers who can self-serve
pricing become faster buyers because they do not need an SA call
for every sizing question.

Base formula:
- RAM unit = 8GB RAM + 32GB disk = $53/month
- Additional disk = $0.15/GB/month
- Total = (RAM units * $53) + (extra disk * $0.15)

### "How does cost scale when we grow?"
Response: Provide scaling projections.
- With quantization: cost stays flat up to 4x data growth
- Without: linear scaling (2x data = 2x cost)
- Show the customer they can grow 4x before hitting the next
  cost tier if they optimize now

### "FDE and Premium support add too much"
Response: These are optional. Remove them from the proposal.
- FDE ($200k) is for complex deployments with custom needs
- Premium support is for strict SLA requirements
- Standard support covers most use cases
- Can always add these later when the deployment scales

### "We need cost to be 1% of revenue, not 50%"
Response: Run the optimization. With mmap + quantization, Qdrant
cost typically drops to 0.5-2% of the infrastructure budget.
Show the optimized numbers, not the unoptimized proposal.
