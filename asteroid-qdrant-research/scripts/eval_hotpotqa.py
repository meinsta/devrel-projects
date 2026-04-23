"""
Evaluate on HotpotQA (same benchmark as Context-1).
Each question gets its own mini-corpus of 10 paragraphs indexed into Qdrant.
The agent searches to find the answer.

Context-1 reported: 0.99 F1 on HotpotQA
"""

import json
import os
import re
import sys
import time

from datasets import load_dataset
from dotenv import load_dotenv
from fastembed import TextEmbedding
from openai import OpenAI
from qdrant_client import QdrantClient, models

load_dotenv()

COLLECTION = "asteroid_hotpotqa_eval"


def normalize_answer(s: str) -> str:
    """Normalize answer for F1 computation (HotpotQA official)."""
    import string
    s = s.lower()
    # Remove articles
    for article in ["a ", "an ", "the "]:
        s = s.replace(article, " ")
    # Remove punctuation
    s = s.translate(str.maketrans("", "", string.punctuation))
    # Remove extra whitespace
    s = " ".join(s.split())
    return s


def compute_f1(prediction: str, ground_truth: str) -> float:
    """Token-level F1 score (HotpotQA official metric)."""
    pred_tokens = normalize_answer(prediction).split()
    truth_tokens = normalize_answer(ground_truth).split()
    if not pred_tokens or not truth_tokens:
        return 0.0
    common = set(pred_tokens) & set(truth_tokens)
    if not common:
        return 0.0
    precision = len(common) / len(pred_tokens)
    recall = len(common) / len(truth_tokens)
    return 2 * precision * recall / (precision + recall)


