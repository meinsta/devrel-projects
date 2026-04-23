"""Base tool protocol and types."""

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class ToolResult:
    content: str
    token_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


class Tool(Protocol):
    """Protocol for agent tools. Each tool maps to a Qdrant capability."""

    @property
    def name(self) -> str: ...

    @property
    def description(self) -> str: ...

    @property
    def parameters(self) -> dict: ...

    def execute(self, **kwargs) -> ToolResult: ...

    def to_openai_schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }
