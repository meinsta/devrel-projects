#!/usr/bin/env python3
"""
Benchmark: Named Vectors Hybrid Search vs Single Embedding

This benchmark compares:
1. Single embedding (MiniLM - what Chroma uses)
2. Single embedding (Jina Code)
3. Hybrid search with RRF fusion (code + text vectors)

Using realistic claude-mem observation data.
"""

import asyncio
import json
import time
from dataclasses import dataclass
from typing import List, Dict, Tuple
import numpy as np

# Test dataset: Realistic claude-mem observations
# Each has: id, content, category (code/text/mixed), relevant_queries
TEST_DOCUMENTS = [
    # CODE-HEAVY observations
    {
        "id": "obs_1",
        "content": "Implemented parseJSON function using recursive descent parser. The function handles nested objects, arrays, strings, numbers, booleans, and null values. Key insight: using a token stream with peek/consume pattern simplifies the logic.",
        "category": "code",
        "relevant_for": ["json parsing", "recursive descent", "parseJSON implementation"]
    },
    {
        "id": "obs_2",
        "content": "Fixed bug in OAuth2 token refresh logic. The issue was that refreshToken() was being called before checking if the access token was actually expired. Added isTokenExpired() check using jwt.decode() to inspect the exp claim.",
        "category": "code",
        "relevant_for": ["oauth token refresh", "jwt expiration", "authentication bug"]
    },
    {
        "id": "obs_3",
        "content": "Added rate limiting middleware using token bucket algorithm. Configuration: 100 requests per minute per API key. Implemented with Redis for distributed state. Key functions: consumeToken(), refillBucket(), getRemainingTokens().",
        "category": "code",
        "relevant_for": ["rate limiting", "token bucket", "redis middleware"]
    },
    {
        "id": "obs_4",
        "content": "Refactored database connection pooling. Replaced pg.Pool with custom ConnectionManager class that implements health checks and automatic reconnection. Pool size: min=5, max=20. Idle timeout: 30s.",
        "category": "code",
        "relevant_for": ["database pooling", "connection manager", "postgres connections"]
    },
    {
        "id": "obs_5",
        "content": "Implemented WebSocket heartbeat mechanism. Server sends ping every 30s, client must respond with pong within 10s or connection is terminated. Added reconnection logic with exponential backoff: 1s, 2s, 4s, 8s, max 30s.",
        "category": "code",
        "relevant_for": ["websocket heartbeat", "ping pong", "reconnection backoff"]
    },
    {
        "id": "obs_6",
        "content": "Created custom ESLint rule to enforce async/await error handling. Rule checks that all async functions either have try/catch or return the promise to a caller that handles errors. Prevents silent promise rejections.",
        "category": "code",
        "relevant_for": ["eslint rule", "async error handling", "promise rejection"]
    },
    {
        "id": "obs_7",
        "content": "Optimized React component re-renders using useMemo and useCallback. The ProductList component was re-rendering on every state change. Memoized the filterProducts() function and the sorted product array. Reduced re-renders by 80%.",
        "category": "code",
        "relevant_for": ["react optimization", "useMemo useCallback", "component re-renders"]
    },
    {
        "id": "obs_8",
        "content": "Implemented binary search for finding insertion point in sorted array. Used for maintaining sorted order in real-time leaderboard. Complexity: O(log n) vs O(n) for linear search. Function: findInsertionIndex(arr, value, compareFn).",
        "category": "code",
        "relevant_for": ["binary search", "sorted array insertion", "leaderboard algorithm"]
    },

    # TEXT-HEAVY observations (discussions, decisions, notes)
    {
        "id": "obs_9",
        "content": "Team decided to migrate from REST to GraphQL for the mobile API. Main reasons: reduce over-fetching on slow mobile connections, enable clients to request exactly the data they need, better typing with code generation. Timeline: 3 sprints.",
        "category": "text",
        "relevant_for": ["graphql migration", "api architecture decision", "mobile optimization"]
    },
    {
        "id": "obs_10",
        "content": "Discussed authentication strategy for the new microservices. Options considered: JWT with short expiry, OAuth2 with refresh tokens, API keys for service-to-service. Decision: OAuth2 for user-facing, mTLS for internal services.",
        "category": "text",
        "relevant_for": ["authentication strategy", "microservices security", "oauth vs jwt discussion"]
    },
    {
        "id": "obs_11",
        "content": "User research findings from last week's interviews. Key pain points: slow search (mentioned by 8/10 users), confusing navigation (6/10), missing bulk actions (5/10). Priority recommendation: focus on search performance first.",
        "category": "text",
        "relevant_for": ["user research", "pain points", "search performance priority"]
    },
    {
        "id": "obs_12",
        "content": "Retrospective notes: What went well - deployment automation saved 2 hours per release. What to improve - code review turnaround time (currently 2 days average). Action item: implement review rotation schedule.",
        "category": "text",
        "relevant_for": ["retrospective", "deployment automation", "code review process"]
    },
    {
        "id": "obs_13",
        "content": "Meeting with stakeholders about Q2 roadmap. Agreed priorities: 1) Performance improvements (load time under 2s), 2) Mobile app launch, 3) Enterprise SSO support. Deferred: analytics dashboard, internationalization.",
        "category": "text",
        "relevant_for": ["q2 roadmap", "stakeholder priorities", "performance goals"]
    },
    {
        "id": "obs_14",
        "content": "Documentation review completed. Found 23 outdated API endpoints, 8 missing error code explanations, and 5 broken code examples. Created Jira tickets for each. Estimated effort: 3 developer days to fix all issues.",
        "category": "text",
        "relevant_for": ["documentation review", "api docs outdated", "technical debt"]
    },

    # MIXED observations (code + context)
    {
        "id": "obs_15",
        "content": "Investigated memory leak in production. Used Chrome DevTools heap snapshots to identify the issue. Root cause: event listeners not being removed in useEffect cleanup. Fixed by adding return () => element.removeEventListener() in 12 components.",
        "category": "mixed",
        "relevant_for": ["memory leak", "useEffect cleanup", "event listener removal"]
    },
    {
        "id": "obs_16",
        "content": "Performance audit results: Largest Contentful Paint was 4.2s, target is 2.5s. Main issues: unoptimized images (saved 800KB by converting to WebP), render-blocking CSS (moved to async loading), large JavaScript bundle (implemented code splitting).",
        "category": "mixed",
        "relevant_for": ["performance audit", "lcp optimization", "code splitting"]
    },
    {
        "id": "obs_17",
        "content": "Debugged intermittent test failures in CI. Problem: tests were sharing database state. Solution: wrapped each test in a transaction that rolls back. Added beforeEach(() => db.beginTransaction()) and afterEach(() => db.rollback()) to test setup.",
        "category": "mixed",
        "relevant_for": ["flaky tests", "database isolation", "test transactions"]
    },
    {
        "id": "obs_18",
        "content": "Implemented feature flags system. Used LaunchDarkly SDK for gradual rollouts. Key patterns: useFeatureFlag() hook for React, featureEnabled() middleware for API routes. Rollout strategy: 10% -> 25% -> 50% -> 100% over 2 weeks.",
        "category": "mixed",
        "relevant_for": ["feature flags", "gradual rollout", "launchdarkly"]
    },
    {
        "id": "obs_19",
        "content": "Set up monitoring and alerting with Datadog. Key metrics: p95 latency, error rate, throughput. Alert thresholds: p95 > 500ms triggers warning, > 1s triggers page. Created dashboard showing request flow through all microservices.",
        "category": "mixed",
        "relevant_for": ["monitoring setup", "datadog alerts", "latency thresholds"]
    },
    {
        "id": "obs_20",
        "content": "Migrated from Webpack to Vite for development builds. Build time improved from 45s to 3s. Hot reload now under 100ms. Required changes: updated import.meta.env usage, added vite.config.ts, modified proxy configuration for API calls.",
        "category": "mixed",
        "relevant_for": ["vite migration", "build performance", "webpack replacement"]
    },
]

