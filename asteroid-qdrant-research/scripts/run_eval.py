"""Run evaluation on wiki trivia questions."""

import argparse
import os

from dotenv import load_dotenv
from fastembed import TextEmbedding
from openai import OpenAI
from qdrant_client import QdrantClient

from asteroid.agent.harness import AgentHarness
from asteroid.agent.logging import log_eval_results
from asteroid.eval.runner import run_eval
from asteroid.tools.search import QdrantSearchTools

load_dotenv()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--collection", default="asteroid_wiki")
    parser.add_argument("--model", default="PrimeIntellect/INTELLECT-3.1")
    parser.add_argument("--n", type=int, default=10)
    parser.add_argument("--output", default="eval_results.json")
    parser.add_argument("--max-turns", type=int, default=8)
    args = parser.parse_args()

    qdrant = QdrantClient(url=os.getenv("QDRANT_URL"), api_key=os.getenv("QDRANT_API_KEY"), timeout=30)
    prime = OpenAI(base_url="https://api.pinference.ai/api/v1", api_key=os.getenv("PRIME_API_KEY"))
    embed_model = TextEmbedding("BAAI/bge-small-en-v1.5")

    tools = QdrantSearchTools(qdrant=qdrant, embed_model=embed_model, collection=args.collection)
    harness = AgentHarness(
        llm=prime,
        tools=tools,
        model=args.model,
        max_turns=args.max_turns,
        verbose=True,
    )

    results = run_eval(
        harness=harness,
        n_samples=args.n,
        judge_client=prime,
        judge_model=args.model,
        output_file=args.output,
    )

    log_eval_results(results, run_name=f"eval-{args.model.split('/')[-1]}")


if __name__ == "__main__":
    main()
