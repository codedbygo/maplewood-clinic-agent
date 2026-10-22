"""Per-message pipeline: pre-screen -> verify -> (escalate | triage -> tool loop) -> post-guard.

The runner talks to the clinic only through the MCP server. `tool_calls` in the output is the real trace.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from collections.abc import Callable
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path
from typing import Any

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.types import TextContent
from pydantic import ValidationError

from agent.llm import LLMQuotaError
from agent.prompts import AGENT_SYSTEM, TRIAGE_SYSTEM, agent_user_content, triage_user_content
from agent.safety import EMERGENCY_TEMPLATE, post_guard, prescreen
from agent.schema import CONVERSATIONAL_ACTIONS, INTENTS, URGENCIES, AgentResult, FinalAnswer
from clinic_mcp.policy.dates import find_date_phrases, next_business_days
from clinic_mcp.policy.refill import _tokens
from clinic_mcp.store import load_store

ROOT = Path(__file__).resolve().parent.parent
MAX_TOOL_CALLS = 12
MAX_TURNS = 20

SUBMIT_TOOL = {
    "name": "submit_result",
    "description": "Finish the message. Call exactly once, after draft_reply (or without a reply for spam).",
    "input_schema": {
        "type": "object",
        "properties": {
            "intents": {"type": "array", "items": {"type": "string", "enum": list(INTENTS)}},
            "urgency": {"type": "string", "enum": list(URGENCIES)},
            "emergency": {"type": "boolean"},
            "actions": {
                "type": "array",
                "items": {"type": "string", "enum": list(CONVERSATIONAL_ACTIONS)},
                "description": (
                    "Only the conversational actions defined in the instructions. Tool-backed actions are recorded automatically."
                ),
            },
            "notes": {"type": "string", "description": "Optional note for staff."},
        },
        "required": ["intents", "urgency", "emergency", "actions"],
    },
}


def redact(obj):
    """Drop verification tokens from anything that leaves the runner (logs, UI events)."""
    if isinstance(obj, dict):
        return {k: ("[redacted]" if k == "verification_token" and v else redact(v)) for k, v in obj.items()}
    if isinstance(obj, list):
        return [redact(v) for v in obj]
    return obj


class ClinicClient:
    """MCP session wrapper that records a (token-free) trace of non-admin calls and emits it live."""

    def __init__(self, session: ClientSession):
        self.session = session
        self.trace: list[dict] = []
        self.emit: Callable[[dict], None] | None = None
        self._tools: list[dict] | None = None

    async def call(self, name: str, args: dict | None = None, record: bool = True) -> dict:
        res = await self.session.call_tool(name, args or {})
        first = res.content[0] if res.content else None
        text = first.text if isinstance(first, TextContent) else "{}"
        try:
            out = json.loads(text)
        except json.JSONDecodeError:
            out = {"ok": False, "reason": text}
        if getattr(res, "is_error", False):
            out = {"ok": False, "reason": text, "tool_error": True}  # bad arguments etc.
        out.setdefault("ok", True)
        if record:
            entry = {"name": name, "input": redact(args or {}), "ok": bool(out.get("ok")), "output": redact(out)}
            self.trace.append(entry)
            if self.emit:
                self.emit({"type": "tool", **entry})
        return out

    async def llm_tools(self) -> list[dict]:
        if self._tools is None:
            listed = (await self.session.list_tools()).tools
            self._tools = [
                {"name": t.name, "description": t.description or "", "input_schema": t.input_schema}
                for t in sorted(listed, key=lambda t: t.name)
                if not t.name.startswith("admin_")
            ]
            self._tools.append(SUBMIT_TOOL)
        return self._tools

    async def reset(self) -> None:
        await self.call("admin_reset_store", record=False)

    async def export_state(self) -> dict:
        return await self.call("admin_export_state", record=False)


@asynccontextmanager
async def open_clinic():
    params = StdioServerParameters(command=sys.executable, args=["-m", "clinic_mcp.server"], cwd=str(ROOT), env={"PYTHONPATH": str(ROOT)})
    with open(os.devnull, "w") as devnull:
        async with stdio_client(params, errlog=devnull) as (read, write), ClientSession(read, write) as session:
            await session.initialize()
            yield ClinicClient(session)


# ---- helpers ----

_LOCAL = load_store()  # read-only reference data (clinic calendar, medication names)


def _phi_terms(state: dict, candidates: list[str], body: str) -> list[str]:
    """Strings that would reveal a candidate patient's appointments or medications to an unverified sender."""
    terms: list[str] = []
    low_body = body.lower()
    for a in state.get("appointments", []):
        if a["patient_id"] in candidates and a.get("status") == "booked":
            d = date.fromisoformat(a["date"])
            h, m = map(int, a["start"].split(":"))
            h12 = h % 12 or 12
            ampm = "am" if h < 12 else "pm"
            terms += [
                a["date"],
                d.strftime("%b %d").replace(" 0", " "),
                d.strftime("%B %d").replace(" 0", " "),
                a["start"],
                f"{h12}:{m:02d} {ampm}",
                f"{h12}:{m:02d}{ampm}",
            ]
            if m == 0:
                terms += [f"{h12} {ampm}", f"{h12}{ampm}"]
    for med in _LOCAL.medications:
        if med["patient_id"] in candidates:
            terms += _tokens(med["medication"])[:1]
    return sorted({t for t in terms if t.lower() not in low_body})


