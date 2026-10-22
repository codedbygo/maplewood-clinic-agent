"""LLM adapters: the Anthropic path with a stub client, and the OpenRouter error paths."""

import asyncio
from types import SimpleNamespace

import httpx2
import pytest

from agent.llm import AnthropicLLM, LLMRefusal, cost_usd, to_openai_messages
from agent.schema import Triage
from tests.test_openrouter import TRIAGE_JSON, chat, make


def usage(**kw):
    base = dict(input_tokens=100, output_tokens=10, cache_read_input_tokens=50, cache_creation_input_tokens=0)
    return SimpleNamespace(**{**base, **kw})


class StubMessages:
    def __init__(self, stop="end_turn"):
        self.stop, self.kwargs = stop, []

    async def parse(self, **kw):
        self.kwargs.append(kw)
        return SimpleNamespace(usage=usage(), stop_reason=self.stop, model=kw["model"], parsed_output=Triage(**TRIAGE_JSON))

    async def create(self, **kw):
        self.kwargs.append(kw)
        return SimpleNamespace(usage=usage(), stop_reason=self.stop, model=kw["model"], content=[])


def anthropic_llm(model, stop="end_turn"):
    llm = AnthropicLLM(model=model)
    stub = StubMessages(stop)
    llm.client = SimpleNamespace(beta=SimpleNamespace(messages=stub))
    return llm, stub


def test_anthropic_triage_and_step_record_usage_and_use_fallbacks():
    llm, stub = anthropic_llm("claude-sonnet-5-5")
    assert asyncio.run(llm.triage("S", "U")).urgency == "routine"
    asyncio.run(llm.step("S", [{"role": "user", "content": "x"}], []))
    assert stub.kwargs[0]["fallbacks"] == "default" and stub.kwargs[0]["output_config"]["effort"] == "low"
    assert "temperature" not in stub.kwargs[1]
    assert [c["kind"] for c in llm.calls] == ["triage", "step"] and llm.calls[0]["cache_read_input_tokens"] == 50


def test_anthropic_model_without_server_fallback_sends_no_fallbacks():
    llm, stub = anthropic_llm("claude-haiku-5-5")
    asyncio.run(llm.step("S", [{"role": "user", "content": "x"}], []))
    assert "fallbacks" not in stub.kwargs[0]


def test_anthropic_refusal_raises():
    llm, _ = anthropic_llm("claude-sonnet-5-5", stop="refusal")
    with pytest.raises(LLMRefusal):
        asyncio.run(llm.step("S", [{"role": "user", "content": "x"}], []))


def test_cost():
    assert cost_usd("nvidia/x:free", {"input_tokens": 10**6}) == 0.0
    assert cost_usd("anything", {"cost_usd": 0.25}) == 0.25
    assert cost_usd("claude-sonnet-5-5", {"input_tokens": 10**6, "output_tokens": 10**6}) == pytest.approx(12.0)


def test_translation_of_list_content_with_text_blocks():
    out = to_openai_messages("S", [{"role": "user", "content": [{"type": "text", "text": "a"}, {"type": "text", "text": "b"}]},
                                   {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "t", "content": [{"x": 1}]}]}])
    assert out[1] == {"role": "user", "content": "a\nb"}
    assert out[2] == {"role": "tool", "tool_call_id": "t", "content": '[{"x": 1}]'}


def test_transport_error_retries_then_gives_up():
    def boom(request):
        raise httpx2.ConnectError("down")

    with pytest.raises(RuntimeError, match="unreachable"):
        asyncio.run(make(boom, max_retries=1).step("S", [{"role": "user", "content": "x"}], []))


def test_non_json_5xx_retries_then_reports_status():
    with pytest.raises(RuntimeError, match="502 after 2 attempts"):
        asyncio.run(make(lambda r: httpx2.Response(502, text="<html>bad gateway</html>"), max_retries=1)
                    .step("S", [{"role": "user", "content": "x"}], []))


def test_client_error_is_not_retried():
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        return httpx2.Response(400, json={"error": {"message": "bad tool schema"}})

    with pytest.raises(RuntimeError, match="400: bad tool schema"):
        asyncio.run(make(handler).step("S", [{"role": "user", "content": "x"}], []))
    assert calls["n"] == 1


def test_error_payload_in_200_retries_then_succeeds():
    answers = iter([httpx2.Response(200, json={"error": {"message": "upstream hiccup"}}), httpx2.Response(200, json=chat(content="ok"))])
    assert asyncio.run(make(lambda r: next(answers)).step("S", [{"role": "user", "content": "x"}], [])).content[0].text == "ok"


def test_usage_cost_is_recorded_when_provider_reports_it():
    body = chat(content="ok")
    body["usage"]["cost"] = 0.0012
    llm = make(lambda r: httpx2.Response(200, json=body), fallbacks=[])
    asyncio.run(llm.step("S", [{"role": "user", "content": "x"}], []))
    assert llm.calls[-1]["cost_usd"] == 0.0012
