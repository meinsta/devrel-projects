"""FRAMES benchmark environment for prime-rl.

824 multi-hop questions requiring 2-15 Wikipedia articles.
Qdrant-backed retrieval harness with 4 canonical tools:
- search_corpus: retrieve candidate documents and snippets
- read_document: inspect one document by stable doc_id
- text_search: exact text/number match across the corpus or one document
- prune_chunks: optionally focus later retrieval on a small doc set

Output contract: ranked documents only, never free-form answers.
"""

from __future__ import annotations

import hashlib
import json
from typing import cast

import httpx
from datasets import load_dataset
from fastembed import TextEmbedding
from qdrant_client import models

import verifiers as vf

try:
    from .shared import (
        FramesQdrantMixin,
        build_qdrant_client,
        extract_user_question,
        get_preindexed_collection_ids,
    )
    from .retrieval_output import (
        RETRIEVAL_OUTPUT_INSTRUCTIONS,
        parse_retrieval_output,
    )
    from .metrics import (
        compute_reward,
        evaluate_retrieval,
    )
    from .token_budget import TokenBudget
except ImportError:
    from shared import (
        FramesQdrantMixin,
        build_qdrant_client,
        extract_user_question,
        get_preindexed_collection_ids,
    )
    from retrieval_output import (
        RETRIEVAL_OUTPUT_INSTRUCTIONS,
        parse_retrieval_output,
    )
    from metrics import (
        compute_reward,
        evaluate_retrieval,
    )
    from token_budget import TokenBudget


SYSTEM_PROMPT = """Search the provided Wikipedia articles to answer the question.
You have four tools:
- search_corpus(query): retrieve candidate documents and snippets. It returns stable doc_ids like d001.
- read_document(doc_id, query=""): inspect one document by doc_id. Use this instead of guessing article titles.
- text_search(phrase, doc_id=""): exact-match grep for names, numbers, or dates across all documents or one doc.
- prune_chunks(doc_ids): optional. Restrict future search_corpus and text_search calls to a comma-separated list of doc_ids. Use 'all' to clear the focus.

Recommended workflow:
1. Start with search_corpus to discover promising doc_ids.
2. Read the best documents with read_document.
3. Use text_search for exact values.
4. Use prune_chunks only if narrowing the remaining search space will help.

Think step by step. Give a short, direct answer."""

SYSTEM_PROMPT_RETRIEVAL = """Search the provided Wikipedia articles to find documents that answer the question.
You have four tools:
- search_corpus(query): retrieve candidate documents and snippets. It returns stable doc_ids like d001.
- read_document(doc_id, query=""): inspect one document by doc_id. Use this instead of guessing article titles.
- text_search(phrase, doc_id=""): exact-match grep for names, numbers, or dates across all documents or one doc.
- prune_chunks(doc_ids): optional. Restrict future search_corpus and text_search calls to a comma-separated list of doc_ids. Use 'all' to clear the focus.

Recommended workflow:
1. Start with search_corpus to discover promising doc_ids.
2. Read the best documents with read_document.
3. Use text_search for exact values.
4. Use prune_chunks only if narrowing the remaining search space will help.

Think step by step.

""" + RETRIEVAL_OUTPUT_INSTRUCTIONS


def search_corpus(query: str) -> str:
    """Search across all indexed Wikipedia documents.

    Returns candidate documents with stable doc_ids and the strongest snippets.
    """
    return "stub"


def read_document(doc_id: str, query: str = "") -> str:
    """Read a single document by doc_id.

    Pass an optional query to retrieve the most relevant passages from that document.
    """
    return "stub"


def text_search(phrase: str, doc_id: str = "") -> str:
    """Find an exact phrase, number, date, or name.

    Pass an optional doc_id to restrict the exact match search to one document.
    """
    return "stub"


def prune_chunks(doc_ids: str) -> str:
    """Restrict future search_corpus and text_search calls to a comma-separated list of doc_ids.

    Pass 'all' or an empty string to clear the focus and search the full collection again.
    """
    return "stub"


def _load_curriculum_env_cls():
    try:
        from .curriculum import CurriculumFramesEnv
    except ImportError:
        from curriculum import CurriculumFramesEnv
    return CurriculumFramesEnv


