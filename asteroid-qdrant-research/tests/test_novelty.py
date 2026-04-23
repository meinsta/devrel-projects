"""Tests for novelty pressure (seen chunk exclusion)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "frames_search"))

from shared import FramesQdrantMixin, make_chunk_id


class MockPoint:
    def __init__(self, point_id: int, title: str = "", text: str = ""):
        self.id = point_id
        self.score = 1.0
        self.payload = {"title": title, "text": text}


class TestMixin(FramesQdrantMixin):
    def __init__(self):
        self._title_cache = {}
        self._doc_catalog_cache = {}

    def _get_qdrant(self):
        raise NotImplementedError

    def _embed(self, text):
        raise NotImplementedError


def test_make_chunk_id():
    assert make_chunk_id(0) == "c0000"
    assert make_chunk_id(12) == "c0012"
    assert make_chunk_id(9999) == "c9999"


def test_get_seen_chunk_ids_empty():
    mixin = TestMixin()
    assert mixin._get_seen_chunk_ids(None) == set()
    assert mixin._get_seen_chunk_ids({}) == set()
    assert mixin._get_seen_chunk_ids({"seen_chunk_ids": []}) == set()


def test_get_seen_chunk_ids():
    mixin = TestMixin()
    state = {"seen_chunk_ids": ["c0001", "c0002"]}
    assert mixin._get_seen_chunk_ids(state) == {"c0001", "c0002"}


def test_record_seen_chunks():
    mixin = TestMixin()
    state = {"seen_chunk_ids": []}
    points = [MockPoint(1), MockPoint(5), MockPoint(10)]
    mixin._record_seen_chunks(state, points)
    assert set(state["seen_chunk_ids"]) == {"c0001", "c0005", "c0010"}


def test_record_seen_chunks_accumulates():
    mixin = TestMixin()
    state = {"seen_chunk_ids": ["c0001"]}
    points = [MockPoint(2)]
    mixin._record_seen_chunks(state, points)
    assert set(state["seen_chunk_ids"]) == {"c0001", "c0002"}


def test_filter_seen_chunks():
    mixin = TestMixin()
    points = [MockPoint(1), MockPoint(2), MockPoint(3)]
    seen = {"c0001", "c0003"}
    filtered = mixin._filter_seen_chunks(points, seen)
    assert len(filtered) == 1
    assert filtered[0].id == 2


def test_filter_seen_chunks_empty_seen():
    mixin = TestMixin()
    points = [MockPoint(1), MockPoint(2)]
    filtered = mixin._filter_seen_chunks(points, set())
    assert len(filtered) == 2


def test_record_to_none_state():
    mixin = TestMixin()
    # Should not raise
    mixin._record_seen_chunks(None, [MockPoint(1)])
