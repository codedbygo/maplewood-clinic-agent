"""LLM providers behind one interface: `triage(system, user) -> Triage` and `step(system, messages, tools)`.

The runner speaks the Anthropic message shape (content blocks, tool_use / tool_result). OpenRouterLLM
translates that to OpenAI-style chat completions and back, so the runner, guard and eval are provider-agnostic.

  LLM_PROVIDER=openrouter (default when OPENROUTER_API_KEY is set) or anthropic
  AGENT_MODEL, AGENT_FALLBACK_MODELS (comma separated, OpenRouter only), AGENT_EFFORT
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import anthropic
import httpx2
from pydantic import ValidationError

from agent.schema import Triage

ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


def load_dotenv(path: Path = ENV_FILE) -> None:
    """Minimal .env loader (no extra dependency). Existing environment variables win."""
    if path.exists():
        for line in path.read_text().splitlines():
            key, sep, value = line.partition("=")
            if sep and not key.strip().startswith("#") and value.strip():
                os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_dotenv()

DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-5-5"
DEFAULT_OPENROUTER_MODEL = "nvidia/nemotron-3-ultra-550b-a55b:free"
DEFAULT_OPENROUTER_FALLBACKS = ["minimax/minimax-m3.1-flash:free", "nvidia/nemotron-3-super-120b-a12b:free"]
DEFAULT_MODEL = DEFAULT_OPENROUTER_MODEL
# $ per million tokens: (input, output, cache read, cache write 5m). ":free" models cost nothing.
PRICES = {
    "claude-sonnet-5-5": (2.00, 10.00, 0.20, 2.50),
    "claude-haiku-5-5": (0.10, 0.50, 0.01, 0.125),
    "claude-opus-5-5": (4.00, 20.00, 0.20, 5.00),
}
FALLBACK_MODELS = {"claude-sonnet-5-5", "claude-opus-5-5"}


class LLMRefusal(Exception):
    pass


class LLMQuotaError(Exception):
    """The provider's daily quota is used up. Retrying will not help today."""


def cost_usd(model: str, usage: dict) -> float:
    if "cost_usd" in usage:
        return float(usage["cost_usd"] or 0.0)
    if model.endswith(":free"):
        return 0.0
    pin, pout, pread, pwrite = PRICES.get(model, PRICES[DEFAULT_ANTHROPIC_MODEL])
    return (
        usage.get("input_tokens", 0) * pin
        + usage.get("output_tokens", 0) * pout
        + usage.get("cache_read_input_tokens", 0) * pread
        + usage.get("cache_creation_input_tokens", 0) * pwrite
    ) / 1e6


def LLM(model: str | None = None, effort: str | None = None):
    provider = os.environ.get("LLM_PROVIDER") or (
        "anthropic" if os.environ.get("ANTHROPIC_API_KEY") and not os.environ.get("OPENROUTER_API_KEY") else "openrouter"
    )
    if provider == "anthropic":
        return AnthropicLLM(model=model, effort=effort)
    return OpenRouterLLM(model=model, effort=effort)


# ---------------------------------------------------------------------------
# Anthropic
# ---------------------------------------------------------------------------


def _usage(resp) -> dict:
    u = resp.usage
    return {k: getattr(u, k, 0) or 0 for k in ("input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")}


class AnthropicLLM:
    """Temperature is not set: Claude Sonnet 5.5 and Haiku 5.5 reject non-default sampling parameters."""

    provider = "anthropic"

    def __init__(self, model: str | None = None, effort: str | None = None):
        self.model = model or os.environ.get("AGENT_MODEL") or DEFAULT_ANTHROPIC_MODEL
        self.effort = effort or os.environ.get("AGENT_EFFORT", "medium")
        self.configured = bool(os.environ.get("ANTHROPIC_API_KEY"))
        self.client = anthropic.AsyncAnthropic(max_retries=4)
        self.calls: list[dict] = []

    def _extra(self) -> dict:
        kw = {"model": self.model, "output_config": {"effort": self.effort}, "cache_control": {"type": "ephemeral"}}
        if self.model in FALLBACK_MODELS:
            kw.update(betas=["server-side-fallback-2026-07-01"], fallbacks="default")
        else:
            kw["betas"] = []
        return kw

    def _record(self, kind: str, resp, started: float) -> dict:
        entry = {
            "kind": kind,
            "model": getattr(resp, "model", self.model),
            **_usage(resp),
            "latency_s": round(time.monotonic() - started, 2),
            "stop_reason": resp.stop_reason,
        }
        self.calls.append(entry)
        if resp.stop_reason == "refusal":
            raise LLMRefusal(str(getattr(resp, "stop_details", None)))
        return entry

    async def triage(self, system: str, user: str) -> Triage:
        started = time.monotonic()
        extra = self._extra()
        extra["output_config"] = {**extra["output_config"], "effort": "low"}
        resp = await self.client.beta.messages.parse(
            max_tokens=2000,
            system=system,
            messages=[{"role": "user", "content": user}],
            output_format=Triage,
            **extra,
        )
        self._record("triage", resp, started)
        if resp.parsed_output is None:
            raise ValueError("triage response did not match the schema")
        return resp.parsed_output

    async def step(self, system: str, messages: list, tools: list):
        started = time.monotonic()
        resp = await self.client.beta.messages.create(max_tokens=8000, system=system, messages=messages, tools=tools, **self._extra())
        self._record("step", resp, started)
        return resp