def _other_patient_names(msg: dict) -> list[str]:
    """Patients other than the sender: every full name, plus first names of anyone the message names."""
    sender = (msg.get("from_name") or "").casefold()
    body = msg["body"].casefold()
    names: list[str] = []
    for p in _LOCAL.patients.values():
        full = p["name"]
        if full.casefold() == sender:
            continue
        names.append(full)
        if full.casefold() in body:
            names.append(full.split()[0])
    return names


async def _resolve_message_dates(clinic: ClinicClient, body: str) -> list[str]:
    """Resolve the message's date phrases with the clinic calendar, so the model never does date arithmetic.
    "the following week" is anchored on the date phrase before it ("from Monday the 16th to the following week")."""
    lines, anchor = [], None
    for phrase in find_date_phrases(body)[:4]:
        args = {"expression": phrase}
        if anchor and re.search(r"following|week after", phrase, re.IGNORECASE):
            args["anchor_date"] = anchor
        out = await clinic.call("resolve_date", args)
        if out.get("ok"):
            anchor = out.get("start") or anchor
            lines.append(f"'{phrase}' = {out['start']} to {out['end']}; business days {out['business_days']}. {out.get('reason', '')}")
        else:
            lines.append(f"'{phrase}': {out.get('reason')}")
    return lines


def _guard_context(screen: dict, triage, phi_terms: list[str], msg: dict) -> dict:
    today = _LOCAL.today
    nbd = next_business_days(today, 2, _LOCAL.clinic["holidays"])
    lang = "es" if "es" in (screen["language"], getattr(triage, "language", None)) else "en"
    return {
        "language": lang,
        "today": today.isoformat(),
        "next_business_day": nbd[1].isoformat() if nbd[0] == today else nbd[0].isoformat(),
        "phi_terms": phi_terms,
        "llm_emergency": bool(getattr(triage, "emergency", False)),
        "providers": [p["name"] for p in _LOCAL.clinic["providers"]],
        "other_patient_names": _other_patient_names(msg),
    }


async def _escalate(clinic: ClinicClient, msg: dict, screen: dict, verification: dict, why: str, lang: str) -> None:
    summary = (
        f"POSSIBLE EMERGENCY from {msg.get('from_name')} ({msg.get('from_contact')}, {msg.get('channel')}). "
        f"Reason: {why}. Message: {msg['body'][:500]}"
    )
    await clinic.call(
        "route_to_queue",
        {
            "queue": "clinician_urgent",
            "summary": summary,
            "priority": "emergency",
            "verification_token": verification.get("verification_token"),
        },
    )
    await clinic.call("draft_reply", {"text": EMERGENCY_TEMPLATE[lang], "language": lang})


