# Feature Gap Playbook

## When a missing feature blocks a deal

### Step 1: Get specific about what is missing
Not "security features" but the exact capability:
- Audit logging (SOC2/HIPAA compliance)
- Range-bound search (numeric range queries)
- Custom alerting thresholds (beyond 80% single threshold)
- Role-based access control
- Data encryption at rest with customer-managed keys

### Step 2: Check the roadmap
Contact product team with:
- Feature name (specific)
- Customer name and deal size (ARR at risk)
- Timeline requirement (when do they need it?)
- Competitive context (does the competitor have it?)

### Step 3: Find a workaround

**Missing audit logging:**
- Interim: deploy an audit proxy that logs all API calls
- Use Qdrant's telemetry endpoint for basic operation tracking
- Pair with customer's existing logging infrastructure (ELK, Splunk)

**Missing range-bound search:**
- Interim: use payload filtering with numeric range conditions
- Combine with vector search for hybrid approach
- Post-process results to enforce range constraints

**Missing alerting customization:**
- Interim: Grafana + Qdrant Prometheus metrics endpoint
- Custom alert rules for any metric threshold
- Dashboard templates available in qdrant monitoring repo

**Missing RBAC:**
- Interim: API key per application/team
- Network-level isolation (VPC peering, private endpoints)
- Application-level authorization in the client layer

### Step 4: Escalate with business impact

Email template for product team:
```
Subject: Feature request: [feature] - $[ARR] at risk

Customer: [name]
Deal size: $[amount]/year
Timeline: Need by [date]
Blocker: [feature] is required for [reason]
Workaround: [interim solution], but customer needs native support
Competitive pressure: [competitor] has this / doesn't have this
Other customers asking: [list if known]
```

### Step 5: Bridge with professional services
If the feature is 3+ months out:
- Offer consulting hours to implement the workaround
- Position it as "interim architecture" not "hack"
- Include the workaround cost in the deal as a credit toward
  future subscription when the feature ships

## Real examples from your deals

### PointClickCare: Audit logging
- Deal: $500k+
- Blocker: Security review failed without audit logging
- Timeline: April 10th production rollout
- Outcome: Customer built in-house workaround
- Lesson: Should have offered interim audit proxy immediately
  and escalated to product with ARR quantification

### Percheron Capital: Range-bound search
- Deal: POC stage
- Blocker: Needed for real-time recommendations with numeric constraints
- Workaround available: Payload filtering covers most of the use case
- Lesson: POC should have included payload filtering demo from day 1

### Payleven: Alerting customization
- Deal: Active customer with issues
- Blocker: Only single 80% threshold email, no customization
- Workaround: Grafana + Prometheus metrics
- Lesson: Should have set up monitoring during onboarding
