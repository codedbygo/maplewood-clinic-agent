"""OpenRouter adapter tests: no network, a mock transport answers every request."""

import asyncio
import json
from types import SimpleNamespace

import httpx2
import pytest

from agent.llm import LLM, LLMQuotaError, OpenRouterLLM, to_openai_messages, to_openai_tools

TRIAGE_JSON = {
    "intents": ["refill"],
    "urgency": "routine",
    "emergency": False,
    "clinical_concern": False,
    "rationale": "Routine refill.",
    "language": "en",
    "suspicious_instruction": False,
}


def chat(content=None, tool_calls=None, model="nvidia/nemotron-3-ultra-550b-a55b:free"):
    msg = {"role": "assistant", "content": content}
    if tool_calls:
        msg["tool_calls"] = tool_calls
    return {
        "model": model,
        "choices": [{"message": msg, "finish_reason": "tool_calls" if tool_calls else "stop"}],
        "usage": {"prompt_tokens": 100, "completion_tokens": 20},
    }


def make(handler, **kw):
    llm = OpenRouterLLM(model="nvidia/nemotron-3-ultra-550b-a55b:free", api_key="test", **kw)
    llm.http = httpx2.AsyncClient(transport=httpx2.MockTransport(handler), base_url="https://openrouter.test/api/v1")
    llm.sleep = lambda s: asyncio.sleep(0)
    return llm


def test_translates_anthropic_shaped_history_to_openai():
    history = [
        {"role": "user", "content": "hello"},
        {
            "role": "assistant",
            "content": [
                SimpleNamespace(type="text", text="checking"),
                SimpleNamespace(type="tool_use", id="c1", name="get_clinic_info", input={"topic": "hours"}),
            ],
        },
        {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "c1", "content": '{"ok": true}'}]},
        {"role": "user", "content": "Call submit_result to finish this message."},
    ]
    out = to_openai_messages("SYSTEM", history)
    assert out[0] == {"role": "system", "content": "SYSTEM"}
    assert out[1] == {"role": "user", "content": "hello"}
    assert out[2]["role"] == "assistant" and out[2]["content"] == "checking"
    assert out[2]["tool_calls"][0] == {
        "id": "c1",
        "type": "function",
        "function": {"name": "get_clinic_info", "arguments": '{"topic": "hours"}'},
    }
    assert out[3] == {"role": "tool", "tool_call_id": "c1", "content": '{"ok": true}'}
    assert out[4] == {"role": "user", "content": "Call submit_result to finish this message."}


def test_translates_tools():
    tools = [{"name": "resolve_date", "description": "d", "input_schema": {"type": "object", "properties": {}}}]
    assert to_openai_tools(tools) == [
        {"type": "function", "function": {"name": "resolve_date", "description": "d", "parameters": {"type": "object", "properties": {}}}}
    ]


def test_step_parses_tool_calls_into_blocks_and_sends_fallbacks():
    seen = {}

    def handler(request):
        seen.update(json.loads(request.content))
        return httpx2.Response(
            200,
            json=chat(
                content="ok",
                tool_calls=[
                    {"id": "t1", "type": "function", "function": {"name": "resolve_date", "arguments": '{"expression": "tomorrow"}'}}
                ],
            ),
        )

    llm = make(handler, fallbacks=["minimax/minimax-m3.1-flash:free"])
    resp = asyncio.run(llm.step("S", [{"role": "user", "content": "hi"}], []))
    uses = [b for b in resp.content if b.type == "tool_use"]
    assert uses[0].name == "resolve_date" and uses[0].input == {"expression": "tomorrow"} and uses[0].id == "t1"
    assert resp.stop_reason == "tool_use"
    assert seen["models"] == ["nvidia/nemotron-3-ultra-550b-a55b:free", "minimax/minimax-m3.1-flash:free"]
    assert seen["temperature"] == 0
    assert llm.calls[-1]["input_tokens"] == 100 and llm.calls[-1]["model"].startswith("nvidia/")


def test_bad_tool_arguments_become_empty_input_not_a_crash():
    def handler(request):
        return httpx2.Response(
            200, json=chat(tool_calls=[{"id": "t1", "type": "function", "function": {"name": "resolve_date", "arguments": "{not json"}}])
        )

    resp = asyncio.run(make(handler).step("S", [{"role": "user", "content": "hi"}], []))
    assert resp.content[0].input == {}


def test_text_only_answer_is_end_turn():
    resp = asyncio.run(make(lambda r: httpx2.Response(200, json=chat(content="done"))).step("S", [{"role": "user", "content": "x"}], []))
    assert resp.stop_reason == "end_turn" and resp.content[0].text == "done"


def test_triage_extracts_json_from_prose_and_fences():
    body = "Here you go:\n```json\n" + json.dumps(TRIAGE_JSON) + "\n```"
    t = asyncio.run(make(lambda r: httpx2.Response(200, json=chat(content=body))).triage("S", "U"))
    assert t.urgency == "routine" and t.intents == ["refill"]


def test_triage_repairs_once_after_invalid_json():
    answers = iter([chat(content='{"urgency": "whenever"}'), chat(content=json.dumps(TRIAGE_JSON))])
    llm = make(lambda r: httpx2.Response(200, json=next(answers)))
    assert asyncio.run(llm.triage("S", "U")).urgency == "routine"
    assert [c["kind"] for c in llm.calls] == ["triage", "triage_repair"]


def test_triage_gives_up_after_one_repair():
    llm = make(lambda r: httpx2.Response(200, json=chat(content="no json here")))
    with pytest.raises(ValueError):
        asyncio.run(llm.triage("S", "U"))


def test_retries_rate_limit_then_succeeds():
    answers = iter(
        [
            httpx2.Response(429, json={"error": {"message": "Rate limit exceeded: free-models-per-min"}}, headers={"Retry-After": "1"}),
            httpx2.Response(503, json={"error": {"message": "busy"}}),
            httpx2.Response(200, json=chat(content="ok")),
        ]
    )
    resp = asyncio.run(make(lambda r: next(answers)).step("S", [{"role": "user", "content": "x"}], []))
    assert resp.content[0].text == "ok"


def test_daily_quota_raises_quota_error_without_retrying():
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        return httpx2.Response(429, json={"error": {"message": "Rate limit exceeded: free-models-per-day. Add credits to unlock more."}})

    with pytest.raises(LLMQuotaError):
        asyncio.run(make(handler).step("S", [{"role": "user", "content": "x"}], []))
    assert calls["n"] == 1


def test_error_payload_inside_200_is_an_error():
    llm = make(lambda r: httpx2.Response(200, json={"error": {"message": "No endpoints found", "code": 404}}), max_retries=0)
    with pytest.raises(RuntimeError, match="No endpoints found"):
        asyncio.run(llm.step("S", [{"role": "user", "content": "x"}], []))


def test_factory_picks_provider(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openrouter")
    monkeypatch.setenv("OPENROUTER_API_KEY", "k")
    assert isinstance(LLM(), OpenRouterLLM)
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    assert not isinstance(LLM(), OpenRouterLLM)