def _normalize(s: str) -> str:
    import string

    s = s.lower()
    for article in ["a ", "an ", "the "]:
        s = s.replace(article, " ")
    s = s.translate(str.maketrans("", "", string.punctuation))
    return " ".join(s.split())


def _compute_f1(prediction: str, ground_truth: str) -> float:
    pred_tokens = _normalize(prediction).split()
    truth_tokens = _normalize(ground_truth).split()
    if not pred_tokens or not truth_tokens:
        return 0.0
    common = set(pred_tokens) & set(truth_tokens)
    if not common:
        return 0.0
    precision = len(common) / len(pred_tokens)
    recall = len(common) / len(truth_tokens)
    return 2 * precision * recall / (precision + recall)


def _fetch_wikipedia(url: str) -> tuple[str, str]:
    """Fetch Wikipedia article text from URL."""
    try:
        title = url.rstrip("/").split("/wiki/")[-1].replace("_", " ")
        api_title = url.split("/wiki/")[-1]
        api_url = (
            "https://en.wikipedia.org/w/api.php"
            f"?action=query&titles={api_title}&prop=extracts&explaintext=1&format=json"
        )
        resp = httpx.get(
            api_url,
            timeout=10,
            follow_redirects=True,
            headers={"User-Agent": "Asteroid/1.0 (research)"},
        )
        if resp.status_code == 200:
            pages = resp.json().get("query", {}).get("pages", {})
            for page in pages.values():
                text = page.get("extract", "")
                if text:
                    return page.get("title", title), text[:15000]
        return title, f"Article: {title}"
    except Exception:
        title = url.rstrip("/").split("/")[-1].replace("_", " ")
        return title, f"Article: {title}"


def reward_answer_found(parser, completion, answer, **kwargs) -> float:
    """Did the model find the correct answer? Checks containment, not exact F1."""
    if not completion or not answer:
        return 0.0
    messages = completion if isinstance(completion, list) else []
    final_content = ""
    for msg in reversed(messages):
        if isinstance(msg, dict):
            content = msg.get("content", "") or ""
            role = msg.get("role", "")
        else:
            content = getattr(msg, "content", "") or ""
            role = getattr(msg, "role", "")
        if role == "assistant" and content:
            if "</think>" in content:
                content = content.split("</think>")[-1].strip()
            if content and "<function=" not in content:
                final_content = content
                break

    if not final_content:
        return 0.0

    if _normalize(answer) in _normalize(final_content):
        return 1.0

    answer_words = [word for word in _normalize(answer).split() if len(word) > 2]
    if not answer_words:
        return 1.0 if _normalize(answer) in _normalize(final_content) else 0.0

    matched = sum(1 for word in answer_words if word in _normalize(final_content))
    ratio = matched / len(answer_words)
    if ratio >= 0.8:
        return 0.8
    if ratio >= 0.5:
        return 0.4
    return 0.0


def reward_retrieval(parser, completion, answer, **kwargs) -> float:
    """Retrieval-subagent reward using Context-1-style scoring.

    Parses the final output as a ranked document list and scores using
    F_beta + trajectory_recall + bonuses - penalties.
    """
    if not completion:
        return 0.0

    messages = completion if isinstance(completion, list) else []
    final_content = ""
    for msg in reversed(messages):
        if isinstance(msg, dict):
            content = msg.get("content", "") or ""
            role = msg.get("role", "")
        else:
            content = getattr(msg, "content", "") or ""
            role = getattr(msg, "role", "")
        if role == "assistant" and content:
            if "</think>" in content:
                content = content.split("</think>")[-1].strip()
            if content and "<function=" not in content:
                final_content = content
                break

    if not final_content:
        return 0.0

    result = parse_retrieval_output(final_content)
    output_doc_ids = result.doc_ids

    # Get gold doc_ids and seen doc_ids from state
    state = kwargs.get("state", {})
    gold_doc_ids = list(state.get("gold_doc_ids", []))
    # Use seen_doc_ids (doc-level tracking) for trajectory recall, not chunk IDs
    seen_doc_ids = list(state.get("seen_doc_ids", []))

    # Count tool calls and turns from messages
    tool_calls = sum(
        1 for msg in messages
        if (isinstance(msg, dict) and msg.get("role") == "tool")
        or (hasattr(msg, "role") and getattr(msg, "role") == "tool")
    )
    turns = sum(
        1 for msg in messages
        if (isinstance(msg, dict) and msg.get("role") == "assistant")
        or (hasattr(msg, "role") and getattr(msg, "role") == "assistant")
    )

    # final_answer_found requires overlap between output and gold docs
    if gold_doc_ids:
        final_answer_found = bool(set(output_doc_ids) & set(gold_doc_ids))
    else:
        final_answer_found = bool(output_doc_ids) and not result.is_empty

    metrics = evaluate_retrieval(
        output_doc_ids=output_doc_ids,
        gold_doc_ids=gold_doc_ids,
        seen_doc_ids=seen_doc_ids,
        final_answer_found=final_answer_found,
        tool_calls=tool_calls,
        turns=turns,
    )

    # Get consecutive prune count from state (tracked by call_tool)
    consecutive_prunes = state.get("consecutive_prunes", 0) if state else 0

    return compute_reward(metrics, consecutive_prunes=consecutive_prunes)


