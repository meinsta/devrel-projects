"""Evaluate search quality against a golden test set.

Usage:
    uv run python eval/run_eval.py                    # run eval, print report
    uv run python eval/run_eval.py --save baseline    # save results as named snapshot
    uv run python eval/run_eval.py --compare baseline # compare current results to snapshot
"""

import argparse
import json
import sys
import time
from pathlib import Path

from fastembed import TextEmbedding
from qdrant_edge import EdgeShard, Query, QueryRequest

EVAL_DIR = Path(__file__).parent
QUERIES_PATH = EVAL_DIR / "queries.jsonl"
RESULTS_DIR = EVAL_DIR / "results"

# Match the main config
SHARD_DIR = Path.home() / ".qdrant-guide" / "shard"
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
TOP_K = 5


def load_queries() -> list[dict]:
    queries = []
    with open(QUERIES_PATH) as f:
        for line in f:
            line = line.strip()
            if line:
                queries.append(json.loads(line))
    return queries


def run_eval(shard: EdgeShard, model: TextEmbedding, queries: list[dict]) -> list[dict]:
    results = []

    for q in queries:
        query_text = q["query"]
        expected_sources = q["expected_sources"]

        query_vector = list(model.embed([query_text]))[0].tolist()

        t0 = time.perf_counter()
        points = shard.query(QueryRequest(
            query=Query.Nearest(query_vector, using="dense"),
            limit=TOP_K,
            with_payload=True,
        ))
        latency_ms = (time.perf_counter() - t0) * 1000

        hits = []
        for p in points:
            payload = p.payload or {}
            hits.append({
                "source": payload.get("source", ""),
                "title": payload.get("title", ""),
                "score": round(p.score, 4) if p.score else 0,
                "snippet": payload.get("content", "")[:200],
            })

        # source match: does any result URL contain any expected source substring
        source_hits = 0
        for hit in hits:
            for exp in expected_sources:
                if exp in hit["source"]:
                    source_hits += 1
                    break

        # reciprocal rank: 1/position of first matching source (0 if no match)
        rr = 0.0
        for i, hit in enumerate(hits):
            for exp in expected_sources:
                if exp in hit["source"]:
                    rr = 1.0 / (i + 1)
                    break
            if rr > 0:
                break

        results.append({
            "query": query_text,
            "expected_sources": expected_sources,
            "source_hits_in_top5": source_hits,
            "reciprocal_rank": round(rr, 4),
            "top1_score": hits[0]["score"] if hits else 0,
            "latency_ms": round(latency_ms, 2),
            "hits": hits,
        })

    return results


def compute_metrics(results: list[dict]) -> dict:
    n = len(results)
    if n == 0:
        return {}

    # hit rate @5: fraction of queries where at least one expected source is in top 5
    hit_rate = sum(1 for r in results if r["source_hits_in_top5"] > 0) / n

    # average source hits in top 5
    avg_source_hits = sum(r["source_hits_in_top5"] for r in results) / n

    # MRR: mean reciprocal rank
    mrr = sum(r["reciprocal_rank"] for r in results) / n

    # average top-1 similarity score
    avg_top1_score = sum(r["top1_score"] for r in results) / n

    # average latency
    avg_latency = sum(r["latency_ms"] for r in results) / n

    # queries that missed entirely
    misses = [r["query"] for r in results if r["source_hits_in_top5"] == 0]

    return {
        "total_queries": n,
        "hit_rate_at_5": round(hit_rate, 3),
        "avg_source_hits_at_5": round(avg_source_hits, 2),
        "mrr": round(mrr, 4),
        "avg_top1_score": round(avg_top1_score, 4),
        "avg_latency_ms": round(avg_latency, 2),
        "misses": misses,
    }