# Test queries with expected relevant document IDs
# Using more realistic/harder queries that don't directly match document wording
TEST_QUERIES = [
    # Code-specific queries - using different terminology than the documents
    {"query": "how to parse JSON recursively", "expected": ["obs_1"], "type": "code"},
    {"query": "token stream peek consume pattern", "expected": ["obs_1"], "type": "code"},
    {"query": "refreshToken function fix", "expected": ["obs_2"], "type": "code"},
    {"query": "jwt.decode exp claim checking", "expected": ["obs_2"], "type": "code"},
    {"query": "API throttling bucket algorithm", "expected": ["obs_3"], "type": "code"},
    {"query": "consumeToken refillBucket functions", "expected": ["obs_3"], "type": "code"},
    {"query": "pg.Pool replacement custom class", "expected": ["obs_4"], "type": "code"},
    {"query": "ConnectionManager health checks", "expected": ["obs_4"], "type": "code"},
    {"query": "exponential backoff reconnection", "expected": ["obs_5"], "type": "code"},
    {"query": "server ping client pong timeout", "expected": ["obs_5"], "type": "code"},
    {"query": "custom lint rule promise rejection", "expected": ["obs_6"], "type": "code"},
    {"query": "try catch async function enforcement", "expected": ["obs_6"], "type": "code"},
    {"query": "filterProducts memoization", "expected": ["obs_7"], "type": "code"},
    {"query": "ProductList component rerenders", "expected": ["obs_7"], "type": "code"},
    {"query": "findInsertionIndex compareFn", "expected": ["obs_8"], "type": "code"},
    {"query": "O(log n) sorted array lookup", "expected": ["obs_8"], "type": "code"},

    # Text/discussion queries - natural language without code terms
    {"query": "why we chose graphql over rest", "expected": ["obs_9"], "type": "text"},
    {"query": "mobile API data fetching strategy", "expected": ["obs_9"], "type": "text"},
    {"query": "service to service authentication method", "expected": ["obs_10"], "type": "text"},
    {"query": "mTLS vs oauth decision", "expected": ["obs_10"], "type": "text"},
    {"query": "user interview feedback summary", "expected": ["obs_11"], "type": "text"},
    {"query": "what are the main pain points", "expected": ["obs_11"], "type": "text"},
    {"query": "sprint retro improvements needed", "expected": ["obs_12"], "type": "text"},
    {"query": "review turnaround time issue", "expected": ["obs_12"], "type": "text"},
    {"query": "stakeholder meeting priorities", "expected": ["obs_13"], "type": "text"},
    {"query": "what we deferred to later", "expected": ["obs_13"], "type": "text"},
    {"query": "outdated endpoints found", "expected": ["obs_14"], "type": "text"},
    {"query": "broken code examples in docs", "expected": ["obs_14"], "type": "text"},

    # Mixed queries - could be interpreted as code or discussion
    {"query": "heap snapshot memory issue", "expected": ["obs_15"], "type": "mixed"},
    {"query": "useEffect cleanup missing", "expected": ["obs_15"], "type": "mixed"},
    {"query": "LCP score improvement", "expected": ["obs_16"], "type": "mixed"},
    {"query": "webp image optimization results", "expected": ["obs_16"], "type": "mixed"},
    {"query": "CI test isolation problem", "expected": ["obs_17"], "type": "mixed"},
    {"query": "transaction rollback test setup", "expected": ["obs_17"], "type": "mixed"},
    {"query": "LaunchDarkly gradual rollout", "expected": ["obs_18"], "type": "mixed"},
    {"query": "useFeatureFlag hook implementation", "expected": ["obs_18"], "type": "mixed"},
    {"query": "p95 latency threshold alerts", "expected": ["obs_19"], "type": "mixed"},
    {"query": "Datadog dashboard microservices", "expected": ["obs_19"], "type": "mixed"},
    {"query": "vite.config.ts migration changes", "expected": ["obs_20"], "type": "mixed"},
    {"query": "hot reload build time improvement", "expected": ["obs_20"], "type": "mixed"},
]