async def _tool_loop(clinic: ClinicClient, llm, user_content: str) -> tuple[FinalAnswer | None, str]:
    tools = await clinic.llm_tools()
    offered = {t["name"] for t in tools}
    messages: list[dict[str, Any]] = [{"role": "user", "content": user_content}]
    model_calls, nudged = 0, False
    for _ in range(MAX_TURNS):
        resp = await llm.step(AGENT_SYSTEM, messages, tools)
        messages.append({"role": "assistant", "content": resp.content})
        uses = [b for b in resp.content if getattr(b, "type", None) == "tool_use"]
        if not uses:
            if nudged:
                return None, "model stopped without submit_result"
            nudged = True
            messages.append({"role": "user", "content": "Call submit_result to finish this message."})
            continue
        results, submitted = [], None
        for u in uses:
            if u.name == "submit_result":
                submitted = u.input
                results.append({"type": "tool_result", "tool_use_id": u.id, "content": "Submitted."})
            elif u.name not in offered:
                # Hidden (admin_) or invented tool names are refused here, not just hidden from the list.
                model_calls += 1
                reason = f"Tool '{u.name}' is not available."
                clinic.trace.append(
                    {"name": u.name, "input": redact(dict(u.input)), "ok": False, "output": {"ok": False, "reason": reason}}
                )
                if clinic.emit:
                    clinic.emit({"type": "tool", **clinic.trace[-1]})
                results.append({"type": "tool_result", "tool_use_id": u.id, "is_error": True, "content": reason})
            elif model_calls >= MAX_TOOL_CALLS:
                results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": u.id,
                        "is_error": True,
                        "content": "Tool-call limit reached. Call submit_result now.",
                    }
                )
            else:
                model_calls += 1
                out = await clinic.call(u.name, dict(u.input))
                results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": u.id,
                        "content": json.dumps(out, default=str),
                        **({"is_error": True} if out.get("tool_error") else {}),
                    }
                )
        if submitted is not None:
            try:
                return FinalAnswer(**submitted), "ok"
            except ValidationError as e:
                return None, f"invalid submit_result: {e.errors()[:2]}"
        messages.append({"role": "user", "content": results})
        if model_calls >= MAX_TOOL_CALLS and nudged:
            return None, "tool-call limit reached"
        if model_calls >= MAX_TOOL_CALLS:
            nudged = True
    return None, "turn limit reached"  # pragma: no cover  (backstop: the tool-call cap ends the loop by turn 14 of 20)


