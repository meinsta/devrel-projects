"""SFT-style environment over the FRAMES tool harness.

The environment uses the same Qdrant-backed retrieval tools as the main FRAMES env
but sources examples from the gold-trajectory dataset.
"""

from __future__ import annotations

import hashlib
import json
from typing import cast

from datasets import load_dataset
from fastembed import TextEmbedding

import verifiers as vf

try:
    from .shared import (
        FramesQdrantMixin,
        build_qdrant_client,
        extract_user_question,
    )
except ImportError:
    from shared import FramesQdrantMixin, build_qdrant_client, extract_user_question


GOLD = {}
try:
    with open("sft_frames.jsonl") as f:
        for line in f:
            item = json.loads(line)
            GOLD[item["question"]] = item
except FileNotFoundError:
    pass


SYSTEM_PROMPT = """You are an expert search agent. Answer the question by searching the provided documents.

Available tools:
- search_corpus(query): retrieve candidate documents and snippets. It returns stable doc_ids like d001.
- read_document(doc_id, query=""): inspect one document by doc_id.
- text_search(phrase, doc_id=""): exact-match grep for names, numbers, or dates.
- prune_chunks(doc_ids): optional. Restrict future search_corpus and text_search calls to a comma-separated list of doc_ids. Use 'all' to clear the focus.

Recommended workflow:
1. Start with search_corpus to discover promising doc_ids.
2. Read the best documents with read_document.
3. Use text_search for exact values.
4. Use prune_chunks only if narrowing the remaining search space will help.

Think step by step. Give a short, direct answer."""


def search_corpus(query: str) -> str:
    """Search across all indexed Wikipedia documents."""
    return "stub"


def read_document(doc_id: str, query: str = "") -> str:
    """Read a single document by doc_id."""
    return "stub"


def text_search(phrase: str, doc_id: str = "") -> str:
    """Find an exact phrase, number, date, or name."""
    return "stub"


def prune_chunks(doc_ids: str) -> str:
    """Restrict future search_corpus and text_search calls to a comma-separated list of doc_ids."""
    return "stub"


def _normalize(s):
    import string

    s = s.lower()
    for article in ["a ", "an ", "the "]:
        s = s.replace(article, " ")
    s = s.translate(str.maketrans("", "", string.punctuation))
    return " ".join(s.split())


def reward_answer_found(parser, completion, answer, **kwargs) -> float:
    """Did the model find the correct answer?"""
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
        return 0.0
    matched = sum(1 for word in answer_words if word in _normalize(final_content))
    ratio = matched / len(answer_words)
    if ratio >= 0.8:
        return 0.8
    if ratio >= 0.5:
        return 0.4
    return 0.0


class SFTFramesEnv(FramesQdrantMixin, vf.ToolEnv):

    def __init__(self, max_turns: int = 8, **kwargs):
        ds = load_dataset("thierrydamiba/asteroid-sft-frames", split="train")

        rubric = vf.Rubric()
        rubric.add_reward_func(reward_answer_found, weight=1.0)

        super().__init__(
            tools=[search_corpus, read_document, text_search, prune_chunks],
            max_turns=max_turns,
            dataset=ds,
            eval_dataset=ds,
            system_prompt=SYSTEM_PROMPT,
            rubric=rubric,
            env_id=kwargs.pop("env_id", "sft-frames"),
            **kwargs,
        )

        self._qdrant = None
        self._embed_model = None
        self._title_cache = {}
        self._doc_catalog_cache = {}

    def _get_qdrant(self):
        if self._qdrant is None:
            self._qdrant = build_qdrant_client(timeout=30)
        return self._qdrant

    def _get_embed_model(self):
        if self._embed_model is None:
            self._embed_model = TextEmbedding("BAAI/bge-small-en-v1.5")
        return self._embed_model

    def _embed(self, text):
        return list(self._get_embed_model().embed([text]))[0].tolist()

    async def setup_state(self, state: vf.State) -> vf.State:
        state = await super().setup_state(state)
        question = extract_user_question(state.get("prompt", []))
        state["collection_id"] = f"fr_{hashlib.md5(question.encode()).hexdigest()[:10]}"
        state["focus_doc_ids"] = []
        state["seen_chunk_ids"] = []
        state["seen_doc_ids"] = []
        state["tool_call_count"] = 0
        state["consecutive_prunes"] = 0
        return state

    async def call_tool(self, tool_name, tool_args, tool_call_id, **kwargs):
        try:
            result = self.run_tool(tool_name, tool_args)
        except Exception as exc:
            result = f"Tool error: {str(exc)}"

        return cast(vf.Message, {"role": "tool", "content": result, "tool_call_id": tool_call_id})

    async def env_response(self, messages, state, **kwargs):
        self._current_state = state
        result = await super().env_response(messages, state, **kwargs)
        self._current_state = None
        return result


def load_environment(env_id="sft-frames", **kwargs):
    return SFTFramesEnv(
        env_id=env_id,
        max_turns=kwargs.get("max_turns", 8),
    )