# ---------------------------------------------------------------------------
# OpenRouter (OpenAI-compatible chat completions)
# ---------------------------------------------------------------------------


def _get(block, key, default=None):
    return block.get(key, default) if isinstance(block, dict) else getattr(block, key, default)


def to_openai_tools(tools: list[dict]) -> list[dict]:
    return [
        {"type": "function", "function": {"name": t["name"], "description": t.get("description", ""), "parameters": t["input_schema"]}}
        for t in tools
    ]


def to_openai_messages(system: str, messages: list[dict]) -> list[dict]:
    """Translate the runner's Anthropic-shaped history into OpenAI chat messages."""
    out: list[dict] = [{"role": "system", "content": system}]
    for m in messages:
        content = m["content"]
        if isinstance(content, str):
            out.append({"role": m["role"], "content": content})
            continue
        if m["role"] == "assistant":
            text = "".join(_get(b, "text", "") or "" for b in content if _get(b, "type") == "text")
            calls = [
                {
                    "id": _get(b, "id"),
                    "type": "function",
                    "function": {"name": _get(b, "name"), "arguments": json.dumps(_get(b, "input") or {})},
                }
                for b in content
                if _get(b, "type") == "tool_use"
            ]
            msg: dict[str, Any] = {"role": "assistant", "content": text or None}
            if calls:
                msg["tool_calls"] = calls
            out.append(msg)
            continue
        texts = []
        for b in content:
            if _get(b, "type") == "tool_result":
                body = _get(b, "content", "")
                out.append(
                    {"role": "tool", "tool_call_id": _get(b, "tool_use_id"), "content": body if isinstance(body, str) else json.dumps(body)}
                )
            elif _get(b, "type") == "text":
                texts.append(_get(b, "text", ""))
        if texts:
            out.append({"role": "user", "content": "\n".join(texts)})
    return out


def _extract_json(text: str) -> dict:
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.S)
    candidate = fenced.group(1) if fenced else text[text.find("{") : text.rfind("}") + 1]
    if not candidate:
        raise ValueError("no JSON object in the model's answer")
    return json.loads(candidate)


TRIAGE_JSON_INSTRUCTION = "\n\nAnswer with ONLY one JSON object, no prose, matching this JSON schema:\n" + json.dumps(
    Triage.model_json_schema()
)


