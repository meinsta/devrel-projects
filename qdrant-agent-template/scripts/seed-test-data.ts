import "dotenv/config";
import { ingestDocuments } from "../lib/ingestion/pipeline";

const testDocuments = [
  {
    content: `# Agentic Vector Search Architecture

## Overview

An agentic vector search system combines traditional retrieval with AI-driven decision making to improve search quality. The key components are:

1. **Multi-Query Planning**: Instead of using the user's query directly, the system generates multiple related queries to increase recall.

2. **Hybrid Retrieval**: Combines dense (semantic) and sparse (keyword/BM25) search for better coverage.

3. **Fusion**: Results from multiple queries are combined using algorithms like Reciprocal Rank Fusion (RRF).

4. **Reranking**: A stronger model reorders results for better precision.

5. **Evidence Critique**: The system evaluates whether retrieved evidence is sufficient to answer the question.

6. **Corrective Loop**: If evidence is insufficient, the system can rewrite queries, switch retrieval modes, or expand scope.

## Benefits

- Higher recall through multi-query planning
- Better precision through reranking
- Self-correcting behavior through critique and correction
- Auditable through comprehensive tracing
`,
    metadata: {
      source: "docs",
      title: "Agentic Vector Search Architecture",
      tags: ["architecture", "overview"],
    },
  },
  {
    content: `# Corrective Retrieval Loop

The corrective retrieval loop is the "agentic" part of the system. It allows the search to adapt when initial results are insufficient.

## How It Works

1. After reranking, the **Evidence Critic** evaluates the quality of retrieved chunks using several metrics:
   - **Coverage**: Do the chunks cover all aspects of the query?
   - **Consistency**: Are there contradictions between chunks?
   - **Specificity**: Are chunks actually about the query topic?

2. These scores are combined into an **Overall Confidence** score.

3. If confidence is below threshold (e.g., 0.72), the system enters a **Corrective Phase**:
   - **Query Rewrite**: Generate new sub-queries targeting missing aspects
   - **Mode Switch**: Change from dense to hybrid or sparse search
   - **Broaden Scope**: Remove restrictive filters
   - **Increase Depth**: Retrieve more candidates

4. The system retries retrieval with the new strategy.

5. After a maximum number of loops (typically 3), it proceeds to answer generation regardless.

## Configuration

- \`maxLoops\`: Maximum correction attempts (default: 3)
- \`CONFIDENCE_THRESHOLDS.PASS\`: Score to skip correction (default: 0.72)
- \`CONFIDENCE_THRESHOLDS.RETRY\`: Minimum score to attempt correction (default: 0.55)
`,
    metadata: {
      source: "docs",
      title: "Corrective Retrieval Loop",
      tags: ["corrective", "loop", "critique"],
    },
  },
  {
    content: `# Multi-Query Planning

Multi-query planning decomposes a user's question into multiple search queries to improve recall.

## Why Multiple Queries?

A single user query often contains multiple concepts or intents. By generating specialized sub-queries, we can:
- Target different aspects of the question
- Use different keyword phrasings
- Search for related concepts the user didn't explicitly mention

## Implementation

The planner uses an LLM to generate 3-6 sub-queries, each with:
- **text**: The search query
- **intent**: What aspect this targets
- **weight**: Importance (0-1, sum to 1)
- **filters**: Optional per-query filters

Example for "How does authentication work in the API?":
1. "API authentication methods OAuth JWT" (intent: auth_methods, weight: 0.3)
2. "API authentication flow request headers" (intent: auth_flow, weight: 0.25)
3. "API security token validation" (intent: security, weight: 0.2)
4. "API login endpoint authentication" (intent: endpoints, weight: 0.25)

## Fusion

Results from each sub-query are combined using **Reciprocal Rank Fusion (RRF)**:

\`\`\`
RRF_score(doc) = Σ weight_i / (k + rank_i(doc))
\`\`\`

Where k is a constant (typically 60) that prevents high-ranked documents from dominating.
`,
    metadata: {
      source: "docs",
      title: "Multi-Query Planning",
      tags: ["planning", "multi-query", "fusion"],
    },
  },
  {
    content: `# Hybrid Search with Qdrant

Hybrid search combines dense (semantic) and sparse (keyword) retrieval for better results.

## Dense Search

Uses neural embeddings to find semantically similar content:
- Good for: conceptual questions, paraphrasing, synonyms
- Model: sentence-transformers/all-MiniLM-L6-v2 (via QCI)

## Sparse Search (BM25)

Uses keyword matching with TF-IDF weighting:
- Good for: specific terms, error codes, exact phrases
- Model: qdrant/bm25 (via QCI)

## Qdrant Configuration

\`\`\`typescript
// Collection with named vectors
await client.createCollection("corpus_chunks", {
  vectors: {
    dense: { size: 384, distance: "Cosine" }
  },
  sparse_vectors: {
    sparse: { modifier: "idf" }
  }
});

// Hybrid query with RRF fusion
const results = await client.query("corpus_chunks", {
  prefetch: [
    { query: denseQuery, using: "dense", limit: 50 },
    { query: sparseQuery, using: "sparse", limit: 50 }
  ],
  query: { fusion: "rrf" },
  limit: 20
});
\`\`\`

## When to Use Each Mode

- **Dense only**: Natural language questions, "explain X", conceptual queries
- **Sparse only**: Error codes, function names, exact matches
- **Hybrid**: Default for most queries, especially technical or ambiguous ones
`,
    metadata: {
      source: "docs",
      title: "Hybrid Search with Qdrant",
      tags: ["hybrid", "qdrant", "dense", "sparse"],
    },
  },
  {
    content: `# Reranking

Reranking improves precision by using a stronger model to reorder initial retrieval results.

## Two-Tier Approach

1. **Initial Retrieval**: Fast but lower precision (dense/sparse/hybrid)
   - Retrieves top 50-100 candidates

2. **Reranking**: Slow but higher precision (cross-encoder)
   - Reorders top 30 candidates
   - Final output: top 10-15 chunks

## Reranker Options

### Jina Reranker
- Model: jina-reranker-v2-base-multilingual
- Supports 100+ languages
- 131K context length
- API: api.jina.ai/v1/rerank

### Cohere Rerank
- Model: rerank-v3.5
- Enterprise-focused
- API: api.cohere.com/v2/rerank

## Implementation

\`\`\`typescript
const reranked = await reranker.rerank({
  query: "How does authentication work?",
  documents: chunks.map(c => c.text),
  topN: 15
});

// Result includes index and relevance score
// [{ index: 3, score: 0.92 }, { index: 0, score: 0.87 }, ...]
\`\`\`

## Impact on Quality

Reranking typically improves nDCG@10 by 10-20% compared to first-stage retrieval alone. The tradeoff is latency (100-500ms additional).
`,
    metadata: {
      source: "docs",
      title: "Reranking",
      tags: ["reranking", "precision", "cross-encoder"],
    },
  },
];

async function main() {
  console.log("Seeding test documents...");

  const results = await ingestDocuments(testDocuments);

  const successful = results.filter((r) => r.status === "success");
  const failed = results.filter((r) => r.status === "error");

  console.log(`Ingested ${successful.length} documents`);
  if (failed.length > 0) {
    console.log(`Failed: ${failed.length}`);
    failed.forEach((f) => console.log(`  - ${f.docId}: ${f.error}`));
  }

  const totalChunks = successful.reduce((sum, r) => sum + r.chunkCount, 0);
  const totalTokens = successful.reduce((sum, r) => sum + r.totalTokens, 0);

  console.log(`Total chunks: ${totalChunks}`);
  console.log(`Total tokens: ${totalTokens}`);
  console.log("Done!");
}

main().catch((error) => {
  console.error("Seeding failed:", error);
  process.exit(1);
});
