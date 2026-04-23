"""
LLM client wrapper
Supports both Anthropic (Claude) and OpenAI-compatible APIs.
Uses Anthropic by default when ANTHROPIC_API_KEY is set.
"""

import json
import os
import re
from typing import Optional, Dict, Any, List

from ..config import Config


class LLMClient:
    """LLM client supporting Anthropic Claude and OpenAI-compatible APIs."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
    ):
        self.api_key = api_key or Config.LLM_API_KEY
        self.base_url = base_url or Config.LLM_BASE_URL
        self.model = model or Config.LLM_MODEL_NAME

        # Detect provider from key prefix or base_url
        anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "")
        self._use_anthropic = bool(anthropic_key) or (
            self.api_key and self.api_key.startswith("sk-ant-")
        )

        if self._use_anthropic:
            import anthropic

            key = anthropic_key or self.api_key
            self.anthropic_client = anthropic.Anthropic(api_key=key)
            # Default to sonnet if model looks like an OpenAI model
            if self.model and not self.model.startswith("claude"):
                self.model = "claude-sonnet-4-20250514"
        else:
            from openai import OpenAI

            if not self.api_key:
                raise ValueError("LLM_API_KEY not configured")
            self.openai_client = OpenAI(
                api_key=self.api_key, base_url=self.base_url
            )

    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 4096,
        response_format: Optional[Dict] = None,
    ) -> str:
        """Send a chat request. Works with both Anthropic and OpenAI."""
        if self._use_anthropic:
            return self._chat_anthropic(messages, temperature, max_tokens, response_format)
        return self._chat_openai(messages, temperature, max_tokens, response_format)

    def _chat_anthropic(
        self,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: int,
        response_format: Optional[Dict],
    ) -> str:
        # Extract system message if present
        system_parts = []
        chat_messages = []
        for msg in messages:
            if msg["role"] == "system":
                system_parts.append(msg["content"])
            else:
                chat_messages.append({"role": msg["role"], "content": msg["content"]})

        system = "\n\n".join(system_parts) if system_parts else ""

        # If JSON mode requested, add instruction to system
        if response_format and response_format.get("type") == "json_object":
            system += "\n\nRespond with valid JSON only. No markdown fences, no commentary."

        # Ensure messages alternate user/assistant and start with user
        if not chat_messages or chat_messages[0]["role"] != "user":
            chat_messages.insert(0, {"role": "user", "content": "Please proceed."})

        # Merge consecutive messages of the same role
        merged = []
        for msg in chat_messages:
            if merged and merged[-1]["role"] == msg["role"]:
                merged[-1]["content"] += "\n\n" + msg["content"]
            else:
                merged.append(dict(msg))

        response = self.anthropic_client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system,
            messages=merged,
        )

        content = response.content[0].text if response.content else ""
        # Strip thinking tags
        content = re.sub(r"<think>[\s\S]*?</think>", "", content).strip()
        return content

    def _chat_openai(
        self,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: int,
        response_format: Optional[Dict],
    ) -> str:
        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if response_format:
            kwargs["response_format"] = response_format

        response = self.openai_client.chat.completions.create(**kwargs)
        content = response.choices[0].message.content
        content = re.sub(r"<think>[\s\S]*?</think>", "", content).strip()
        return content

    def chat_json(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> Dict[str, Any]:
        """Send a chat request and return parsed JSON."""
        response = self.chat(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format={"type": "json_object"},
        )
        cleaned = response.strip()
        cleaned = re.sub(r"^```(?:json)?\s*\n?", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\n?```\s*$", "", cleaned)
        cleaned = cleaned.strip()

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            raise ValueError(f"Invalid JSON from LLM: {cleaned[:200]}")