async def process_message(
    msg: dict, clinic: ClinicClient, llm, emit: Callable[[dict], None] | None = None, fail_on_quota: bool = False
) -> tuple[AgentResult, dict]:
    """Process one message. `emit` receives live events (stages, tool calls, guard, result) for the UI.

    fail_on_quota: batch runs re-raise LLMQuotaError (after any emergency escalation) so a run never
    silently fills up with fallback results; the live console keeps the safe fallback instead.
    """
    started = time.monotonic()
    first_call = len(getattr(llm, "calls", []))
    clinic.trace = []
    clinic.emit = emit
    say = emit or (lambda event: None)
    log: dict[str, Any] = {"id": msg["id"], "from_name": msg.get("from_name"), "body": msg["body"], "path": None, "error": None}

    await clinic.call(
        "admin_begin_message",
        {
            "message_id": msg["id"],
            "from_name": msg.get("from_name", ""),
            "from_contact": msg.get("from_contact", ""),
            "channel": msg.get("channel", ""),
            "received_at": msg.get("received_at"),
        },
        record=False,
    )
    screen = prescreen(msg["body"])
    say({"type": "stage", "stage": "prescreen", "data": screen})
    verification = await clinic.call("verify_sender", {"stated_dob": msg.get("stated_dob")})
    triage = None
    answer: FinalAnswer | None = None

    if screen["tier"] == "emergency":
        # Escalate before any LLM call: a model outage or refusal cannot delay this.
        log["path"] = "emergency"
        await _escalate(clinic, msg, screen, verification, f"safety pre-screen: {', '.join(screen['matches'])}", screen["language"])
        try:
            triage = await llm.triage(TRIAGE_SYSTEM, triage_user_content(msg))
            say({"type": "stage", "stage": "triage", "data": triage.model_dump()})
        except Exception as e:  # intents are nice to have here; escalation already happened
            log["error"] = f"triage failed after escalation: {e!r}"  # never re-raised: the emergency is handled
        answer = FinalAnswer(intents=list(triage.intents) if triage else ["clinical"], urgency="emergency", emergency=True)
    else:
        try:
            triage = await llm.triage(TRIAGE_SYSTEM, triage_user_content(msg))
            say({"type": "stage", "stage": "triage", "data": triage.model_dump()})
        except Exception as e:
            if fail_on_quota and isinstance(e, LLMQuotaError):
                raise
            log["error"] = f"triage failed: {e!r}"
            say({"type": "stage", "stage": "triage", "data": None, "error": str(e)})
        if triage is not None and triage.emergency:
            log["path"] = "emergency"
            lang = "es" if "es" in (screen["language"], triage.language) else "en"
            await _escalate(clinic, msg, screen, verification, f"LLM triage: {triage.rationale}", lang)
            answer = FinalAnswer(intents=list(triage.intents), urgency="emergency", emergency=True)
        elif triage is not None:
            log["path"] = "normal"
            summary = None
            if verification.get("verification_token"):
                summary = (await clinic.call("get_patient_summary", {"verification_token": verification["verification_token"]})).get(
                    "patient"
                )
            dates = await _resolve_message_dates(clinic, msg["body"])
            content = agent_user_content(msg, screen, verification, summary, triage.model_dump(), dates)
            try:
                answer, status = await _tool_loop(clinic, llm, content)
            except Exception as e:
                if fail_on_quota and isinstance(e, LLMQuotaError):
                    raise
                answer, status = None, f"tool loop error: {e!r}"
            if answer is None:
                log["path"], log["error"] = "fallback", status

    if answer is None:
        # Fail safe: a human owns the message; clinical concerns go to a clinician.
        log["path"] = "fallback"
        urgency = triage.urgency if triage else ("urgent" if screen["tier"] == "urgent_clinical" else "routine")
        if (triage and triage.clinical_concern) or screen["tier"] == "urgent_clinical":
            await clinic.call(
                "route_to_queue",
                {
                    "queue": "clinician_urgent" if urgency != "routine" else "clinician_routine",
                    "summary": f"Agent could not complete ({log['error']}). Clinical concern present.",
                    "priority": urgency,
                    "verification_token": verification.get("verification_token"),
                },
            )
        answer = FinalAnswer(intents=list(triage.intents) if triage else ["other"], urgency=urgency)

    say({"type": "stage", "stage": "path", "data": {"path": log["path"], "error": log["error"]}})
    phi = []
    if not str(verification.get("status", "")).startswith("verified") and verification.get("candidate_patient_ids"):
        phi = _phi_terms(await clinic.export_state(), verification["candidate_patient_ids"], msg["body"])
    later = [
        c["output"]
        for c in clinic.trace
        if c["name"] == "verify_sender" and c["ok"] and str(c["output"].get("status", "")).startswith("verified")
    ]
    if later and not str(verification.get("status", "")).startswith("verified"):
        verification = later[-1]
    log["phi_terms"] = phi
    outcome = post_guard(msg["id"], answer, clinic.trace, screen, verification, _guard_context(screen, triage, phi, msg))
    for r in outcome.extra_routes:
        await clinic.call("route_to_queue", {**r, "verification_token": verification.get("verification_token")})
    result = outcome.result.model_copy(update={"tool_calls": [c["name"] for c in clinic.trace]})
    say({"type": "guard", "data": {"violations": outcome.violations, "extra_routes": outcome.extra_routes}})

    log.update(
        screen=screen,
        triage=triage.model_dump() if triage else None,
        verification=redact(verification),
        trace=clinic.trace,
        final_answer=answer.model_dump(),
        guard_violations=outcome.violations,
        extra_routes=outcome.extra_routes,
        llm_calls=list(getattr(llm, "calls", []))[first_call:],
        latency_s=round(time.monotonic() - started, 2),
        result=result.model_dump(),
    )
    say({"type": "result", "data": result.model_dump(), "latency_s": log["latency_s"], "llm_calls": log["llm_calls"]})
    return result, log
