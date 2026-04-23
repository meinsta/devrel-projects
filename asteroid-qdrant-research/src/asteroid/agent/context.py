"""Token budget and context window management."""

from dataclasses import dataclass, field


@dataclass
class Chunk:
    chunk_id: str
    title: str
    text: str
    score: float
    token_count: int


@dataclass
class ContextManager:
    """Tracks active chunks in the agent's working context.

    Three tiers:
    - Below soft threshold: search freely
    - Between soft and hard: encourage pruning, truncate tool results
    - Above hard: block all tools except prune, force answer
    """

    max_tokens: int = 32768
    soft_threshold: float = 0.75
    hard_threshold: float = 0.90
    reserve_tokens: int = 2048

    active_chunks: dict[str, Chunk] = field(default_factory=dict)
    total_tokens_used: int = 0
    turns: int = 0
    tool_calls: int = 0

    @property
    def tokens_available(self) -> int:
        return self.max_tokens - self.total_tokens_used - self.reserve_tokens

    @property
    def utilization(self) -> float:
        if self.max_tokens == 0:
            return 0.0
        return self.total_tokens_used / self.max_tokens

    @property
    def should_prune(self) -> bool:
        return self.utilization >= self.soft_threshold

    @property
    def must_answer(self) -> bool:
        return self.utilization >= self.hard_threshold

    def add_chunk(self, chunk: Chunk) -> None:
        if chunk.chunk_id in self.active_chunks:
            return
        self.active_chunks[chunk.chunk_id] = chunk
        self.total_tokens_used += chunk.token_count

    def remove_chunks(self, chunk_ids: list[str]) -> int:
        freed = 0
        for cid in chunk_ids:
            if cid in self.active_chunks:
                freed += self.active_chunks[cid].token_count
                del self.active_chunks[cid]
        self.total_tokens_used -= freed
        return freed

    def status_line(self) -> str:
        pct = self.utilization * 100
        n_chunks = len(self.active_chunks)
        warning = ""
        if self.must_answer:
            warning = " [MUST ANSWER]"
        elif self.should_prune:
            warning = " [consider pruning]"
        return f"Context: {self.total_tokens_used:,}/{self.max_tokens:,} tokens ({pct:.0f}%), {n_chunks} chunks, {self.tool_calls} tool calls{warning}"

    def record_tool_call(self) -> None:
        self.tool_calls += 1

    def record_turn(self) -> None:
        self.turns += 1
