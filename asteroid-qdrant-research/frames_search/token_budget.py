"""Token budget management for the retrieval-subagent harness.

Enforces context window limits with soft and hard thresholds:
- Below soft: normal operation
- Above soft: inject token-usage state and prune-or-conclude guidance
- Above hard: reject all tools except prune_chunks
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TokenBudget:
    total: int = 32_768
    reserve: int = 2_048
    soft_pct: float = 0.50
    hard_pct: float = 0.85

    @property
    def effective(self) -> int:
        return self.total - self.reserve

    @property
    def soft_threshold(self) -> int:
        return int(self.total * self.soft_pct)

    @property
    def hard_threshold(self) -> int:
        return int(self.total * self.hard_pct)

    def usage_state(self, current_tokens: int) -> str:
        """Return 'normal', 'soft', or 'hard' based on current usage."""
        if current_tokens >= self.hard_threshold:
            return "hard"
        if current_tokens >= self.soft_threshold:
            return "soft"
        return "normal"

    def should_inject_guidance(self, current_tokens: int) -> bool:
        return self.usage_state(current_tokens) in ("soft", "hard")

    def is_tool_allowed(self, tool_name: str, current_tokens: int) -> bool:
        """Above hard cutoff, only prune_chunks is allowed."""
        if self.usage_state(current_tokens) != "hard":
            return True
        return tool_name == "prune_chunks"

    def guidance_message(self, current_tokens: int) -> str:
        """Generate context-aware guidance for the model."""
        state = self.usage_state(current_tokens)
        pct = current_tokens / self.total * 100
        remaining = self.total - current_tokens

        if state == "hard":
            return (
                f"[TOKEN BUDGET: {current_tokens}/{self.total} ({pct:.0f}%) HARD LIMIT]\n"
                f"You have {remaining} tokens remaining. "
                "You MUST use prune_chunks now to free context, or return your final "
                "ranked document list immediately. No other tools are available."
            )
        if state == "soft":
            return (
                f"[TOKEN BUDGET: {current_tokens}/{self.total} ({pct:.0f}%)]\n"
                f"You have {remaining} tokens remaining. "
                "Consider pruning irrelevant documents with prune_chunks to free "
                "context, or conclude your search and return your ranked document list."
            )
        return ""

    def format_usage_header(self, current_tokens: int) -> str:
        """Short usage line appended to each turn above soft threshold."""
        if not self.should_inject_guidance(current_tokens):
            return ""
        pct = current_tokens / self.total * 100
        return f"[Tokens: {current_tokens}/{self.total} ({pct:.0f}%)]"
