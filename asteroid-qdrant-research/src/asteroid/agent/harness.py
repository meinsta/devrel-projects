"""Core agent harness: observe-reason-act loop with token budget."""

import json
import re
import time
from dataclasses import dataclass, field

from openai import OpenAI

from .context import ContextManager, Chunk
from .prompt import SYSTEM_PROMPT
from ..tools.search import QdrantSearchTools


@dataclass
class Turn:
    role: str
    content: str
    tool_calls: list[dict] = field(default_factory=list)
    tool_results: list[dict] = field(default_factory=list)
    tokens: int = 0
    latency: float = 0.0


@dataclass
class Trajectory:
    question: str
    turns: list[Turn] = field(default_factory=list)
    final_answer: str = ""
    total_tokens: int = 0
    total_latency: float = 0.0
    tool_call_count: int = 0


class AgentHarness:
    """Observe-reason-act loop for the Asteroid search agent.

    Works with any OpenAI-compatible LLM. The model calls tools,
    the harness executes them against Qdrant, and feeds results back.
    """

    def __init__(
        self,
        llm: OpenAI,
        tools: QdrantSearchTools,
        model: str = "PrimeIntellect/INTELLECT-3.1",
        max_turns: int = 8,
        max_tokens: int = 2048,
        temperature: float = 0.6,
        context: ContextManager | None = None,
        verbose: bool = True,
    ):
        self.llm = llm
        self.tools = tools
        self.model = model
        self.max_turns = max_turns
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.context = context or ContextManager()
        self.verbose = verbose

    def _log(self, msg: str) -> None:
        if self.verbose:
            print(msg)

    def _execute_tool(self, name: str, args: dict) -> str:
        """Dispatch a tool call to the appropriate method."""
        self.context.record_tool_call()

        if name == "search_corpus":
            result = self.tools.search_corpus(args["query"])
        elif name == "filter_search":
            filters = args.get("filters", {})
            if isinstance(filters, str):
                filters = json.loads(filters)
            result = self.tools.filter_search(args["query"], filters)
        elif name == "text_search":
            result = self.tools.text_search(args["phrase"])
        elif name == "read_document":
            result = self.tools.read_document(args["page_id"])
        elif name == "group_search":
            result = self.tools.group_search(args["query"], args["group_by"])
        elif name == "refine_search":
            pos = args.get("positive_ids", [])
            neg = args.get("negative_ids", [])
            result = self.tools.refine_search(pos, neg)
        elif name == "prune_chunks":
            chunk_ids = args.get("chunk_ids", [])
            self.context.remove_chunks(chunk_ids)
            result = self.tools.prune_chunks(chunk_ids)
        else:
            return f"Unknown tool: {name}"

        self._log(f"    {name}({json.dumps(args, ensure_ascii=False)[:120]})")
        self._log(f"    -> {result.metadata}")
        return result.content

    def _parse_xml_tool_call(self, content: str) -> tuple[str, dict] | None:
        """Parse INTELLECT-3.1 style XML tool calls from content."""
        match = re.search(r'<function=(\w+)>\s*(.*?)\s*</function>', content, re.DOTALL)
        if not match:
            return None

        func_name = match.group(1)
        params_str = match.group(2)
        args = {}

        for pm in re.finditer(r'<parameter=(\w+)>\s*(.*?)\s*</parameter>', params_str, re.DOTALL):
            value = pm.group(2).strip()
            # Try to parse as JSON for complex types
            try:
                args[pm.group(1)] = json.loads(value)
            except (json.JSONDecodeError, ValueError):
                args[pm.group(1)] = value

        return func_name, args

    def _strip_thinking(self, content: str) -> str:
        """Remove <think>...</think> blocks from model output."""
        if "</think>" in content:
            return content.split("</think>")[-1].strip()
        return content.strip()

    def run(self, question: str) -> Trajectory:
        """Run the agent loop on a question. Returns the full trajectory."""
        trajectory = Trajectory(question=question)

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": question},
        ]

        tool_schemas = self.tools.get_tool_schemas()

        self._log(f"\nQuestion: {question}")
        self._log(f"{self.context.status_line()}\n")

        for turn_idx in range(self.max_turns):
            self.context.record_turn()
            self._log(f"--- Turn {turn_idx + 1} ---")

            # Force answer on last turn
            if turn_idx == self.max_turns - 1:
                messages.append({"role": "user", "content": "You have reached the search limit. Answer the question now with whatever information you have found."})
                tool_schemas_for_turn = []  # no tools on last turn
            else:
                tool_schemas_for_turn = tool_schemas

            t0 = time.perf_counter()
            create_kwargs = {
                "model": self.model,
                "messages": messages,
                "temperature": self.temperature,
                "max_tokens": self.max_tokens,
            }
            if tool_schemas_for_turn:
                create_kwargs["tools"] = tool_schemas_for_turn
                create_kwargs["tool_choice"] = "auto"

            response = self.llm.chat.completions.create(**create_kwargs)
            latency = time.perf_counter() - t0

            choice = response.choices[0]
            content = choice.message.content or ""
            tokens = response.usage.completion_tokens if response.usage else 0

            turn = Turn(
                role="assistant",
                content=content,
                tokens=tokens,
                latency=latency,
            )

            trajectory.total_tokens += response.usage.total_tokens if response.usage else 0
            trajectory.total_latency += latency

            self._log(f"  ({latency:.1f}s, {tokens} tokens)")

            # Case 1: Structured tool calls (OpenAI format)
            if choice.finish_reason == "tool_calls" and choice.message.tool_calls:
                messages.append(choice.message)
                for tc in choice.message.tool_calls:
                    args = json.loads(tc.function.arguments)
                    turn.tool_calls.append({"name": tc.function.name, "args": args})
                    result = self._execute_tool(tc.function.name, args)
                    turn.tool_results.append({"name": tc.function.name, "result": result[:500]})
                    messages.append({"role": "tool", "tool_call_id": tc.id, "content": result})
                    trajectory.tool_call_count += 1

            # Case 2: XML-style tool calls (INTELLECT-3.1)
            elif "<function=" in content:
                parsed = self._parse_xml_tool_call(content)
                if parsed:
                    func_name, args = parsed
                    turn.tool_calls.append({"name": func_name, "args": args})
                    result = self._execute_tool(func_name, args)
                    turn.tool_results.append({"name": func_name, "result": result[:500]})
                    messages.append({"role": "assistant", "content": content})
                    messages.append({"role": "user", "content": f"Tool results:\n\n{result}\n\nContinue searching if needed, or answer the question."})
                    trajectory.tool_call_count += 1
                else:
                    answer = self._strip_thinking(content)
                    trajectory.final_answer = answer
                    turn.content = answer
                    trajectory.turns.append(turn)
                    self._log(f"\n  Answer: {answer[:300]}")
                    break

            # Case 3: Final answer (no tool call)
            else:
                answer = self._strip_thinking(content)
                trajectory.final_answer = answer
                turn.content = answer
                trajectory.turns.append(turn)
                self._log(f"\n  Answer: {answer[:300]}")
                break

            trajectory.turns.append(turn)
            self._log(f"  {self.context.status_line()}")

        if not trajectory.final_answer:
            trajectory.final_answer = "[Agent did not produce a final answer within turn limit]"

        self._log(f"\n=== Summary ===")
        self._log(f"Turns: {len(trajectory.turns)}, Tool calls: {trajectory.tool_call_count}")
        self._log(f"Total tokens: {trajectory.total_tokens:,}, Total latency: {trajectory.total_latency:.1f}s")

        return trajectory
