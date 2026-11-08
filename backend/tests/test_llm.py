from types import SimpleNamespace as NS

import httpx
import openai
import pytest
from pydantic import BaseModel

from backend import llm as llm_mod
from backend.llm import DeepSeekLLM, LLMError, LLMTimeout, LLMValidationError


class Out(BaseModel):
    answer: int


def reply(content, prompt=10, completion=5):
    message = NS(content=content, tool_calls=None, model_dump=lambda **_: {"role": "assistant", "content": content})
    return NS(choices=[NS(message=message)], usage=NS(prompt_tokens=prompt, completion_tokens=completion))


class FakeClient:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []
        self.chat = NS(completions=NS(create=self._create))

    async def _create(self, **kw):
        self.calls.append(kw)
        r = self.responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    async def _sleep(_):
        return None

    monkeypatch.setattr(llm_mod.asyncio, "sleep", _sleep)


REQ = httpx.Request("POST", "https://api.deepseek.com/chat/completions")


async def test_chat_tracks_usage():
    llm = DeepSeekLLM(client=FakeClient(reply("OK")))
    assert await llm.chat([{"role": "user", "content": "hi"}]) == "OK"
    assert llm.usage.total_tokens == 15 and llm.usage.calls == 1


async def test_chat_json_valid_and_fenced():
    llm = DeepSeekLLM(client=FakeClient(reply('```json\n{"answer": 4}\n```')))
    assert (await llm.chat_json([], Out)).answer == 4


async def test_chat_json_retries_once_then_succeeds():
    client = FakeClient(reply("not json"), reply('{"answer": 7}'))
    llm = DeepSeekLLM(client=client)
    assert (await llm.chat_json([], Out)).answer == 7
    assert "invalid" in client.calls[1]["messages"][-1]["content"]
    assert llm.usage.calls == 2


async def test_chat_json_gives_up_after_one_retry():
    client = FakeClient(reply("nope"), reply('{"answer": "x"}'), reply('{"answer": 1}'))
    with pytest.raises(LLMValidationError):
        await DeepSeekLLM(client=client).chat_json([], Out)
    assert len(client.calls) == 2


async def test_timeout_retries_with_backoff_then_raises():
    client = FakeClient(*[openai.APITimeoutError(request=REQ) for _ in range(3)])
    with pytest.raises(LLMTimeout):
        await DeepSeekLLM(client=client).chat([])
    assert len(client.calls) == 3


async def test_timeout_recovers():
    client = FakeClient(openai.APITimeoutError(request=REQ), reply("OK"))
    assert await DeepSeekLLM(client=client).chat([]) == "OK"


async def test_auth_error_is_not_retried():
    err = openai.AuthenticationError("bad key", response=httpx.Response(401, request=REQ), body=None)
    client = FakeClient(err, reply("OK"))
    with pytest.raises(LLMError):
        await DeepSeekLLM(client=client).chat([])
    assert len(client.calls) == 1
