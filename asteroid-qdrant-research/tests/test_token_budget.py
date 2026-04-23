"""Tests for token budget management."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "frames_search"))

from token_budget import TokenBudget


def test_default_thresholds():
    budget = TokenBudget()
    assert budget.total == 32_768
    assert budget.reserve == 2_048
    assert budget.soft_threshold == 16_384  # 50%
    assert budget.hard_threshold == 27_852  # 85%
    assert budget.effective == 30_720


def test_normal_state():
    budget = TokenBudget()
    assert budget.usage_state(1000) == "normal"
    assert not budget.should_inject_guidance(1000)


def test_soft_state():
    budget = TokenBudget()
    assert budget.usage_state(20_000) == "soft"
    assert budget.should_inject_guidance(20_000)


def test_hard_state():
    budget = TokenBudget()
    assert budget.usage_state(30_000) == "hard"
    assert budget.should_inject_guidance(30_000)


def test_tool_allowed_normal():
    budget = TokenBudget()
    assert budget.is_tool_allowed("search_corpus", 1000)
    assert budget.is_tool_allowed("read_document", 1000)
    assert budget.is_tool_allowed("text_search", 1000)
    assert budget.is_tool_allowed("prune_chunks", 1000)


def test_tool_blocked_hard():
    budget = TokenBudget()
    assert not budget.is_tool_allowed("search_corpus", 30_000)
    assert not budget.is_tool_allowed("read_document", 30_000)
    assert not budget.is_tool_allowed("text_search", 30_000)
    assert budget.is_tool_allowed("prune_chunks", 30_000)  # only prune allowed


def test_guidance_message_normal():
    budget = TokenBudget()
    assert budget.guidance_message(1000) == ""


def test_guidance_message_soft():
    budget = TokenBudget()
    msg = budget.guidance_message(20_000)
    assert "TOKEN BUDGET" in msg
    assert "prune" in msg.lower()


def test_guidance_message_hard():
    budget = TokenBudget()
    msg = budget.guidance_message(30_000)
    assert "HARD LIMIT" in msg
    assert "prune_chunks" in msg


def test_usage_header_normal():
    budget = TokenBudget()
    assert budget.format_usage_header(1000) == ""


def test_usage_header_soft():
    budget = TokenBudget()
    header = budget.format_usage_header(20_000)
    assert "Tokens:" in header


def test_custom_budget():
    budget = TokenBudget(total=16_384, reserve=1_024, soft_pct=0.6, hard_pct=0.9)
    assert budget.soft_threshold == 9_830  # 60% of 16384
    assert budget.hard_threshold == 14_745  # 90% of 16384
    assert budget.effective == 15_360
