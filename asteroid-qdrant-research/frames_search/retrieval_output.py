"""Ranked-document output contract for retrieval-subagent behavior.

The agent returns ranked documents only, never a final free-form answer.
Output is a machine-readable list of up to 5 documents with justifications.
Malformed output is scored as an empty document set.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field


@dataclass
class RetrievalDocument:
    doc_id: str
    rank: int
    justification: str = ""
    supporting_chunk_ids: list[str] = field(default_factory=list)


@dataclass
class RetrievalResult:
    documents: list[RetrievalDocument] = field(default_factory=list)
    raw_output: str = ""
    parse_error: str = ""

    @property
    def doc_ids(self) -> list[str]:
        return [d.doc_id for d in self.documents]

    @property
    def is_empty(self) -> bool:
        return len(self.documents) == 0


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

_JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*(\[.*?\])\s*```", re.DOTALL)
_BARE_JSON_RE = re.compile(r"(\[\s*\{.*?\}\s*\])", re.DOTALL)


def parse_retrieval_output(text: str) -> RetrievalResult:
    """Parse model output into a RetrievalResult.

    Accepts either a fenced JSON block or bare JSON array. Each element must
    have at least ``doc_id``. Malformed output yields an empty result with a
    parse_error message.
    """
    if not text or not text.strip():
        return RetrievalResult(raw_output=text, parse_error="empty output")

    json_str = _extract_json(text)
    if json_str is None:
        return RetrievalResult(raw_output=text, parse_error="no JSON array found in output")

    try:
        items = json.loads(json_str)
    except json.JSONDecodeError as exc:
        return RetrievalResult(raw_output=text, parse_error=f"JSON decode error: {exc}")

    if not isinstance(items, list):
        return RetrievalResult(raw_output=text, parse_error="top-level JSON is not an array")

    documents: list[RetrievalDocument] = []
    for i, item in enumerate(items[:5]):
        if not isinstance(item, dict):
            continue
        doc_id = item.get("doc_id")
        if not doc_id:
            continue
        documents.append(RetrievalDocument(
            doc_id=str(doc_id),
            rank=item.get("rank", i + 1),
            justification=str(item.get("justification", "")),
            supporting_chunk_ids=[
                str(c) for c in item.get("supporting_chunk_ids", [])
            ],
        ))

    if not documents:
        return RetrievalResult(
            raw_output=text,
            parse_error="JSON parsed but no valid documents with doc_id found",
        )

    return RetrievalResult(documents=documents, raw_output=text)


def _extract_json(text: str) -> str | None:
    """Pull the first JSON array from fenced block or bare text."""
    m = _JSON_BLOCK_RE.search(text)
    if m:
        return m.group(1)
    m = _BARE_JSON_RE.search(text)
    if m:
        return m.group(1)
    return None


# ---------------------------------------------------------------------------
# Output format prompt fragment
# ---------------------------------------------------------------------------

RETRIEVAL_OUTPUT_INSTRUCTIONS = """\
When you have finished searching, return your final answer as a JSON array \
of up to 5 documents, ranked by relevance. Use this exact format:

```json
[
  {
    "doc_id": "d001",
    "rank": 1,
    "justification": "One sentence explaining why this document answers the question.",
    "supporting_chunk_ids": ["c012", "c034"]
  }
]
```

Rules:
- Return ONLY the JSON array as your final message. No other text.
- Maximum 5 documents. Rank 1 is most relevant.
- doc_id must match IDs from your search results.
- supporting_chunk_ids are optional but encouraged.
- If you cannot find relevant documents, return an empty array: []
"""
