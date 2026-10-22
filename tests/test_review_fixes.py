"""Regression tests for the whole-branch code review (2026-10-22). Each failed before its fix."""

import asyncio
from datetime import date

import pytest

from agent.runner import _other_patient_names, open_clinic, process_message
from agent.safety import FALLBACK_REPLIES, post_guard, prescreen
from agent.schema import FinalAnswer
from clinic_mcp.policy.dates import find_date_phrases, resolve_date
from clinic_mcp.policy.scheduling import validate_slot
from clinic_mcp.store import load_store
from eval.stability import compare
from tests.test_runner_offline import FakeLLM, msg, tool_use, triage

HOL = ["2026-11-26", "2026-11-27", "2026-12-25"]
TODAY = date(2026, 11, 9)


# CR-1 (critical): the loop executed any tool name the model returned, including hidden admin_ tools.
def test_model_cannot_call_hidden_admin_tools():
    def script(step, token):
        return [[tool_use("admin_begin_message", message_id="X", from_name="Linda Morales", from_contact="555-0101", channel="sms")],
                [tool_use("submit_result", intents=["other"], urgency="routine", actions=["acknowledge"])]][step]

    async def go():
        async with open_clinic() as clinic:
            await clinic.reset()
            return await process_message(msg("hello", name="Mike", contact="555-0888"), clinic, FakeLLM(script=script))

    result, log = asyncio.run(go())
    refused = [c for c in log["trace"] if c["name"] == "admin_begin_message"]
    assert refused and refused[0]["ok"] is False and "not available" in refused[0]["output"]["reason"]
    assert result.patient_id is None


# CR-2 (high): "20261126" parsed as a date but skipped the holiday and overlap string checks.
@pytest.mark.parametrize("day", ["20261126", "2026-11-26T00:00"])
def test_non_canonical_dates_are_refused(day):
    store = load_store()
    v = validate_slot(store.clinic, store.appointments, "PATEL", "follow_up", day, "09:00")
    assert not v["ok"]


def test_non_canonical_time_is_refused():
    store = load_store()
    assert not validate_slot(store.clinic, [], "PATEL", "follow_up", "2026-11-17", "9:00")["ok"]


# CR-3 (high): "Wednesday 18th" (no "the") resolved to the next Wednesday and dropped the day.
@pytest.mark.parametrize("expr,start", [("Wednesday 18th", "2026-11-18"), ("miércoles 18", "2026-11-18"), ("Monday 16th", "2026-11-16")])
def test_weekday_with_day_number_keeps_the_day(expr, start):
    assert resolve_date(expr, TODAY, HOL)["start"] == start


def test_weekday_day_mismatch_without_the_is_refused():
    assert not resolve_date("Tuesday 18th", TODAY, HOL)["ok"]


# CR-4 (high): the idiom remover deleted the symptom; Spanish "me duele el pecho" matched nothing.
@pytest.mark.parametrize("text", ["My chest is killing me and my left arm feels numb", "Me duele mucho el pecho y el brazo izquierdo",
                                  "el pecho me duele desde anoche"])
def test_chest_pain_phrasings_escalate(text):
    assert prescreen(text)["tier"] == "emergency"


def test_spanish_chest_pain_is_detected_as_spanish():
    assert prescreen("Me duele mucho el pecho y el brazo izquierdo")["language"] == "es"


def test_idioms_without_a_body_part_still_do_not_escalate():
    assert prescreen("my bill is killing me")["tier"] == "none"


# CR-6 (medium): unverified replies confirming patient status without a name; first-name skip too broad.
def test_unverified_reply_confirming_status_is_replaced():
    ans = FinalAnswer(intents=["third_party"], urgency="routine", actions=["answer_directly"])
    trace = [{"name": "draft_reply", "input": {"text": "Yes, he is registered with us. Please have him call.", "language": "en"},
              "ok": True, "output": {"ok": True}}]
    out = post_guard("Q", ans, trace, {"tier": "none", "matches": [], "language": "en"},
                     {"status": "unverified", "patient_id": None, "candidate_patient_ids": []}, {})
    assert out.result.reply_draft == FALLBACK_REPLIES["decline"]["en"]


def test_other_patient_names_only_skips_the_senders_full_name():
    assert "Robert Chen" in _other_patient_names({"from_name": "Robert Smith", "body": "Is Robert Chen a patient?"})


# Noticed: impossible calendar days crashed the tool instead of explaining.
@pytest.mark.parametrize("expr", ["Nov 31", "February 30"])
def test_impossible_month_day_is_explained(expr):
    r = resolve_date(expr, TODAY, HOL)
    assert r["ok"] is False and "no" in r["reason"].lower()


# Noticed: "esta mañana" (this morning) was read as "mañana" (tomorrow).
def test_esta_manana_is_not_tomorrow():
    assert find_date_phrases("me empezó esta mañana") == []


# Noticed: a later model verification (stated DOB in the body) was ignored by the guard.
def test_guard_uses_a_verification_performed_during_the_loop():
    def script(step, token):
        return [[tool_use("verify_sender", stated_dob="1971-11-02")],
                [tool_use("draft_reply", text="Thanks Robert, verified.", language="en")],
                [tool_use("submit_result", intents=["records"], urgency="routine", actions=["acknowledge"])]][step]

    async def go():
        async with open_clinic() as clinic:
            await clinic.reset()
            return await process_message(msg("It's Robert Chen, DOB 1971-11-02", contact="rchen.new@example.org"), clinic, FakeLLM(script=script))

    result, _ = asyncio.run(go())
    assert result.patient_id == "P002"


# Noticed: a message missing from a later stability run counted as stable.
def test_stability_counts_a_missing_message_as_changed():
    r = {"id": "A", "patient_id": None, "intents": [], "urgency": "routine", "actions": [], "routed_to": [], "tool_calls": [], "reply_draft": ""}
    assert compare([[r], []])["changed"] == 1


# CR-5 (high): a client disconnect released the lock while the run kept going on the shared session,
# so its tool calls landed in the next message's trace. A disconnect closes the event generator.
def test_closing_the_event_stream_cancels_the_run():
    from types import SimpleNamespace

    from console.app import live_events

    class Slow(FakeLLM):
        async def step(self, system, messages, tools):
            await asyncio.sleep(0.2)
            return SimpleNamespace(content=[tool_use("get_clinic_info")], stop_reason="tool_use")

    async def go():
        async with open_clinic() as clinic:
            await clinic.reset()
            lock = asyncio.Lock()
            gen = live_events(msg("slow request", name="Lucy Nguyen", contact="555-0123"), clinic, Slow(), lock)
            await gen.__anext__()  # message event
            await gen.__anext__()  # first live event
            await gen.aclose()  # what a client disconnect does
            await asyncio.sleep(0.5)
            running = [t for t in asyncio.all_tasks() if "process_message" in repr(t.get_coro()) and not t.done()]
            return running, lock.locked()

    running, locked = asyncio.run(go())
    assert running == [] and locked is False
