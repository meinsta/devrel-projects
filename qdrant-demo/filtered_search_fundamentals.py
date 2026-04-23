"""
How Filtered Search Actually Works in Qdrant
=============================================

Most vector databases treat filtering as an afterthought: search first,
filter later, hope you still have enough results. Qdrant does something
smarter. It has a query planner that looks at your filter BEFORE searching
and picks the fastest strategy.

This demo walks through the three strategies Qdrant uses and why they matter.

Run: uv run filtered_search_fundamentals.py
"""

import os
import time
import random

from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
    Range,
    PayloadSchemaType,
)

load_dotenv()
random.seed(42)

QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")

if not QDRANT_URL or not QDRANT_API_KEY:
    raise SystemExit("Set QDRANT_URL and QDRANT_API_KEY in .env")

client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)

# ---------------------------------------------------------------------------
# Setup: 50k "products" with 128-dim vectors
# ---------------------------------------------------------------------------
NUM_POINTS = 50_000
VECTOR_DIM = 128
COLLECTION = "filtered_search_demo"

CATEGORIES = ["electronics", "clothing", "books", "home", "sports"]
# Notice the distribution: "clothing" is ~40% of the data, "sports" is ~5%.
# This matters for how the query planner behaves.
CATEGORY_WEIGHTS = [0.20, 0.40, 0.15, 0.20, 0.05]

print("=" * 60)
print("HOW FILTERED SEARCH WORKS IN QDRANT")
print("=" * 60)


def setup_collection():
    """Create collection, upload points, build payload indexes."""
    # Delete if exists from a previous run
    collections = [c.name for c in client.get_collections().collections]
    if COLLECTION in collections:
        client.delete_collection(COLLECTION)
        print(f"  Deleted existing '{COLLECTION}'")

    client.create_collection(
        collection_name=COLLECTION,
        vectors_config=VectorParams(size=VECTOR_DIM, distance=Distance.COSINE),
    )
    print(f"  Created collection '{COLLECTION}'")

    # Upload in batches
    batch_size = 1000
    for batch_start in range(0, NUM_POINTS, batch_size):
        points = []
        for i in range(batch_start, min(batch_start + batch_size, NUM_POINTS)):
            cat = random.choices(CATEGORIES, weights=CATEGORY_WEIGHTS, k=1)[0]
            points.append(
                PointStruct(
                    id=i,
                    vector=[random.gauss(0, 1) for _ in range(VECTOR_DIM)],
                    payload={
                        "category": cat,
                        "price": round(random.uniform(5, 500), 2),
                        "rating": round(random.uniform(1, 5), 1),
                        "in_stock": random.random() > 0.1,
                    },
                )
            )
        client.upsert(collection_name=COLLECTION, points=points)
        done = min(batch_start + batch_size, NUM_POINTS)
        if done % 10_000 == 0 or done == NUM_POINTS:
            print(f"  Uploaded {done:,}/{NUM_POINTS:,} points")

    # Create payload indexes. This is critical for filtered search performance.
    for field, schema in [
        ("category", PayloadSchemaType.KEYWORD),
        ("price", PayloadSchemaType.FLOAT),
        ("rating", PayloadSchemaType.FLOAT),
        ("in_stock", PayloadSchemaType.BOOL),
    ]:
        client.create_payload_index(COLLECTION, field, schema)
    print("  Created payload indexes on: category, price, rating, in_stock")


print(f"\nSetting up {NUM_POINTS:,} points with {VECTOR_DIM}-dim vectors on Qdrant Cloud...")
setup_collection()
print("Done.\n")