class OpenRouterLLM:
    """OpenRouter chat completions over httpx2. Free models are paced, retried and fall back between models."""

    provider = "openrouter"

    def __init__(
        self,
        model: str | None = None,
        effort: str | None = None,
        api_key: str | None = None,
        fallbacks: list[str] | None = None,
        max_retries: int = 5,
    ):
        self.model = model or os.environ.get("AGENT_MODEL") or DEFAULT_OPENROUTER_MODEL
        env_fallbacks = [m.strip() for m in os.environ.get("AGENT_FALLBACK_MODELS", "").split(",") if m.strip()]
        chosen = fallbacks if fallbacks is not None else (env_fallbacks or DEFAULT_OPENROUTER_FALLBACKS)
        self.fallbacks = [m for m in chosen if m != self.model]
        self.effort = effort or os.environ.get("AGENT_EFFORT", "medium")
        key = api_key or os.environ.get("OPENROUTER_API_KEY", "")
        self.configured = bool(key)
        self.max_retries = max_retries
        self.min_interval = float(os.environ.get("OPENROUTER_MIN_INTERVAL", "3.2"))  # free tier: stay under ~20 requests/minute
        self.http = httpx2.AsyncClient(
            base_url=os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
            headers={"Authorization": f"Bearer {key}", "X-Title": "Maplewood clinic inbox agent"},
            timeout=httpx2.Timeout(180.0, connect=15.0),
        )
        self.sleep = asyncio.sleep
        self.calls: list[dict] = []
        self._last = 0.0

    async def _post(self, payload: dict) -> dict:
        for attempt in range(self.max_retries + 1):
            wait = self.min_interval - (time.monotonic() - self._last)
            if wait > 0:
                await self.sleep(wait)
            self._last = time.monotonic()
            try:
                r = await self.http.post("/chat/completions", json=payload)
            except httpx2.TransportError as e:
                if attempt == self.max_retries:
                    raise RuntimeError(f"OpenRouter unreachable: {e!r}") from e
                await self.sleep(min(2**attempt, 30))
                continue
            try:
                body = r.json()
            except ValueError:
                body = {}
            message = str((body.get("error") or {}).get("message", r.text[:300]))
            if r.status_code == 429 and re.search(r"per[- ]day|daily", message, flags=re.I):
                raise LLMQuotaError(f"OpenRouter daily free-model quota reached: {message}")
            if r.status_code in (408, 429) or r.status_code >= 500:
                if attempt == self.max_retries:
                    raise RuntimeError(f"OpenRouter {r.status_code} after {attempt + 1} attempts: {message}")
                retry_after = r.headers.get("Retry-After")
                await self.sleep(min(float(retry_after), 60.0) if retry_after else min(2 ** (attempt + 1), 60))
                continue
            if r.status_code >= 400:
                raise RuntimeError(f"OpenRouter {r.status_code}: {message}")
            if "error" in body and not body.get("choices"):
                if attempt == self.max_retries:
                    raise RuntimeError(f"OpenRouter error: {message}")
                await self.sleep(min(2 ** (attempt + 1), 60))
                continue
            return body
        raise RuntimeError("unreachable")

    def _payload(self, messages: list[dict], max_tokens: int, tools: list[dict] | None = None) -> dict:
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0,
            "max_tokens": max_tokens,
            "reasoning": {"effort": self.effort, "exclude": True},
        }
        if self.fallbacks:
            payload["models"] = [self.model, *self.fallbacks]
        if tools:
            payload["tools"] = to_openai_tools(tools)
            payload["tool_choice"] = "auto"
        return payload

    def _record(self, kind: str, body: dict, started: float, stop: str) -> None:
        u = body.get("usage") or {}
        entry = {
            "kind": kind,
            "model": body.get("model", self.model),
            "input_tokens": u.get("prompt_tokens", 0) or 0,
            "output_tokens": u.get("completion_tokens", 0) or 0,
            "cache_read_input_tokens": 0,
            "cache_creation_input_tokens": 0,
            "latency_s": round(time.monotonic() - started, 2),
            "stop_reason": stop,
        }
        if "cost" in u:
            entry["cost_usd"] = u["cost"]
        self.calls.append(entry)

    async def triage(self, system: str, user: str) -> Triage:
        messages = [{"role": "system", "content": system + TRIAGE_JSON_INSTRUCTION}, {"role": "user", "content": user}]
        last_error = ""
        for kind in ("triage", "triage_repair"):
            if last_error:
                messages.append(
                    {"role": "user", "content": f"That was not valid ({last_error}). Reply with only the corrected JSON object."}
                )
            started = time.monotonic()
            body = await self._post(self._payload(messages, 3000))
            text = (body["choices"][0]["message"].get("content") or "").strip()
            self._record(kind, body, started, body["choices"][0].get("finish_reason") or "stop")
            messages.append({"role": "assistant", "content": text})
            try:
                return Triage.model_validate(_extract_json(text))
            except (ValueError, ValidationError) as e:
                last_error = str(e).splitlines()[0][:200]
        raise ValueError(f"triage returned invalid JSON twice: {last_error}")

    async def step(self, system: str, messages: list, tools: list):
        started = time.monotonic()
        body = await self._post(self._payload(to_openai_messages(system, messages), 6000, tools))
        msg = body["choices"][0]["message"]
        blocks = []
        if msg.get("content"):
            blocks.append(SimpleNamespace(type="text", text=msg["content"]))
        for call in msg.get("tool_calls") or []:
            try:
                args = json.loads(call["function"].get("arguments") or "{}")
            except json.JSONDecodeError:
                args = {}  # the tool's own validation then tells the model what was wrong
            blocks.append(
                SimpleNamespace(
                    type="tool_use",
                    id=call.get("id") or f"call_{len(blocks)}",
                    name=call["function"]["name"],
                    input=args if isinstance(args, dict) else {},
                )
            )
        stop = "tool_use" if any(b.type == "tool_use" for b in blocks) else "end_turn"
        self._record("step", body, started, stop)
        return SimpleNamespace(content=blocks, stop_reason=stop, model=body.get("model"))