def reward_f1(parser, completion, answer, **kwargs) -> float:
    """F1-based reward for FRAMES."""
    if not completion or not answer:
        return 0.0
    messages = completion if isinstance(completion, list) else []
    final_content = ""
    for msg in reversed(messages):
        if isinstance(msg, dict):
            content = msg.get("content", "") or ""
            role = msg.get("role", "")
        else:
            content = getattr(msg, "content", "") or ""
            role = getattr(msg, "role", "")
        if role == "assistant" and content:
            if "</think>" in content:
                content = content.split("</think>")[-1].strip()
            if content and "<function=" not in content:
                final_content = content
                break

    if not final_content:
        return 0.0

    f1 = _compute_f1(final_content, answer)
    if _normalize(answer) in _normalize(final_content):
        f1 = max(f1, 0.8)
    if len(final_content.split()) > 50:
        f1 *= 0.8
    return f1


class FramesSearchEnv(FramesQdrantMixin, vf.ToolEnv):

    def __init__(
        self,
        max_turns: int = 8,
        n_questions: int = 824,
        use_preindexed: bool = True,
        holdout_frac: float = 0.0,
        use_retrieval_reward: bool = False,
        token_budget: TokenBudget | None = None,
        **kwargs,
    ):
        ds = load_dataset("google/frames-benchmark", split="test")

        ds = ds.rename_column("Prompt", "question")
        ds = ds.rename_column("Answer", "answer")

        self._use_preindexed = use_preindexed
        self._use_retrieval_reward = use_retrieval_reward
        self._token_budget = token_budget or TokenBudget()

        if use_preindexed:
            indexed_ids = get_preindexed_collection_ids(timeout=15)

            keep = []
            for i in range(len(ds)):
                col_id = f"fr_{hashlib.md5(ds[i]['question'].encode()).hexdigest()[:10]}"
                if col_id in indexed_ids:
                    keep.append(i)

            ds = ds.select(keep)
            print(f"FRAMES: {len(keep)} pre-indexed questions (of {n_questions} requested)")

        # Deterministic train/holdout split by index (last N% held out)
        holdout_frac = float(holdout_frac)
        eval_ds = None
        if holdout_frac > 0:
            split_idx = int(len(ds) * (1 - holdout_frac))
            eval_ds = ds.select(range(split_idx, min(split_idx + 50, len(ds))))
            ds = ds.select(range(split_idx))
            print(f"FRAMES: training on first {split_idx} questions (holdout_frac={holdout_frac})")

        if n_questions < len(ds):
            ds = ds.select(range(n_questions))

        if eval_ds is None:
            eval_ds = ds.select(range(min(50, len(ds))))

        rubric = vf.Rubric()
        if use_retrieval_reward:
            rubric.add_reward_func(reward_retrieval, weight=1.0)
        else:
            rubric.add_reward_func(reward_answer_found, weight=1.0)

        prompt = SYSTEM_PROMPT_RETRIEVAL if use_retrieval_reward else SYSTEM_PROMPT

        super().__init__(
            tools=[search_corpus, read_document, text_search, prune_chunks],
            max_turns=max_turns,
            dataset=ds,
            eval_dataset=eval_ds,
            system_prompt=prompt,
            rubric=rubric,
            env_id=kwargs.pop("env_id", "frames-search"),
            **kwargs,
        )

        self._qdrant = None
        self._embed_model = None
        self._wiki_cache = {}
        self._title_cache = {}
        self._doc_catalog_cache = {}

    def _resolve_gold_doc_ids(self, collection_id: str, row: dict) -> list[str]:
        """Map gold Wikipedia URLs from the dataset row to doc_ids in the collection."""
        if not row:
            return []
        try:
            # Extract gold article titles from wiki URLs
            wiki_links = row.get("wiki_links", [])
            if isinstance(wiki_links, str):
                import ast
                try:
                    wiki_links = ast.literal_eval(wiki_links)
                except Exception:
                    wiki_links = [u.strip() for u in wiki_links.split(",") if u.strip()]

            gold_titles = set()
            for url in (wiki_links or []):
                if "wikipedia" in str(url):
                    title = url.rstrip("/").split("/wiki/")[-1].replace("_", " ")
                    from urllib.parse import unquote
                    gold_titles.add(unquote(title))

            if not gold_titles:
                return []

            # Match against collection titles
            gold_doc_ids = []
            for doc_id, title in self._get_doc_catalog(collection_id):
                if title in gold_titles:
                    gold_doc_ids.append(doc_id)
            return gold_doc_ids
        except Exception:
            return []

    def _get_qdrant(self):
        if self._qdrant is None:
            self._qdrant = build_qdrant_client(timeout=30)
        return self._qdrant

    def _get_embed_model(self):
        if self._embed_model is None:
            self._embed_model = TextEmbedding("BAAI/bge-small-en-v1.5")
        return self._embed_model

    def _embed(self, text: str) -> list[float]:
        return list(self._get_embed_model().embed([text]))[0].tolist()

    async def setup_state(self, state: vf.State) -> vf.State:
        state = await super().setup_state(state)
        row = state.get("row", {})

        # Initialize novelty tracking
        state["seen_chunk_ids"] = []
        state["seen_doc_ids"] = []
        state["tool_call_count"] = 0
        state["consecutive_prunes"] = 0

        if self._use_preindexed:
            question = extract_user_question(state.get("prompt", []))
            state["collection_id"] = f"fr_{hashlib.md5(question.encode()).hexdigest()[:10]}"
            state["focus_doc_ids"] = []
            # Map gold wiki URLs to doc_ids in the collection
            state["gold_doc_ids"] = self._resolve_gold_doc_ids(
                state["collection_id"], row
            )
            return state

        if not row:
            return state

        wiki_urls = []
        wiki_links = row.get("wiki_links")
        if wiki_links:
            if isinstance(wiki_links, str):
                try:
                    wiki_urls = json.loads(wiki_links)
                except Exception:
                    wiki_urls = [url.strip() for url in wiki_links.split(",") if url.strip()]
            elif isinstance(wiki_links, list):
                wiki_urls = wiki_links

        for i in range(1, 12):
            key = f"wikipedia_link_{i}" if i < 11 else "wikipedia_link_11+"
            val = row.get(key)
            if val and isinstance(val, str) and "wikipedia" in val:
                wiki_urls.append(val)

        wiki_urls = list(set(url for url in wiki_urls if url and "wikipedia" in str(url)))
        if not wiki_urls:
            return state

        question = row.get("question", row.get("Prompt", ""))
        collection_id = f"fr_{hashlib.md5(question.encode()).hexdigest()[:10]}"
        state["collection_id"] = collection_id
        state["focus_doc_ids"] = []

        qdrant = self._get_qdrant()
        try:
            try:
                qdrant.delete_collection(collection_id)
            except Exception:
                pass

            qdrant.create_collection(
                collection_name=collection_id,
                vectors_config={"dense": models.VectorParams(size=384, distance=models.Distance.COSINE)},
                sparse_vectors_config={
                    "bm25": models.SparseVectorParams(modifier=models.Modifier.IDF)
                },
            )

            all_chunks = []
            for url in wiki_urls[:10]:
                if url in self._wiki_cache:
                    title, text = self._wiki_cache[url]
                else:
                    title, text = _fetch_wikipedia(url)
                    self._wiki_cache[url] = (title, text)
                words = text.split()
                for start in range(0, len(words), 250):
                    chunk = " ".join(words[start:start + 300])
                    all_chunks.append({"title": title, "text": chunk})

            if not all_chunks:
                return state

            avg_len = sum(len(chunk["text"].split()) for chunk in all_chunks) / len(all_chunks)
            texts = [chunk["text"] for chunk in all_chunks]
            dense_vecs = list(self._get_embed_model().embed(texts))

            points = []
            for idx, (chunk, dense_vec) in enumerate(zip(all_chunks, dense_vecs)):
                points.append(
                    models.PointStruct(
                        id=idx,
                        payload={"title": chunk["title"], "text": chunk["text"]},
                        vector={
                            "dense": dense_vec.tolist(),
                            "bm25": models.Document(
                                text=chunk["text"],
                                model="Qdrant/bm25",
                                options={"avg_len": avg_len},
                            ),
                        },
                    )
                )
            qdrant.upsert(collection_name=collection_id, points=points)
            self._title_cache.pop(collection_id, None)
            self._doc_catalog_cache.pop(collection_id, None)
            state["article_titles"] = list(set(chunk["title"] for chunk in all_chunks))
            # Populate gold_doc_ids for non-preindexed runs
            state["gold_doc_ids"] = self._resolve_gold_doc_ids(collection_id, row)
        except Exception as exc:
            state["index_error"] = str(exc)

        return state

    async def call_tool(self, tool_name: str, tool_args: dict, tool_call_id: str, **kwargs) -> vf.Message:
        state = getattr(self, "_current_state", None)

        # Token budget enforcement
        if state is not None:
            current_tokens = state.get("token_usage", 0)
            if not self._token_budget.is_tool_allowed(tool_name, current_tokens):
                return cast(vf.Message, {
                    "role": "tool",
                    "content": self._token_budget.guidance_message(current_tokens),
                    "tool_call_id": tool_call_id,
                })

            # Track tool calls
            state["tool_call_count"] = state.get("tool_call_count", 0) + 1
            if tool_name in ("prune_chunks", "prune_documents"):
                state["consecutive_prunes"] = state.get("consecutive_prunes", 0) + 1
            else:
                state["consecutive_prunes"] = 0

        try:
            result = self.run_tool(tool_name, tool_args)
        except Exception as exc:
            result = f"Tool error: {str(exc)}"

        # Estimate and accumulate token usage (words * 1.3 approximation)
        if state is not None:
            result_tokens = int(len(result.split()) * 1.3)
            state["token_usage"] = state.get("token_usage", 0) + result_tokens

        # Inject token budget guidance if above soft threshold
        if state is not None:
            current_tokens = state.get("token_usage", 0)
            guidance = self._token_budget.guidance_message(current_tokens)
            if guidance:
                result = result + "\n\n" + guidance

        return cast(vf.Message, {"role": "tool", "content": result, "tool_call_id": tool_call_id})

    async def env_response(self, messages, state, **kwargs):
        self._current_state = state
        # Count tokens from the latest assistant message
        if messages and state is not None:
            last = messages[-1]
            content = ""
            if isinstance(last, dict):
                content = last.get("content", "") or ""
            else:
                content = getattr(last, "content", "") or ""
            if content:
                state["token_usage"] = state.get("token_usage", 0) + int(len(content.split()) * 1.3)
        result = await super().env_response(messages, state, **kwargs)
        self._current_state = None
        return result


def load_environment(env_id: str = "frames-search", **kwargs):
    benchmark = kwargs.pop("benchmark", None)
    if benchmark == "browsecomp":
        try:
            from .browsecomp_env import BrowseCompEnv
        except ImportError:
            from browsecomp_env import BrowseCompEnv
        return BrowseCompEnv(env_id=env_id, **kwargs)
    stage = kwargs.pop("stage", None)
    if stage is not None:
        CurriculumFramesEnv = _load_curriculum_env_cls()
        return CurriculumFramesEnv(env_id=env_id, stage=int(stage), **kwargs)
    return FramesSearchEnv(env_id=env_id, **kwargs)
