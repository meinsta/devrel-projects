"""Published baseline scores from Context-1 and SID-1 for comparison."""

# Context-1 (Chroma, March 2026)
# Source: https://www.trychroma.com/research/context-1
CONTEXT_1 = {
    "model": "Context-1 (20B MoE, 3.6B active)",
    "training": "SFT + CISPO on Tinker",
    "retrieval": "Chroma (client-side BM25 + dense fusion)",
    "scores": {
        "HotpotQA": {"f1": 0.99, "final_answer_found": 0.99},
        "FRAMES": {"f1": 0.82, "final_answer_found": 0.96},
        "BrowseComp-Plus": {"f1": 0.96},
        "LongSeal": {"f1": 0.79},
        "SealQA": {"f1": 0.52},
        # Custom benchmarks (4x ensemble)
        "Web (Diff 2+)": {"f1": 0.82, "final_answer_found": 0.97},
        "Finance (Diff 1+)": {"f1": 0.82, "final_answer_found": 0.82},
        "Legal": {"f1": 0.82, "final_answer_found": 0.95},
        "Email": {"f1": 0.82, "final_answer_found": 0.98},
    },
    "efficiency": {
        "avg_tool_calls_per_turn": 2.56,
        "avg_trajectory_turns": 5.2,
        "prune_accuracy": 0.941,
        "tokens_per_second": 450,  # approximate, B200 GPU
    },
}

# SID-1 (SID AI, December 2025)
# Source: https://sid.ai/blog
SID_1 = {
    "model": "SID-1 (Qwen3-14B)",
    "training": "RL-trained agentic retrieval",
    "retrieval": "Proprietary",
    "scores": {
        # Custom benchmark (191 questions, 5 domains)
        "SID-Custom (1x)": {"recall": 0.77, "ndcg": 0.70},
        "SID-Custom (4x)": {"recall": 0.84, "ndcg": 0.73},
        # Public benchmarks (saturated)
        "HotpotQA": {"note": "saturated, near-perfect"},
        "SciFact": {"note": "saturated, near-perfect"},
    },
    "efficiency": {
        "latency_seconds": 6,  # per query
        "cost_vs_gpt5": "24x faster",
        "cost_vs_sonnet": "374x cheaper self-hosted",
    },
}

# Our baseline (untrained INTELLECT-3.1 with Asteroid toolkit)
ASTEROID_BASELINE = {
    "model": "INTELLECT-3.1 (106B MoE, 12B active) untrained",
    "training": "None (base model)",
    "retrieval": "Qdrant (server-side BM25 + dense RRF)",
    "scores": {},  # filled at runtime
    "efficiency": {},
}


def print_comparison(benchmark: str, our_score: float, our_metric: str = "score"):
    """Print our score alongside published baselines."""
    print(f"\n  Comparison for {benchmark}:")
    print(f"    Asteroid (ours):  {our_metric}={our_score:.2f}")

    if benchmark in CONTEXT_1["scores"]:
        c1 = CONTEXT_1["scores"][benchmark]
        for k, v in c1.items():
            if isinstance(v, float):
                print(f"    Context-1:        {k}={v:.2f}")

    if benchmark in SID_1["scores"]:
        s1 = SID_1["scores"][benchmark]
        for k, v in s1.items():
            if isinstance(v, float):
                print(f"    SID-1:            {k}={v:.2f}")
            elif isinstance(v, str):
                print(f"    SID-1:            {k}: {v}")


def print_efficiency_comparison(our_turns: float, our_tool_calls: float, our_tokens: float):
    """Print efficiency metrics alongside baselines."""
    print(f"\n  Efficiency comparison:")
    print(f"    Asteroid (ours):  turns={our_turns:.1f}, tool_calls={our_tool_calls:.1f}, tokens={our_tokens:,.0f}")
    c1e = CONTEXT_1["efficiency"]
    print(f"    Context-1:        turns={c1e['avg_trajectory_turns']}, tool_calls/turn={c1e['avg_tool_calls_per_turn']}, prune_acc={c1e['prune_accuracy']}")
    print(f"    SID-1:            latency={SID_1['efficiency']['latency_seconds']}s/query")