def bench(label, query_filter=None, runs=50):
    """Run a search multiple times and return avg latency + results."""
    query_vector = [random.gauss(0, 1) for _ in range(VECTOR_DIM)]
    # Warmup
    for _ in range(5):
        client.query_points(
            collection_name=COLLECTION,
            query=query_vector,
            query_filter=query_filter,
            limit=10,
        )
    # Timed runs
    times = []
    results = None
    for _ in range(runs):
        t0 = time.perf_counter()
        results = client.query_points(
            collection_name=COLLECTION,
            query=query_vector,
            query_filter=query_filter,
            limit=10,
        )
        times.append(time.perf_counter() - t0)

    avg_ms = sum(times) / len(times) * 1000
    p50 = sorted(times)[len(times) // 2] * 1000
    p99 = sorted(times)[int(len(times) * 0.99)] * 1000
    print(f"  Avg: {avg_ms:.2f}ms  |  p50: {p50:.2f}ms  |  p99: {p99:.2f}ms")
    return results


# ---------------------------------------------------------------------------
# BASELINE: No filter
# ---------------------------------------------------------------------------
print("-" * 60)
print("BASELINE: Search without any filter")
print("-" * 60)
print("""
Without a filter, Qdrant traverses the HNSW graph directly.
This is the fastest path: O(log n) with the graph structure.
""")
results = bench("no filter")
print(f"  Top result: id={results.points[0].id}, score={results.points[0].score:.4f}")


# ---------------------------------------------------------------------------
# STRATEGY 1: Broad filter (high cardinality)
# ---------------------------------------------------------------------------
print()
print("-" * 60)
print('STRATEGY 1: Broad filter  ->  "clothing" (~40% of data)')
print("-" * 60)
print("""
When a filter matches MANY points, Qdrant uses HNSW + inline filtering.
It traverses the graph normally, but checks the filter at each node.
Most nodes pass, so the graph stays well-connected and search is fast.

Think of it like walking through a mall and skipping closed stores.
If 90% are open, you barely notice the closed ones.
""")

broad_filter = Filter(
    must=[FieldCondition(key="category", match=MatchValue(value="clothing"))]
)
results = bench("broad", broad_filter)
p = results.points[0]
print(f"  Top: id={p.id}, cat={p.payload['category']}, score={p.score:.4f}")


# ---------------------------------------------------------------------------
# STRATEGY 2: Narrow filter (low cardinality)
# ---------------------------------------------------------------------------
print()
print("-" * 60)
print('STRATEGY 2: Narrow filter  ->  "sports" (~5% of data)')
print("-" * 60)
print("""
When a filter matches FEW points, HNSW graph traversal breaks down.
Too many nodes get rejected, the graph loses connectivity. Like walking
through a mall where 95% of stores are closed: nothing but dead ends.

Qdrant flips the strategy: filter FIRST via the inverted index to get
matching IDs, then score only those vectors. A plain scan over a small
set beats a crippled graph traversal every time.
""")

narrow_filter = Filter(
    must=[FieldCondition(key="category", match=MatchValue(value="sports"))]
)
results = bench("narrow", narrow_filter)
p = results.points[0]
print(f"  Top: id={p.id}, cat={p.payload['category']}, score={p.score:.4f}")


# ---------------------------------------------------------------------------
# COMPOUND: AND conditions (must)
# ---------------------------------------------------------------------------
print()
print("-" * 60)
print("COMPOUND: AND conditions reordered by selectivity")
print("-" * 60)
print("""
Real queries stack multiple conditions. Qdrant optimizes the execution
order: in AND (must) clauses, the MOST SELECTIVE condition runs first.

If the first condition eliminates 95% of points, the second condition
only checks the remaining 5%. The payload index gives cardinality
estimates per condition, and Qdrant sorts them cheapest-first.
Same idea as a SQL query planner.
""")

compound_filter = Filter(
    must=[
        FieldCondition(key="category", match=MatchValue(value="sports")),
        FieldCondition(key="price", range=Range(lt=50.0)),
        FieldCondition(key="rating", range=Range(gte=4.0)),
    ]
)
count = client.count(collection_name=COLLECTION, count_filter=compound_filter)
print(f"  Filter: sports AND price < $50 AND rating >= 4.0")
print(f"  Matching: {count.count:,} / {NUM_POINTS:,} points")
results = bench("compound", compound_filter)
if results.points:
    p = results.points[0]
    print(f"  Top: id={p.id}, ${p.payload['price']}, "
          f"rating={p.payload['rating']}, score={p.score:.4f}")


# ---------------------------------------------------------------------------
# OR: should conditions
# ---------------------------------------------------------------------------
print()
print("-" * 60)
print("OR FILTERS: Optimized in the opposite direction")
print("-" * 60)
print("""
OR (should) clauses run the BROADEST condition first. For OR, a single
match is enough. If the first condition matches 40% of points, most
pass on the first check without evaluating the rest.
""")

or_filter = Filter(
    should=[
        FieldCondition(key="category", match=MatchValue(value="sports")),
        FieldCondition(key="category", match=MatchValue(value="books")),
    ]
)
count = client.count(collection_name=COLLECTION, count_filter=or_filter)
print(f"  Filter: sports OR books")
print(f"  Matching: {count.count:,} / {NUM_POINTS:,} points")
bench("or", or_filter)


# ---------------------------------------------------------------------------
# BORDERLINE: The uncertain case
# ---------------------------------------------------------------------------
print()
print("-" * 60)
print("THE BORDERLINE CASE: When Qdrant isn't sure")
print("-" * 60)
print("""
Sometimes the cardinality estimate is ambiguous: the filter might match
between 5% and 30%. The min/max bounds straddle the decision threshold.

Qdrant samples ~1,000 random points, applies the filter, and uses a
statistical confidence interval (Agresti-Coull) to sharpen the estimate.
Costs microseconds, prevents picking the wrong strategy (which could
cost milliseconds).

Three-level confidence system:
  Level 1: Index-based estimate          O(1)      always runs
  Level 2: Sample-based refinement       O(1000)   only when uncertain
  Level 3: Actual search                 O(n)      the query itself
""")

borderline_filter = Filter(
    must=[
        FieldCondition(key="price", range=Range(gte=100.0, lt=200.0)),
        FieldCondition(key="in_stock", match=MatchValue(value=True)),
    ]
)
count = client.count(collection_name=COLLECTION, count_filter=borderline_filter)
pct = count.count / NUM_POINTS * 100
print(f"  Filter: $100-200 AND in_stock")
print(f"  Matching: {count.count:,} ({pct:.1f}% of data)")
bench("borderline", borderline_filter)


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
print()
print("=" * 60)
print("SUMMARY")
print("=" * 60)
print("""
Qdrant's filtered search is not a single algorithm. It's a query planner
that picks from multiple strategies based on your filter's selectivity:

  Broad filter  (many matches)  ->  HNSW graph + inline filter checks
  Narrow filter (few matches)   ->  filter first, score only matches
  Borderline    (uncertain)     ->  sample to estimate, then decide

Key takeaways:
  - Payload indexes enable cardinality estimation (create them!)
  - AND conditions: most selective first
  - OR conditions: broadest first
  - No manual tuning needed: the planner adapts per-query

The same approach SQL databases use for query planning, applied to
vector search.
""")

# Cleanup option
print("Collection left on cloud for inspection. Delete with:")
print(f'  client.delete_collection("{COLLECTION}")')
