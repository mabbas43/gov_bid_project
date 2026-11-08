"""DeepSeek wrapper (OpenAI SDK). chat(), chat_json(schema), tool calls, usage tracking, backoff."""
from __future__ import annotations

import asyncio
import json
import logging
import random
import re
from dataclasses import dataclass, field
from typing import Any, Optional, Protocol, Type, TypeVar

import openai
from openai import AsyncOpenAI
from pydantic import BaseModel, ValidationError

from backend.config import get_settings

log = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)

RETRYABLE = (
    openai.APITimeoutError,
    openai.APIConnectionError,
    openai.RateLimitError,
    openai.InternalServerError,
)


class LLMError(RuntimeError):
    """The model could not be reached after retries, or auth/config failed."""


class LLMTimeout(LLMError):
    """Every attempt timed out."""


class LLMValidationError(LLMError):
    """The model returned invalid JSON twice."""


@dataclass
class Usage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    calls: int = 0

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens

    def add(self, prompt: int, completion: int) -> None:
        self.prompt_tokens += prompt
        self.completion_tokens += completion
        self.calls += 1

    def cost_usd(self) -> float:
        s = get_settings()
        return (
            self.prompt_tokens * s.deepseek_input_usd_per_m
            + self.completion_tokens * s.deepseek_output_usd_per_m
        ) / 1_000_000


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class ChatResponse:
    content: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    prompt_tokens: int = 0
    completion_tokens: int = 0
    raw_assistant_message: dict[str, Any] = field(default_factory=dict)


class LLM(Protocol):
    """Shared by DeepSeekLLM and the offline DemoLLM."""

    usage: Usage

    async def chat(self, messages: list[dict], **kw: Any) -> str: ...

    async def chat_json(self, messages: list[dict], schema: Type[T], **kw: Any) -> T: ...

    async def chat_tools(self, messages: list[dict], tools: list[dict], **kw: Any) -> ChatResponse: ...


def _strip_fences(text: str) -> str:
    text = text.strip()
    m = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, re.S)
    return m.group(1) if m else text


class DeepSeekLLM:
    def __init__(self, client: Optional[Any] = None, model: Optional[str] = None):
        s = get_settings()
        self.model = model or s.deepseek_model
        self.max_retries = s.llm_max_retries
        self.usage = Usage()
        if client is None and not s.deepseek_api_key:
            raise LLMError("DEEPSEEK_API_KEY is not set")
        self.client = client or AsyncOpenAI(
            api_key=s.deepseek_api_key,
            base_url=s.deepseek_base_url,
            timeout=s.llm_timeout_s,
            max_retries=0,  # we run our own backoff below
        )

    async def _complete(self, messages: list[dict], **kw: Any):
        last: Optional[Exception] = None
        for attempt in range(self.max_retries + 1):
            try:
                resp = await self.client.chat.completions.create(
                    model=self.model, messages=messages, **kw
                )
                if resp.usage:
                    self.usage.add(resp.usage.prompt_tokens, resp.usage.completion_tokens)
                return resp
            except RETRYABLE as exc:
                last = exc
                if attempt < self.max_retries:
                    delay = 2**attempt + random.random()
                    log.warning("DeepSeek %s; retry %s in %.1fs", type(exc).__name__, attempt + 1, delay)
                    await asyncio.sleep(delay)
            except openai.OpenAIError as exc:  # auth, bad request: retrying will not help
                raise LLMError(f"DeepSeek error: {exc}") from exc
        if isinstance(last, openai.APITimeoutError):
            raise LLMTimeout(f"DeepSeek timed out after {self.max_retries + 1} attempts") from last
        raise LLMError(f"DeepSeek failed after {self.max_retries + 1} attempts: {last}") from last

    async def chat(self, messages: list[dict], **kw: Any) -> str:
        resp = await self._complete(messages, **kw)
        return resp.choices[0].message.content or ""

    async def chat_json(self, messages: list[dict], schema: Type[T], **kw: Any) -> T:
        shape = json.dumps(schema.model_json_schema())
        msgs = [
            *messages,
            {
                "role": "system",
                "content": f"Respond with one JSON object only, matching this JSON schema:\n{shape}",
            },
        ]
        error = ""
        for attempt in range(2):  # 1 retry on invalid JSON
            resp = await self._complete(msgs, response_format={"type": "json_object"}, **kw)
            content = resp.choices[0].message.content or ""
            try:
                return schema.model_validate_json(_strip_fences(content))
            except ValidationError as exc:
                error = str(exc)
                log.warning("Invalid JSON from model (attempt %s): %s", attempt + 1, error[:300])
                msgs = [
                    *msgs,
                    {"role": "assistant", "content": content},
                    {
                        "role": "user",
                        "content": f"That was invalid: {error[:1000]}\nReturn corrected JSON only.",
                    },
                ]
        raise LLMValidationError(f"Invalid JSON after retry: {error[:500]}")

    async def chat_tools(self, messages: list[dict], tools: list[dict], **kw: Any) -> ChatResponse:
        resp = await self._complete(messages, tools=tools, tool_choice="auto", **kw)
        msg = resp.choices[0].message
        calls: list[ToolCall] = []
        for tc in msg.tool_calls or []:
            try:
                args = json.loads(tc.function.arguments or "{}")
                if not isinstance(args, dict):
                    args = {}
            except json.JSONDecodeError:
                # Surfaced to the model as a tool error by the orchestrator.
                args = {"__invalid_json__": tc.function.arguments}
            calls.append(ToolCall(id=tc.id, name=tc.function.name, arguments=args))
        return ChatResponse(
            content=msg.content or "",
            tool_calls=calls,
            prompt_tokens=resp.usage.prompt_tokens if resp.usage else 0,
            completion_tokens=resp.usage.completion_tokens if resp.usage else 0,
            raw_assistant_message=msg.model_dump(exclude_none=True),
        )
