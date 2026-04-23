---
name: qdrant-devrel-community-qa-triage
description: "Triage and respond to community questions about Qdrant. Use when someone asks a question on Discord, GitHub, Reddit, Stack Overflow, or any community channel. Classifies question type, routes to the right resource, and provides response templates."
---

# Community Q&A Triage

Quickly classify the question, find the right resource, and respond with the right tone. Do not write long custom answers from scratch. Route to docs, GitHub issues, or existing threads whenever possible.

## Question Classification

First, identify what type of question this is:

| Type | Signals | Route to |
|------|---------|----------|
| Setup / Getting Started | "how do I install", "getting started", "first collection", "connection error" | Docs quickstart |
| SDK / Client Usage | "python client", "typescript", "how to upsert", "query_points" | Docs + snippet lookup |
| Performance | "slow search", "high memory", "indexing stuck", "latency" | Performance skills |
| Deployment / Ops | "docker", "kubernetes", "cloud", "cluster", "scaling" | Deployment + scaling skills |
| Conceptual / Architecture | "when to use", "difference between", "should I", "best practice" | Docs concepts + SA judgment |
| Bug Report | "unexpected behavior", "error", "exception", stack trace | GitHub issues |
| Feature Request | "would be nice if", "is there a way to", "does Qdrant support" | GitHub discussions |
| Duplicate / Already Answered | same question appeared before | Link to existing thread |


## Response Principles

- **Route, don't repeat.** Link to docs rather than re-explaining what docs already say well.
- **Be direct.** Developers don't want filler. Get to the answer fast.
- **Match the channel tone.** Discord = casual. GitHub = precise. Stack Overflow = formal.
- **One follow-up offer.** End with "let me know if that doesn't solve it" not a list of questions.


## Response Templates

### Setup / Getting Started
```
Here's the quickstart: https://qdrant.tech/documentation/quickstart/

If you're hitting a connection issue specifically, check [X].
```

### SDK Usage
```
Here's how to do [X] with the Python client:

[snippet from snippets.qdrant.tech or docs]

Full reference: [doc link]
```

### Performance Issue
```
Depends on whether this is a latency or throughput issue — they need different fixes.

Quick triage:
- Latency → reduce hnsw_ef, check segment count
- Throughput → fewer segments, add replicas, batch queries
- Memory → check resident vs page cache (page cache filling RAM is normal)

More detail: https://qdrant.tech/documentation/guides/optimize/
```

### Bug Report
```
Thanks for the report. Can you share:
- Qdrant version
- Client version
- Minimal reproduction

File it here: https://github.com/qdrant/qdrant/issues
```

### Feature Request
```
Good idea. Best place to track this is GitHub Discussions so the team can see it and others can upvote:
https://github.com/qdrant/qdrant/discussions
```

### Already Answered
```
This came up before — [link to thread]. Let me know if that doesn't cover your case.
```


## Escalation

Escalate to the eng team or SA when:
- Security vulnerability reported
- Data loss or corruption reported
- Qdrant Cloud outage or billing issue
- Enterprise customer with a P0 blocker
- Bug that cannot be reproduced but affects multiple users


## Common Questions + Quick Answers

| Question | Answer |
|----------|--------|
| "What's the difference between scalar and binary quantization?" | Scalar = 4x memory reduction, small quality loss. Binary = 32x, needs rescore=true. [Quantization docs](https://qdrant.tech/documentation/guides/quantization/) |
| "How do I do hybrid search?" | Dense + sparse vectors with prefetch + RRF fusion. [Hybrid queries](https://qdrant.tech/documentation/concepts/hybrid-queries/) |
| "Why is memory so high?" | Page cache filling RAM is normal OS behavior. Check resident memory (RSSAnon) instead. |
| "Can I update vectors in place?" | Yes, upsert with the same ID overwrites. |
| "How many shards should I use?" | Multiple of your node count. Default is fine for single node. |
| "Does Qdrant support full-text search?" | Sparse vectors + keyword payload index. Not a full-text search engine. |
| "What's the difference between filter and must?" | `must` is AND, `should` is OR, `must_not` is NOT. [Filtering docs](https://qdrant.tech/documentation/concepts/filtering/) |
