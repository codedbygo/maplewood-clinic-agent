"""Runner tests with a scripted LLM against the real MCP server (no network)."""

import asyncio
import re
from types import SimpleNamespace

from agent.runner import MAX_TOOL_CALLS, open_clinic, process_message
from agent.safety import EMERGENCY_TEMPLATE
from agent.schema import Triage


def triage(**kw):
    base = dict(
        intents=["refill"],
        urgency="routine",
        emergency=False,
        clinical_concern=False,
        rationale="r",
        language="en",
        suspicious_instruction=False,
    )
    base.update(kw)
    return Triage(**base)


def tool_use(name, **inp):
    return SimpleNamespace(type="tool_use", id=f"tu_{name}_{len(inp)}", name=name, input=inp)


class FakeLLM:
    model = "fake"

    def __init__(self, triage_result=None, script=None, triage_error=None):
        self.triage_result, self.script, self.triage_error = triage_result or triage(), script or [], triage_error
        self.calls, self.steps = [], 0

    async def triage(self, system, user):
        if self.triage_error:
            raise self.triage_error
        return self.triage_result

    async def step(self, system, messages, tools):
        first = messages[0]["content"]
        token = (re.search(r"verification_token: (\S+)", first) or [None, None])[1]
        blocks = self.script(self.steps, token) if callable(self.script) else self.script[self.steps]
        self.steps += 1
        return SimpleNamespace(content=blocks, stop_reason="tool_use")


def msg(body, name="Robert Chen", contact="555-0102", mid="T1"):
    return {
        "id": mid,
        "received_at": "2026-11-09T08:00:00-06:00",
        "channel": "sms",
        "from_name": name,
        "from_contact": contact,
        "body": body,
    }


async def _run(m, llm):
    async with open_clinic() as clinic:
        await clinic.reset()
        return await process_message(m, clinic, llm)


def test_emergency_prescreen_escalates_without_the_tool_loop():
    llm = FakeLLM(triage_result=triage(intents=["clinical"], urgency="emergency", emergency=True))
    result, log = asyncio.run(_run(msg("crushing chest pain into my left arm"), llm))
    assert llm.steps == 0
    assert result.actions == ["escalate_emergency"]
    assert result.routed_to == ["clinician_urgent"]
    assert result.reply_draft == EMERGENCY_TEMPLATE["en"]
    assert result.tool_calls == ["verify_sender", "route_to_queue", "draft_reply"]
    assert log["path"] == "emergency"


def test_emergency_escalates_even_if_triage_call_fails():
    llm = FakeLLM(triage_error=RuntimeError("API down"))
    result, _ = asyncio.run(_run(msg("I can't breathe"), llm))
    assert result.actions == ["escalate_emergency"] and result.urgency == "emergency"


def test_llm_triage_can_raise_to_emergency():
    llm = FakeLLM(triage_result=triage(intents=["clinical"], urgency="emergency", emergency=True))
    result, log = asyncio.run(_run(msg("something feels very wrong with my heart"), llm))
    assert result.actions == ["escalate_emergency"]
    assert log["path"] == "emergency"


def test_scripted_refill_flow_uses_real_trace():
    def script(step, token):
        return [
            [tool_use("check_refill_eligibility", verification_token=token, medication_query="lisinopril")],
            [tool_use("prepare_refill_for_approval", verification_token=token, medication_query="lisinopril")],
            [tool_use("draft_reply", text="Hi Robert, sent to Dr. Okafor for approval.", language="en")],
            [tool_use("submit_result", intents=["refill"], urgency="routine", actions=[], emergency=False)],
        ][step]

    result, log = asyncio.run(_run(msg("Can I get my lisinopril refilled?"), FakeLLM(script=script)))
    assert result.patient_id == "P002"
    assert result.actions == ["prepare_refill_for_approval"]
    assert result.routed_to == ["provider_refills"]
    assert result.tool_calls == [
        "verify_sender",
        "get_patient_summary",
        "check_refill_eligibility",
        "prepare_refill_for_approval",
        "draft_reply",
    ]
    assert log["guard_violations"] == []


def test_loop_is_capped_and_falls_back_safely():
    llm = FakeLLM(script=lambda step, token: [tool_use("get_clinic_info")])
    result, log = asyncio.run(_run(msg("What are your hours?"), llm))
    assert result.tool_calls.count("get_clinic_info") == MAX_TOOL_CALLS
    assert result.reply_draft  # fallback acknowledgment
    assert "route_to_front_desk" in result.actions
    assert log["path"] == "fallback"


def test_admin_tools_are_hidden_from_the_model():
    seen = {}

    def script(step, token):
        return [tool_use("submit_result", intents=["admin"], urgency="routine", actions=["acknowledge"])]

    class Spy(FakeLLM):
        async def step(self, system, messages, tools):
            seen["names"] = {t["name"] for t in tools}
            return await super().step(system, messages, tools)

    asyncio.run(_run(msg("hello"), Spy(script=script)))
    assert "submit_result" in seen["names"]
    assert not any(n.startswith("admin_") for n in seen["names"])


def test_runner_emits_stage_and_tool_events_in_order():
    events = []

    def script(step, token):
        return [
            [tool_use("draft_reply", text="Hi", language="en")],
            [tool_use("submit_result", intents=["other"], urgency="routine", actions=["acknowledge"])],
        ][step]

    async def go():
        async with open_clinic() as clinic:
            await clinic.reset()
            return await process_message(
                msg("thanks!"), clinic, FakeLLM(triage_result=triage(intents=["other"]), script=script), emit=events.append
            )

    asyncio.run(go())
    kinds = [e["type"] if e["type"] != "stage" else e["stage"] for e in events]
    assert kinds[0] == "prescreen"
    assert kinds.index("tool") < kinds.index("triage")
    assert kinds[-2:] == ["guard", "result"]
    assert any(e["type"] == "tool" and e["name"] == "draft_reply" for e in events)


def test_verification_token_never_leaves_the_runner():
    import json as _json

    events = []

    def script(step, token):
        return [
            [tool_use("list_medications", verification_token=token)],
            [tool_use("submit_result", intents=["refill"], urgency="routine", actions=[])],
        ][step]

    async def go():
        async with open_clinic() as clinic:
            await clinic.reset()
            return await process_message(msg("what meds am I on"), clinic, FakeLLM(script=script), emit=events.append)

    _, log = asyncio.run(go())
    blob = _json.dumps([events, log], default=str)
    assert "vt_" not in blob


def test_quota_error_stops_a_batch_run_but_live_falls_back_safely():
    from agent.llm import LLMQuotaError

    quota = FakeLLM(triage_error=LLMQuotaError("daily quota"))

    async def go(strict):
        # Batch runs catch the error inside the MCP session, as agent.cli.run_file does.
        async with open_clinic() as clinic:
            await clinic.reset()
            try:
                return await process_message(msg("refill please"), clinic, quota, fail_on_quota=strict)
            except LLMQuotaError:
                return "stopped"

    assert asyncio.run(go(True)) == "stopped"
    result, log = asyncio.run(go(False))
    assert log["path"] == "fallback" and result.reply_draft


def test_quota_error_never_blocks_emergency_escalation():
    from agent.llm import LLMQuotaError

    async def go():
        async with open_clinic() as clinic:
            await clinic.reset()
            return await process_message(msg("I can't breathe"), clinic, FakeLLM(triage_error=LLMQuotaError("q")), fail_on_quota=True)

    result, _ = asyncio.run(go())
    assert result.actions == ["escalate_emergency"]