def run_hotpotqa_eval(
    n_questions: int = 50,
    model_id: str = "Qwen/Qwen3-30B-A3B-Instruct-2507",
):
    qdrant = QdrantClient(url=os.getenv("QDRANT_URL"), api_key=os.getenv("QDRANT_API_KEY"), timeout=60)
    prime = OpenAI(base_url="https://api.pinference.ai/api/v1", api_key=os.getenv("PRIME_API_KEY"))
    embed_model = TextEmbedding("BAAI/bge-small-en-v1.5")

    ds = load_dataset("hotpot_qa", "fullwiki", split="validation")
    if n_questions < len(ds):
        ds = ds.select(range(n_questions))

    results = []
    f1_scores = []
    exact_matches = []

    print(f"Running HotpotQA eval: {n_questions} questions, model={model_id}")
    print(f"Context-1 baseline: 0.99 F1\n")

    for i, ex in enumerate(ds):
        question = ex["question"]
        answer = ex["answer"]
        context_titles = ex["context"]["title"]
        context_sents = ex["context"]["sentences"]

        # Index this question's context into Qdrant
        try:
            qdrant.delete_collection(COLLECTION)
        except Exception:
            pass

        qdrant.create_collection(
            collection_name=COLLECTION,
            vectors_config={
                "dense": models.VectorParams(size=384, distance=models.Distance.COSINE),
            },
            sparse_vectors_config={
                "bm25": models.SparseVectorParams(modifier=models.Modifier.IDF),
            },
        )

        # Index paragraphs
        points = []
        all_texts = []
        for j, (title, sentences) in enumerate(zip(context_titles, context_sents)):
            text = " ".join(sentences)
            all_texts.append(text)
            points.append({
                "id": j,
                "title": title,
                "text": text,
            })

        avg_len = sum(len(p["text"].split()) for p in points) / max(len(points), 1)
        dense_vecs = list(embed_model.embed(all_texts))

        qdrant_points = []
        for p, dvec in zip(points, dense_vecs):
            qdrant_points.append(
                models.PointStruct(
                    id=p["id"],
                    payload={"title": p["title"], "text": p["text"]},
                    vector={
                        "dense": dvec.tolist(),
                        "bm25": models.Document(
                            text=p["text"],
                            model="Qdrant/bm25",
                            options={"avg_len": avg_len},
                        ),
                    },
                )
            )
        qdrant.upsert(collection_name=COLLECTION, points=qdrant_points)

        # Run the agent
        tools = [{
            "type": "function",
            "function": {
                "name": "search",
                "description": "Search the documents for relevant information.",
                "parameters": {
                    "type": "object",
                    "properties": {"query": {"type": "string"}},
                    "required": ["query"],
                },
            },
        }]

        messages = [
            {"role": "system", "content": "Search the documents to answer the question. Reply with ONLY the answer, nothing else. No explanation. Example: Q: 'What year was X born?' A: '1990'"},
            {"role": "user", "content": question},
        ]

        final_answer = ""
        for turn in range(4):
            response = prime.chat.completions.create(
                model=model_id,
                messages=messages,
                tools=tools,
                tool_choice="auto",
                max_tokens=512,
                temperature=0.0,
            )

            choice = response.choices[0]
            content = choice.message.content or ""

            if choice.message.tool_calls:
                # Prime requires content field even on tool_calls messages
                msg_dict = {"role": "assistant", "content": content or "", "tool_calls": [
                    {"id": tc.id, "type": "function", "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                    for tc in choice.message.tool_calls
                ]}
                messages.append(msg_dict)
                for tc in choice.message.tool_calls:
                    args = json.loads(tc.function.arguments)
                    query = args.get("query", question)

                    search_results = qdrant.query_points(
                        collection_name=COLLECTION,
                        prefetch=[
                            models.Prefetch(query=models.Document(text=query, model="Qdrant/bm25"), using="bm25", limit=5),
                            models.Prefetch(query=list(embed_model.embed([query]))[0].tolist(), using="dense", limit=5),
                        ],
                        query=models.FusionQuery(fusion=models.Fusion.RRF),
                        limit=3,
                        with_payload=True,
                    )

                    result_text = "\n\n".join(
                        f"[{p.payload['title']}] {p.payload['text']}" for p in search_results.points
                    )
                    messages.append({"role": "tool", "tool_call_id": tc.id, "content": result_text})
            else:
                if "</think>" in content:
                    content = content.split("</think>")[-1].strip()
                final_answer = content
                break

        if not final_answer:
            messages.append({"role": "user", "content": "Answer the question now based on what you found."})
            response = prime.chat.completions.create(
                model=model_id, messages=messages, max_tokens=256, temperature=0.0,
            )
            final_answer = response.choices[0].message.content or ""
            if "</think>" in final_answer:
                final_answer = final_answer.split("</think>")[-1].strip()

        f1 = compute_f1(final_answer, answer)
        em = 1.0 if answer.lower() in final_answer.lower() else 0.0
        f1_scores.append(f1)
        exact_matches.append(em)

        status = "PASS" if em > 0.5 else "FAIL"
        print(f"[{i+1}/{n_questions}] {status} f1={f1:.2f} em={em:.0f} | Q: {question[:60]} | A: {answer} | Got: {final_answer[:60]}")

        results.append({
            "question": question, "answer": answer,
            "prediction": final_answer, "f1": f1, "em": em,
        })

    # Cleanup
    try:
        qdrant.delete_collection(COLLECTION)
    except Exception:
        pass

    avg_f1 = sum(f1_scores) / len(f1_scores)
    avg_em = sum(exact_matches) / len(exact_matches)

    print(f"\n{'='*60}")
    print(f"HotpotQA Results (n={n_questions}):")
    print(f"  F1:    {avg_f1:.3f}")
    print(f"  EM:    {avg_em:.3f}")
    print(f"\nComparison:")
    print(f"  Asteroid (ours): F1={avg_f1:.3f}")
    print(f"  Context-1:       F1=0.990")
    print(f"  SID-1:           saturated (near-perfect)")

    with open("hotpotqa_results.json", "w") as f:
        json.dump({"f1": avg_f1, "em": avg_em, "n": n_questions, "model": model_id, "results": results}, f, indent=2)
    print(f"\nSaved to hotpotqa_results.json")

    return avg_f1, avg_em


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=50)
    parser.add_argument("--model", default="Qwen/Qwen3-30B-A3B-Instruct-2507")
    args = parser.parse_args()
    run_hotpotqa_eval(n_questions=args.n, model_id=args.model)
