"""Tests for ranked-document output parsing and normalization."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "frames_search"))

from retrieval_output import parse_retrieval_output


def test_parse_fenced_json():
    text = '''Here are the relevant documents:

```json
[
  {"doc_id": "d001", "rank": 1, "justification": "Contains the answer.", "supporting_chunk_ids": ["c012", "c034"]},
  {"doc_id": "d003", "rank": 2, "justification": "Supporting evidence."}
]
```'''
    result = parse_retrieval_output(text)
    assert not result.is_empty
    assert len(result.documents) == 2
    assert result.doc_ids == ["d001", "d003"]
    assert result.documents[0].rank == 1
    assert result.documents[0].justification == "Contains the answer."
    assert result.documents[0].supporting_chunk_ids == ["c012", "c034"]
    assert result.documents[1].supporting_chunk_ids == []


def test_parse_bare_json():
    text = '[{"doc_id": "d005", "rank": 1, "justification": "Direct match."}]'
    result = parse_retrieval_output(text)
    assert not result.is_empty
    assert result.doc_ids == ["d005"]


def test_malformed_output_returns_empty():
    result = parse_retrieval_output("I think the answer is 42.")
    assert result.is_empty
    assert result.parse_error


def test_empty_output_returns_empty():
    result = parse_retrieval_output("")
    assert result.is_empty
    assert result.parse_error == "empty output"


def test_json_without_doc_id_returns_empty():
    text = '[{"rank": 1, "justification": "No doc_id field."}]'
    result = parse_retrieval_output(text)
    assert result.is_empty
    assert "no valid documents" in result.parse_error


def test_max_five_documents():
    docs = [{"doc_id": f"d{i:03d}", "rank": i} for i in range(1, 10)]
    import json
    text = json.dumps(docs)
    result = parse_retrieval_output(text)
    assert len(result.documents) == 5


def test_auto_rank_assignment():
    text = '[{"doc_id": "d001"}, {"doc_id": "d002"}]'
    result = parse_retrieval_output(text)
    assert result.documents[0].rank == 1
    assert result.documents[1].rank == 2


def test_invalid_json_returns_error():
    text = '```json\n[{"doc_id": "d001" INVALID}\n```'
    result = parse_retrieval_output(text)
    assert result.is_empty
    assert result.parse_error  # regex or JSON error depending on malformation


def test_non_array_json_returns_error():
    text = '{"doc_id": "d001"}'
    result = parse_retrieval_output(text)
    assert result.is_empty


def test_empty_array():
    text = "[]"
    result = parse_retrieval_output(text)
    assert result.is_empty
