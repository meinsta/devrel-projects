"""Per-tool curriculum for FRAMES.

Each stage trains one retrieval capability, then composes them on the full tasks.

Stage 1: search_corpus only (base retrieval, ~200 questions)
Stage 2: search_corpus + read_document (document selection, ~300 questions)
Stage 3: search_corpus + read_document + text_search (exact match, ~380 questions)
Stage 4: search_corpus + read_document + text_search + prune_chunks (full multi-hop, all 824)
"""

from __future__ import annotations

import hashlib
from typing import cast

from datasets import load_dataset
from fastembed import TextEmbedding

import verifiers as vf

try:
    from .shared import (
        FramesQdrantMixin,
        build_qdrant_client,
        extract_user_question,
        get_preindexed_collection_ids,
        load_stage_indices,
    )
except ImportError:
    from shared import (
        FramesQdrantMixin,
        build_qdrant_client,
        extract_user_question,
        get_preindexed_collection_ids,
        load_stage_indices,
    )


PROMPTS = {
    1: "Search the documents to answer the question. Start with search_corpus. Use the doc_ids it returns. Give a short, direct answer.",
    2: "Search the documents to answer the question. Start with search_corpus to discover doc_ids, then inspect the best document with read_document. Give a short, direct answer.",
    3: "Search the documents to answer the question. Start with search_corpus to discover doc_ids, read the best documents with read_document, and use text_search for exact names, numbers, and dates. Give a short, direct answer.",
    4: """Search the documents to answer the question. You have four tools:
- search_corpus(query): retrieve candidate documents and snippets. It returns stable doc_ids like d001.
- read_document(doc_id, query=""): inspect one document by doc_id.
- text_search(phrase, doc_id=""): exact-match grep for names, numbers, or dates.
- prune_chunks(doc_ids): optional. Restrict future search_corpus and text_search calls to a comma-separated list of doc_ids. Use 'all' to clear the focus.

Recommended workflow:
1. Start with search_corpus to discover promising doc_ids.
2. Read the best documents with read_document.
3. Use text_search for exact values.
4. Use prune_chunks only if narrowing the remaining search space will help.

Think step by step. Give a short, direct answer.""",
}


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


STAGE_TOOLS = {
    1: [search_corpus],
    2: [search_corpus, read_document],
    3: [search_corpus, read_document, text_search],
    4: [search_corpus, read_document, text_search, prune_chunks],
}


def _normalize(s):
    import string

    s = s.lower()
    for article in ["a ", "an ", "the "]:
        s = s.replace(article, " ")
    s = s.translate(str.maketrans("", "", string.punctuation))
    return " ".join(s.split())


def reward_answer_found(parser, completion, answer, **kwargs) -> float:
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


class CurriculumFramesEnv(FramesQdrantMixin, vf.ToolEnv):

    def __init__(
        self,
        stage: int = 1,
        max_turns: int | None = None,
        n_questions: int | None = None,
        use_preindexed: bool = True,
        **kwargs,
    ):
        stage = int(stage)
        if stage not in STAGE_TOOLS:
            raise ValueError(f"Unknown curriculum stage: {stage}")
        self.stage = stage

        ds = load_dataset("google/frames-benchmark", split="test")
        ds = ds.rename_column("Prompt", "question")
        ds = ds.rename_column("Answer", "answer")

        stage_indices = load_stage_indices(stage)
        ds = ds.select(stage_indices)

        self._use_preindexed = use_preindexed
        if use_preindexed:
            indexed_ids = get_preindexed_collection_ids(timeout=30)

            keep = []
            for i in range(len(ds)):
                col_id = f"fr_{hashlib.md5(ds[i]['question'].encode()).hexdigest()[:10]}"
                if col_id in indexed_ids:
                    keep.append(i)
            ds = ds.select(keep)
            print(
                f"FRAMES stage {stage}: {len(keep)} pre-indexed questions "
                f"(of {len(stage_indices)} stage questions)"
            )

        if n_questions is not None and n_questions < len(ds):
            ds = ds.select(range(n_questions))

        rubric = vf.Rubric()
        rubric.add_reward_func(reward_answer_found, weight=1.0)

        turns = max_turns if max_turns is not None else {1: 4, 2: 6, 3: 6, 4: 8}[stage]

        super().__init__(
            tools=STAGE_TOOLS[stage],
            max_turns=turns,
            dataset=ds,
            eval_dataset=ds.select(range(min(50, len(ds)))),
            system_prompt=PROMPTS[stage],
            rubric=rubric,
            env_id=kwargs.pop("env_id", "curriculum"),
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


def load_environment(env_id: str = "curriculum", **kwargs):
    return CurriculumFramesEnv(env_id=env_id, **kwargs)