def print_report(metrics: dict, results: list[dict]):
    print("\n=== search eval report ===\n")
    print(f"queries:              {metrics['total_queries']}")
    print(f"hit rate @5:          {metrics['hit_rate_at_5']:.1%}")
    print(f"avg source hits @5:   {metrics['avg_source_hits_at_5']}")
    print(f"MRR:                  {metrics['mrr']:.4f}")
    print(f"avg top-1 score:      {metrics['avg_top1_score']:.4f}")
    print(f"avg latency:          {metrics['avg_latency_ms']:.1f} ms")

    if metrics["misses"]:
        print(f"\nmisses ({len(metrics['misses'])}):")
        for m in metrics["misses"]:
            print(f"  - {m}")

    print()

    # per-query detail
    for r in results:
        status = "hit" if r["source_hits_in_top5"] > 0 else "MISS"
        rr = r["reciprocal_rank"]
        print(f"  [{status}] {r['query']}")
        print(f"         source_hits={r['source_hits_in_top5']}  RR={rr:.2f}  score={r['top1_score']:.4f}  {r['latency_ms']:.1f}ms")
        if r["hits"]:
            print(f"         top1: {r['hits'][0]['source']}")
        print()


def save_snapshot(name: str, metrics: dict, results: list[dict]):
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    path = RESULTS_DIR / f"{name}.json"
    data = {"name": name, "metrics": metrics, "results": results}
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    print(f"saved snapshot to {path}")


def compare_snapshots(name: str, current_metrics: dict, current_results: list[dict]):
    path = RESULTS_DIR / f"{name}.json"
    if not path.exists():
        print(f"error: snapshot '{name}' not found at {path}")
        sys.exit(1)

    with open(path) as f:
        baseline = json.load(f)

    bm = baseline["metrics"]
    cm = current_metrics

    print(f"\n=== comparison vs '{name}' ===\n")
    print(f"{'metric':<25} {'baseline':>10} {'current':>10} {'delta':>10}")
    print("-" * 58)

    for key in ["hit_rate_at_5", "avg_source_hits_at_5", "mrr", "avg_top1_score", "avg_latency_ms"]:
        if key not in bm or key not in cm:
            continue
        bv = bm[key]
        cv = cm[key]
        delta = cv - bv
        sign = "+" if delta > 0 else ""
        # for latency, lower is better
        if key == "avg_latency_ms":
            indicator = " (worse)" if delta > 0 else " (better)" if delta < 0 else ""
        else:
            indicator = " (better)" if delta > 0 else " (worse)" if delta < 0 else ""
        print(f"  {key:<23} {bv:>10} {cv:>10} {sign}{delta:>+9.4f}{indicator}")

    # show regressions: queries that were hits before but misses now
    baseline_results = {r["query"]: r for r in baseline["results"]}
    regressions = []
    improvements = []
    for r in current_results:
        br = baseline_results.get(r["query"])
        if br is None:
            continue
        was_hit = br["source_hits_in_top5"] > 0
        is_hit = r["source_hits_in_top5"] > 0
        if was_hit and not is_hit:
            regressions.append(r["query"])
        elif not was_hit and is_hit:
            improvements.append(r["query"])

    if regressions:
        print(f"\nregressions ({len(regressions)}):")
        for q in regressions:
            print(f"  - {q}")

    if improvements:
        print(f"\nimprovements ({len(improvements)}):")
        for q in improvements:
            print(f"  - {q}")

    if not regressions and not improvements:
        print("\nno changes in hit/miss status")

    print()


def main():
    parser = argparse.ArgumentParser(description="evaluate qdrant-guide search quality")
    parser.add_argument("--save", metavar="NAME", help="save results as a named snapshot")
    parser.add_argument("--compare", metavar="NAME", help="compare current results to a saved snapshot")
    parser.add_argument("--shard-dir", type=Path, default=SHARD_DIR, help="path to shard directory")
    args = parser.parse_args()

    if not args.shard_dir.exists():
        print(f"error: shard not found at {args.shard_dir}")
        sys.exit(1)

    print(f"loading shard from {args.shard_dir}...")
    shard = EdgeShard(str(args.shard_dir))

    print(f"loading embedding model ({EMBEDDING_MODEL})...")
    model = TextEmbedding(EMBEDDING_MODEL)

    queries = load_queries()
    print(f"running {len(queries)} queries...")

    results = run_eval(shard, model, queries)
    metrics = compute_metrics(results)

    print_report(metrics, results)

    if args.save:
        save_snapshot(args.save, metrics, results)

    if args.compare:
        compare_snapshots(args.compare, metrics, results)

    shard.close()


if __name__ == "__main__":
    main()
