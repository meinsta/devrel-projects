"""Generate gold search trajectories for FRAMES using Claude (via the current session's reasoning).

For each indexed FRAMES question:
1. Search Qdrant with multiple strategies
2. Record which tools were used and what was found
3. Produce the correct answer
4. Save as SFT training data
"""

import hashlib, json, os
from dotenv import load_dotenv
from fastembed import TextEmbedding
from openai import OpenAI
from qdrant_client import QdrantClient, models

load_dotenv()

qdrant = QdrantClient(url=os.getenv("QDRANT_URL"), api_key=os.getenv("QDRANT_API_KEY"), timeout=30)
prime = OpenAI(base_url="https://api.pinference.ai/api/v1", api_key=os.getenv("PRIME_API_KEY"))
embed = TextEmbedding("BAAI/bge-small-en-v1.5")

# Load indexed questions
with open("frames_indexed_questions.json") as f:
    questions = json.load(f)

print(f"Generating gold trajectories for {len(questions)} FRAMES questions")

SYSTEM = """You are an expert search agent. Answer the question by searching the provided documents.

You have these tools:
- search(query): hybrid search across all articles
- search_article(query, title): search within a specific article
- lookup(phrase): find exact text matches

Think step by step. Use multiple searches to find all needed information.
Give a short, direct final answer.

IMPORTANT: Call tools by using function calling. Do NOT answer from memory. ALWAYS search first."""

trajectories = []

for i, q in enumerate(questions):
    question = q["question"]
    answer = q["answer"]
    collection = q["collection"]

    print(f"\n[{i+1}/{len(questions)}] {question[:80]}...")
    print(f"  Gold answer: {answer}")

    messages = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": question},
    ]

    tools = [
        {"type": "function", "function": {
            "name": "search", "description": "Hybrid search across all articles",
            "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
        }},
        {"type": "function", "function": {
            "name": "search_article", "description": "Search within a specific article by title",
            "parameters": {"type": "object", "properties": {
                "query": {"type": "string"}, "title": {"type": "string"}
            }, "required": ["query", "title"]},
        }},
        {"type": "function", "function": {
            "name": "lookup", "description": "Find exact text, numbers, or dates",
            "parameters": {"type": "object", "properties": {"phrase": {"type": "string"}}, "required": ["phrase"]},
        }},
    ]

    trajectory = {"question": question, "answer": answer, "turns": []}

    for turn in range(6):
        try:
            response = prime.chat.completions.create(
                model="anthropic/claude-opus-4.6",
                messages=messages,
                tools=tools,
                tool_choice="auto",
                max_tokens=1024,
                temperature=0.0,
            )
        except Exception as e:
            print(f"  API error: {e}")
            break

        choice = response.choices[0]
        content = choice.message.content or ""

        if choice.message.tool_calls:
            msg_dict = {"role": "assistant", "content": content, "tool_calls": [
                {"id": tc.id, "type": "function", "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                for tc in choice.message.tool_calls
            ]}
            messages.append(msg_dict)

            for tc in choice.message.tool_calls:
                args = json.loads(tc.function.arguments)
                tool_name = tc.function.name

                # Execute against Qdrant
                try:
                    if tool_name == "search":
                        qvec = list(embed.embed([args["query"]]))[0].tolist()
                        results = qdrant.query_points(
                            collection_name=collection,
                            prefetch=[
                                models.Prefetch(query=models.Document(text=args["query"], model="Qdrant/bm25"), using="bm25", limit=10),
                                models.Prefetch(query=qvec, using="dense", limit=10),
                            ],
                            query=models.FusionQuery(fusion=models.Fusion.RRF),
                            limit=5, with_payload=True,
                        )
                        result = "\n\n".join(f"[{p.payload['title']}] {p.payload['text']}" for p in results.points)

                    elif tool_name == "search_article":
                        qvec = list(embed.embed([args["query"]]))[0].tolist()
                        results = qdrant.query_points(
                            collection_name=collection,
                            prefetch=[
                                models.Prefetch(query=models.Document(text=args["query"], model="Qdrant/bm25"), using="bm25", limit=10),
                                models.Prefetch(query=qvec, using="dense", limit=10),
                            ],
                            query=models.FusionQuery(fusion=models.Fusion.RRF),
                            query_filter=models.Filter(must=[models.FieldCondition(key="title", match=models.MatchValue(value=args["title"]))]),
                            limit=3, with_payload=True,
                        )
                        result = "\n\n".join(f"[{p.payload['title']}] {p.payload['text']}" for p in results.points)

                    elif tool_name == "lookup":
                        points, _ = qdrant.scroll(
                            collection_name=collection,
                            scroll_filter=models.Filter(must=[models.FieldCondition(key="text", match=models.MatchText(text=args["phrase"]))]),
                            limit=5, with_payload=True,
                        )
                        result = "\n\n".join(f"[{p.payload['title']}] {p.payload['text']}" for p in points)

                    else:
                        result = "Unknown tool"

                    if not result:
                        result = "No results found."

                except Exception as e:
                    result = f"Error: {e}"

                messages.append({"role": "tool", "tool_call_id": tc.id, "content": result})

                trajectory["turns"].append({
                    "tool": tool_name,
                    "args": args,
                    "result_length": len(result),
                })
                print(f"  Turn {turn}: {tool_name}({json.dumps(args)[:60]})")

        else:
            # Final answer
            if "</think>" in content:
                content = content.split("</think>")[-1].strip()
            trajectory["final_answer"] = content
            trajectory["num_turns"] = len(trajectory["turns"])

            # Check if correct
            import string
            def _norm(s):
                s = s.lower()
                for a in ["a ", "an ", "the "]: s = s.replace(a, " ")
                s = s.translate(str.maketrans("", "", string.punctuation))
                return " ".join(s.split())
            correct = _norm(answer) in _norm(content)
            trajectory["correct"] = correct
            print(f"  Answer: {content[:80]}")
            print(f"  Correct: {correct}")
            break

    trajectories.append(trajectory)

# Save
with open("gold_trajectories.json", "w") as f:
    json.dump(trajectories, f, indent=2)

correct = sum(1 for t in trajectories if t.get("correct"))
print(f"\n{'='*60}")
print(f"Generated {len(trajectories)} trajectories")
print(f"Correct: {correct}/{len(trajectories)} ({correct/len(trajectories)*100:.0f}%)")
print(f"Avg turns: {sum(t.get('num_turns', 0) for t in trajectories)/len(trajectories):.1f}")
print(f"Saved to gold_trajectories.json")