@dataclass
class BenchmarkResult:
    model_name: str
    precision_at_1: float
    precision_at_3: float
    precision_at_5: float
    mrr: float  # Mean Reciprocal Rank
    by_query_type: Dict[str, Dict[str, float]]


async def run_benchmark():
    """Run the full benchmark comparing embedding approaches."""

    print("=" * 60)
    print("Named Vectors Hybrid Search Benchmark")
    print("=" * 60)
    print()

    # Import fastembed
    try:
        from fastembed import TextEmbedding
    except ImportError:
        print("ERROR: fastembed not installed. Run: pip install fastembed")
        return

    # Initialize embedding models
    print("Loading embedding models...")
    start = time.time()

    model_minilm = TextEmbedding("sentence-transformers/all-MiniLM-L6-v2")
    print(f"  - MiniLM loaded ({time.time() - start:.1f}s)")

    start = time.time()
    model_jina = TextEmbedding("jinaai/jina-embeddings-v2-base-code")
    print(f"  - Jina Code loaded ({time.time() - start:.1f}s)")
    print()

    # Embed all documents
    print("Embedding documents...")
    doc_contents = [d["content"] for d in TEST_DOCUMENTS]
    doc_ids = [d["id"] for d in TEST_DOCUMENTS]

    embeddings_minilm = list(model_minilm.embed(doc_contents))
    embeddings_jina = list(model_jina.embed(doc_contents))

    embeddings_minilm = np.array(embeddings_minilm)
    embeddings_jina = np.array(embeddings_jina)

    print(f"  - MiniLM: {embeddings_minilm.shape}")
    print(f"  - Jina: {embeddings_jina.shape}")
    print()

    # Run searches and measure precision
    results = {}

    for model_name, model, doc_embeddings in [
        ("MiniLM (Chroma default)", model_minilm, embeddings_minilm),
        ("Jina Code", model_jina, embeddings_jina),
    ]:
        print(f"Testing {model_name}...")
        results[model_name] = evaluate_model(model, doc_embeddings, doc_ids)

    # Test hybrid with RRF
    print("Testing Hybrid (RRF fusion)...")
    results["Hybrid RRF"] = evaluate_hybrid_rrf(
        model_minilm, embeddings_minilm,
        model_jina, embeddings_jina,
        doc_ids
    )

    print()
    print("=" * 60)
    print("RESULTS")
    print("=" * 60)
    print()

    # Print results table
    print(f"{'Model':<25} {'P@1':>8} {'P@3':>8} {'P@5':>8} {'MRR':>8}")
    print("-" * 57)

    for model_name, result in results.items():
        print(f"{model_name:<25} {result.precision_at_1:>7.1%} {result.precision_at_3:>7.1%} {result.precision_at_5:>7.1%} {result.mrr:>7.3f}")

    print()
    print("By Query Type:")
    print()

    for query_type in ["code", "text", "mixed"]:
        print(f"  {query_type.upper()} queries:")
        print(f"  {'Model':<25} {'P@1':>8} {'P@3':>8} {'P@5':>8}")
        print(f"  {'-' * 49}")
        for model_name, result in results.items():
            type_results = result.by_query_type.get(query_type, {})
            p1 = type_results.get("p@1", 0)
            p3 = type_results.get("p@3", 0)
            p5 = type_results.get("p@5", 0)
            print(f"  {model_name:<25} {p1:>7.1%} {p3:>7.1%} {p5:>7.1%}")
        print()

    # Save results as JSON
    output = {
        "overall": {
            name: {
                "precision_at_1": r.precision_at_1,
                "precision_at_3": r.precision_at_3,
                "precision_at_5": r.precision_at_5,
                "mrr": r.mrr,
            }
            for name, r in results.items()
        },
        "by_type": {
            name: r.by_query_type
            for name, r in results.items()
        }
    }

    with open("benchmark_results.json", "w") as f:
        json.dump(output, f, indent=2)

    print("Results saved to benchmark_results.json")


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Compute cosine similarity between two vectors."""
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))


def search(query_embedding: np.ndarray, doc_embeddings: np.ndarray, doc_ids: List[str], k: int = 5) -> List[Tuple[str, float]]:
    """Search for most similar documents."""
    similarities = [cosine_similarity(query_embedding, doc_emb) for doc_emb in doc_embeddings]
    ranked = sorted(zip(doc_ids, similarities), key=lambda x: x[1], reverse=True)
    return ranked[:k]


def rrf_fusion(results_list: List[List[Tuple[str, float]]], k: int = 60) -> List[Tuple[str, float]]:
    """Reciprocal Rank Fusion to combine multiple result lists."""
    scores = {}

    for results in results_list:
        for rank, (doc_id, _) in enumerate(results):
            if doc_id not in scores:
                scores[doc_id] = 0
            scores[doc_id] += 1 / (k + rank + 1)

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return ranked


def evaluate_model(model, doc_embeddings: np.ndarray, doc_ids: List[str]) -> BenchmarkResult:
    """Evaluate a single embedding model."""

    p1_scores = []
    p3_scores = []
    p5_scores = []
    rr_scores = []  # Reciprocal ranks

    by_type = {"code": {"p@1": [], "p@3": [], "p@5": []},
               "text": {"p@1": [], "p@3": [], "p@5": []},
               "mixed": {"p@1": [], "p@3": [], "p@5": []}}

    for query_data in TEST_QUERIES:
        query = query_data["query"]
        expected = set(query_data["expected"])
        query_type = query_data["type"]

        # Embed query
        query_emb = list(model.embed([query]))[0]

        # Search
        results = search(query_emb, doc_embeddings, doc_ids, k=5)
        result_ids = [r[0] for r in results]

        # Calculate precision at k
        p1 = len(set(result_ids[:1]) & expected) / min(1, len(expected))
        p3 = len(set(result_ids[:3]) & expected) / min(3, len(expected))
        p5 = len(set(result_ids[:5]) & expected) / min(5, len(expected))

        p1_scores.append(p1)
        p3_scores.append(p3)
        p5_scores.append(p5)

        by_type[query_type]["p@1"].append(p1)
        by_type[query_type]["p@3"].append(p3)
        by_type[query_type]["p@5"].append(p5)

        # Calculate reciprocal rank
        rr = 0
        for i, doc_id in enumerate(result_ids):
            if doc_id in expected:
                rr = 1 / (i + 1)
                break
        rr_scores.append(rr)

    # Average by type
    by_type_avg = {}
    for t in by_type:
        by_type_avg[t] = {
            "p@1": np.mean(by_type[t]["p@1"]) if by_type[t]["p@1"] else 0,
            "p@3": np.mean(by_type[t]["p@3"]) if by_type[t]["p@3"] else 0,
            "p@5": np.mean(by_type[t]["p@5"]) if by_type[t]["p@5"] else 0,
        }

    return BenchmarkResult(
        model_name="",
        precision_at_1=np.mean(p1_scores),
        precision_at_3=np.mean(p3_scores),
        precision_at_5=np.mean(p5_scores),
        mrr=np.mean(rr_scores),
        by_query_type=by_type_avg,
    )


def evaluate_hybrid_rrf(model_text, embeddings_text: np.ndarray,
                        model_code, embeddings_code: np.ndarray,
                        doc_ids: List[str]) -> BenchmarkResult:
    """Evaluate hybrid search with RRF fusion."""

    p1_scores = []
    p3_scores = []
    p5_scores = []
    rr_scores = []

    by_type = {"code": {"p@1": [], "p@3": [], "p@5": []},
               "text": {"p@1": [], "p@3": [], "p@5": []},
               "mixed": {"p@1": [], "p@3": [], "p@5": []}}

    for query_data in TEST_QUERIES:
        query = query_data["query"]
        expected = set(query_data["expected"])
        query_type = query_data["type"]

        # Embed query with both models
        query_emb_text = list(model_text.embed([query]))[0]
        query_emb_code = list(model_code.embed([query]))[0]

        # Search with both
        results_text = search(query_emb_text, embeddings_text, doc_ids, k=10)
        results_code = search(query_emb_code, embeddings_code, doc_ids, k=10)

        # RRF fusion
        fused = rrf_fusion([results_text, results_code])
        result_ids = [r[0] for r in fused[:5]]

        # Calculate precision at k
        p1 = len(set(result_ids[:1]) & expected) / min(1, len(expected))
        p3 = len(set(result_ids[:3]) & expected) / min(3, len(expected))
        p5 = len(set(result_ids[:5]) & expected) / min(5, len(expected))

        p1_scores.append(p1)
        p3_scores.append(p3)
        p5_scores.append(p5)

        by_type[query_type]["p@1"].append(p1)
        by_type[query_type]["p@3"].append(p3)
        by_type[query_type]["p@5"].append(p5)

        # Calculate reciprocal rank
        rr = 0
        for i, doc_id in enumerate(result_ids):
            if doc_id in expected:
                rr = 1 / (i + 1)
                break
        rr_scores.append(rr)

    # Average by type
    by_type_avg = {}
    for t in by_type:
        by_type_avg[t] = {
            "p@1": np.mean(by_type[t]["p@1"]) if by_type[t]["p@1"] else 0,
            "p@3": np.mean(by_type[t]["p@3"]) if by_type[t]["p@3"] else 0,
            "p@5": np.mean(by_type[t]["p@5"]) if by_type[t]["p@5"] else 0,
        }

    return BenchmarkResult(
        model_name="Hybrid RRF",
        precision_at_1=np.mean(p1_scores),
        precision_at_3=np.mean(p3_scores),
        precision_at_5=np.mean(p5_scores),
        mrr=np.mean(rr_scores),
        by_query_type=by_type_avg,
    )


if __name__ == "__main__":
    asyncio.run(run_benchmark())
