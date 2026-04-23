"""Eval runner: load questions, run agent, score with LLM judge."""

import json
import os
import time

from datasets import load_dataset
from dotenv import load_dotenv
from openai import OpenAI

from ..agent.harness import AgentHarness, Trajectory


# Exact judge prompt from Prime's wiki-search environment
JUDGE_PROMPT = """Given a ground truth answer \
    and a response, determine if the response is both correct and coherent.

    Question:
    ```
    {question}
    ```

    Ground truth answer:
    ```
    {answer}
    ```

    Response:
    ```
    {response}
    ```

    Respond either "yes" or "no" only.

    If a response contains incoherent text, respond with "no" even if the correct answer is also present.
    """


def judge_answer(
    question: str,
    ground_truth: str,
    response: str,
    judge_client: OpenAI,
    judge_model: str = "PrimeIntellect/INTELLECT-3.1",
) -> tuple[float, str]:
    """Score an answer using an LLM judge. Returns (score, explanation)."""
    prompt = JUDGE_PROMPT.format(question=question, answer=ground_truth, response=response)

    result = judge_client.chat.completions.create(
        model=judge_model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=256,
        temperature=0.0,
    )

    judge_response = result.choices[0].message.content or ""

    # Strip thinking
    if "</think>" in judge_response:
        judge_response = judge_response.split("</think>")[-1].strip()

    # Match Prime's exact scoring: binary yes/no
    score = 1.0 if "yes" in judge_response.lower() else 0.0
    return score, judge_response


def run_eval(
    harness: AgentHarness,
    dataset_name: str = "willcb/wiki-trivia-questions-v4",
    split: str = "train",
    n_samples: int = 10,
    judge_client: OpenAI | None = None,
    judge_model: str = "PrimeIntellect/INTELLECT-3.1",
    output_file: str | None = None,
) -> list[dict]:
    """Run eval on a dataset. Returns list of result dicts."""

    ds = load_dataset(dataset_name, split=split)

    if n_samples < len(ds):
        ds = ds.select(range(n_samples))

    if judge_client is None:
        load_dotenv()
        judge_client = OpenAI(
            base_url="https://api.pinference.ai/api/v1",
            api_key=os.getenv("PRIME_API_KEY"),
        )

    results = []

    for i, row in enumerate(ds):
        question = row["question"]
        ground_truth = row["answer"]

        print(f"\n{'='*60}")
        print(f"[{i+1}/{len(ds)}] {question}")
        print(f"Ground truth: {ground_truth}")

        trajectory = harness.run(question)

        score, explanation = judge_answer(
            question=question,
            ground_truth=ground_truth,
            response=trajectory.final_answer,
            judge_client=judge_client,
            judge_model=judge_model,
        )

        result = {
            "question": question,
            "ground_truth": ground_truth,
            "answer": trajectory.final_answer,
            "score": score,
            "judge_explanation": explanation,
            "turns": len(trajectory.turns),
            "tool_calls": trajectory.tool_call_count,
            "total_tokens": trajectory.total_tokens,
            "total_latency": trajectory.total_latency,
        }
        results.append(result)

        status = "PASS" if score > 0.5 else "FAIL"
        print(f"  {status} (score={score}, turns={len(trajectory.turns)}, tools={trajectory.tool_call_count})")

    # Summary
    from .baselines import print_comparison, print_efficiency_comparison

    scores = [r["score"] for r in results]
    avg_turns = sum(r["turns"] for r in results) / len(results)
    avg_tools = sum(r["tool_calls"] for r in results) / len(results)
    avg_tokens = sum(r["total_tokens"] for r in results) / len(results)
    avg_latency = sum(r["total_latency"] for r in results) / len(results)

    print(f"\n{'='*60}")
    print(f"Results: {sum(scores)}/{len(scores)} correct ({sum(scores)/len(scores)*100:.0f}%)")
    print(f"Avg turns: {avg_turns:.1f}")
    print(f"Avg tool calls: {avg_tools:.1f}")
    print(f"Avg tokens: {avg_tokens:,.0f}")
    print(f"Avg latency: {avg_latency:.1f}s")

    # Compare against published baselines
    accuracy = sum(scores) / len(scores)
    print_comparison("HotpotQA", accuracy, "accuracy")
    print_efficiency_comparison(avg_turns, avg_tools, avg_tokens)

    if output_file:
        with open(output_file, "w") as f:
            json.dump(results, f, indent=2)
        print(f"Results saved to {output_file}")

    return results
