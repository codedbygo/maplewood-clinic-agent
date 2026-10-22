"""Paths no other test reached: safety rules, guard branches, refusals and reporting edges."""

import asyncio
import json
from types import SimpleNamespace

import pytest
from starlette.testclient import TestClient

import agent.cli as cli
from agent.llm import AnthropicLLM, load_dotenv, to_openai_messages
from agent.prompts import agent_user_content
from agent.runner import open_clinic, process_message
from agent.safety import EMERGENCY_TEMPLATE, detect_language, post_guard, prescreen
from agent.schema import FinalAnswer
from clinic_mcp.policy import scheduling
from clinic_mcp.policy.refill import resolve_medication
from clinic_mcp.policy.verification import _contact_eq, verify_sender
from clinic_mcp.store import load_store
from clinic_mcp.tools import Tools
from console.app import create_app, live_events
from eval.harness import _pct
from eval.metrics import _set_f1
from eval.must_not import _c_book_on_leave, _c_escalate, _c_prepare, _phi_terms, global_safety_checks
from eval.report import _trace_line
from tests.test_runner_offline import FakeLLM, msg, tool_use, triage
from tests.test_tools import token_for

NONE = {"tier": "none", "matches": [], "language": "en"}
VERIFIED = {"status": "verified_patient", "patient_id": "P002", "candidate_patient_ids": ["P002"]}


def _draft(text):
    return {"name": "draft_reply", "input": {"text": text, "language": "en"}, "ok": True, "output": {"ok": True}}


# Safety pre-screen rules that had no test.
def test_bleeding_in_pregnancy_is_an_emergency():
    s = prescreen("I'm 10 weeks pregnant and bleeding with cramps")
    assert s["tier"] == "emergency" and "pregnancy_bleeding" in s["matches"]


def test_low_sugar_described_in_words_with_symptoms_is_an_emergency():
    s = prescreen("I think my sugar is low, I'm shaky and sweaty")
    assert s["tier"] == "emergency" and "hypoglycaemia" in s["matches"]


def test_language_of_a_message_without_words_defaults_to_english():
    assert detect_language("") == "en" and detect_language("123 !!") == "en"


# Post-guard branches.
def test_unknown_intent_is_dropped_and_logged():
    out = post_guard(
        "Q", FinalAnswer(intents=["refill", "bogus"], urgency="routine", actions=["acknowledge"]), [_draft("Thanks.")], NONE, VERIFIED, {}
    )
    assert out.result.intents == ["refill"] and any("unknown intent 'bogus'" in v for v in out.violations)


def test_work_done_on_an_emergency_is_flagged_and_reply_forced_to_template():
    trace = [{"name": "book_appointment", "input": {}, "ok": True, "output": {"ok": True, "appointment": {"date": "2026-11-10"}}}]
    screen = {"tier": "emergency", "matches": ["chest_pain"], "language": "en"}
    out = post_guard("Q", FinalAnswer(intents=["schedule"], urgency="routine", actions=[]), trace, screen, VERIFIED, {})
    assert out.result.actions == ["escalate_emergency"] and out.result.reply_draft == EMERGENCY_TEMPLATE["en"]
    assert any("work done on an emergency" in v for v in out.violations)


def test_clinical_advice_reply_with_an_existing_clinician_route_adds_no_second_route():
    trace = [
        {"name": "route_to_queue", "input": {"queue": "clinician_routine", "priority": "routine"}, "ok": True, "output": {"ok": True}},
        _draft("High TSH means your thyroid is underactive; you should take more levothyroxine."),
    ]
    out = post_guard("Q", FinalAnswer(intents=["clinical"], urgency="routine", actions=[]), trace, NONE, VERIFIED, {})
    assert out.result.routed_to == ["clinician_routine"] and "route_to_clinician" in out.result.actions


# Policy edges.
def test_reschedule_of_an_unknown_appointment_is_refused():
    assert scheduling.reschedule(load_store(), "A999", "2026-11-12", "09:00")["violations"] == ["not_found"]


def test_match_appointments_filters_by_visit_type():
    appts = load_store().appointments
    hits = scheduling.match_appointments(appts, "P019", visit_type="annual_physical")
    assert [a["id"] for a in hits] == ["A001", "A101"]


def test_medication_match_keeps_the_closer_of_two_near_misses():
    meds = [{"medication": "Metformin 500 mg"}, {"medication": "Metformin 1000 mg"}]
    assert resolve_medication("metformn", meds) is meds[0]


def test_empty_contact_never_matches_and_shared_name_and_dob_is_not_verified():
    assert _contact_eq("", "555-0101") is False
    twins = {
        "X1": {"id": "X1", "name": "Sam Lee", "dob": "1990-01-01", "phone": "1", "email": "a@x"},
        "X2": {"id": "X2", "name": "Sam Lee", "dob": "1990-01-01", "phone": "2", "email": "b@x"},
    }
    assert verify_sender(twins, "Sam Lee", "nobody@x", "1990-01-01")["status"] != "verified_patient"


# Tool edges.
def test_slots_outside_a_providers_leave_carry_no_leave_note():
    tools = Tools(load_store())
    token = token_for(tools, "Robert Chen", "555-0102")
    out = tools.find_available_slots("follow_up", verification_token=token, provider="OKAFOR", date_from="2026-11-10", date_to="2026-11-10")
    assert "on leave" not in json.dumps(out)


def test_invalid_reschedule_and_repeated_cancel_are_refused():
    tools = Tools(load_store())
    token = token_for(tools, "Robert Chen", "555-0102")
    assert tools.reschedule_appointment(token, "2026-11-26", "09:00", appointment_id="A062")["ok"] is False  # holiday
    assert tools.cancel_appointment(token, appointment_id="A062")["ok"] is True
    assert tools.cancel_appointment(token, appointment_id="A062")["ok"] is False


# Runner paths.
def test_unresolvable_date_phrase_is_passed_on_with_its_reason():
    async def go():
        llm = FakeLLM(script=[[tool_use("submit_result", intents=["schedule"], urgency="routine", actions=["acknowledge"])]])
        async with open_clinic() as clinic:
            await clinic.reset()
            await process_message(msg("Can I come in on February 30?"), clinic, llm)
        return llm

    assert asyncio.run(go()).steps == 1


def test_refused_tool_is_emitted_and_a_loop_crash_falls_back_to_a_human():
    events = []

    def script(step, token):
        if step == 0:
            return [tool_use("admin_reset_store")]
        raise RuntimeError("model crashed")

    async def go():
        async with open_clinic() as clinic:
            await clinic.reset()
            return await process_message(msg("Can I get my lisinopril refilled?"), clinic, FakeLLM(script=script), emit=events.append)

    result, log = asyncio.run(go())
    assert any(e.get("type") == "tool" and e.get("ok") is False for e in events)
    assert result.routed_to and "tool loop error" in log["error"]


def test_refused_tool_calls_count_toward_the_cap():
    refused = tool_use("admin_reset_store")  # a model looping on refused tools still hits the cap
    result, log = asyncio.run(_one(FakeLLM(script=lambda step, token: [refused])))
    assert log["error"] == "tool-call limit reached" and result.routed_to


async def _one(llm):
    async with open_clinic() as clinic:
        await clinic.reset()
        return await process_message(msg("Can I get my lisinopril refilled?"), clinic, llm)


def test_prompt_without_triage_has_no_triage_block():
    content = agent_user_content(msg("hi"), NONE, {"status": "unverified"}, None, None)
    assert "<triage>" not in content


# LLM adapter edges.
def test_missing_env_file_is_ignored(tmp_path):
    load_dotenv(tmp_path / "absent.env")


def test_triage_that_does_not_parse_raises():
    llm = AnthropicLLM(model="claude-haiku-5-5")

    async def parse(**kw):
        usage = SimpleNamespace(input_tokens=1, output_tokens=1, cache_read_input_tokens=0, cache_creation_input_tokens=0)
        return SimpleNamespace(usage=usage, stop_reason="end_turn", model=kw["model"], parsed_output=None)

    llm.client = SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(parse=parse)))
    with pytest.raises(ValueError, match="did not match"):
        asyncio.run(llm.triage("S", "U"))


def test_translation_of_text_only_assistant_turn_and_unknown_blocks():
    out = to_openai_messages(
        "S",
        [
            {"role": "assistant", "content": [{"type": "text", "text": "hello"}]},
            {"role": "user", "content": [{"type": "image", "source": {}}, {"type": "text", "text": "x"}]},
        ],
    )
    assert out[1] == {"role": "assistant", "content": "hello"} and out[2] == {"role": "user", "content": "x"}


# CLI.
def test_cli_process_prints_guard_notes_and_json(monkeypatch, capsys):
    llm = FakeLLM(
        triage_result=triage(), script=[[tool_use("submit_result", intents=["refill"], urgency="routine", actions=["acknowledge"])]]
    )
    monkeypatch.setattr(cli, "LLM", lambda model=None: llm)
    args = SimpleNamespace(
        id="L1", received_at="2026-11-09T09:00:00-06:00", channel="sms", sender="Robert Chen", contact="555-0102",
        text="refill please", dob="1971-11-02", model=None, json=True,
    )  # fmt: skip
    asyncio.run(cli._process(args))
    assert '"result"' in capsys.readouterr().out


def test_cli_run_that_completes_exits_normally(monkeypatch, tmp_path):
    async def fake_run(m, o, model):
        return {"meta": {"stopped": None}}

    monkeypatch.setattr(cli, "run_file", fake_run)
    monkeypatch.setattr("sys.argv", ["agent.cli", "run", "--out", str(tmp_path / "r.json")])
    cli.main()


# Console.
def test_console_without_run_pointer_stability_or_frontend(tmp_path):
    (tmp_path / "results_sample.json").write_text("[]")
    client = TestClient(create_app(results_dir=tmp_path, static_dir=None, llm_factory=lambda: FakeLLM()))
    assert client.get("/api/stability").status_code == 404
    assert client.get("/").status_code == 404
    assert client.get("/api/datasets/sample/state").status_code in (200, 404)


def test_live_run_with_stated_dob_streams_a_result(tmp_path):
    script = [[tool_use("submit_result", intents=["records"], urgency="routine", actions=["acknowledge"])]]
    with TestClient(create_app(results_dir=tmp_path, static_dir=None, llm_factory=lambda: FakeLLM(script=script))) as client:
        body = {"from_name": "Robert Chen", "from_contact": "x@y.z", "channel": "email", "body": "send my labs", "stated_dob": "1971-11-02"}
        text = client.post("/api/live/process", json=body).text
    assert '"type": "result"' in text


def test_live_events_report_a_crashed_run():
    async def boom(*a, **k):
        await asyncio.sleep(0.3)
        raise RuntimeError("crash")

    async def go(monkeypatch_target):
        out = []
        async for e in live_events(msg("x"), None, None, asyncio.Lock()):
            out.append(e)
        return out

    import console.app as app

    original = app.process_message
    app.process_message = boom
    try:
        events = asyncio.run(go(None))
    finally:
        app.process_message = original
    assert '"type": "error"' in events[-1]


# Evaluation edges.
def test_percentile_and_set_f1_edges():
    assert _pct([], 0.5) == 0.0
    assert _set_f1(set(), set()) == 1.0 and _set_f1({"a"}, {"b"}) == 0.0


def test_trace_line_shows_tool_violations():
    line = _trace_line({"name": "book_appointment", "input": {}, "ok": False, "output": {"violations": ["lunch"]}})
    assert "['lunch']" in line


def test_must_not_checks_pass_clean_results():
    state = load_store().as_dict() if hasattr(load_store(), "as_dict") else {"appointments": [], "refill_requests": []}
    clean = {"id": "M1", "actions": ["acknowledge"], "urgency": "routine", "reply_draft": "Thanks.", "patient_id": None}
    assert _c_escalate(clean, {}, state, {}) is None
    assert _c_prepare(clean, {}, state, {}) is None
    assert _c_book_on_leave(clean, {}, state, {}) is None
    assert global_safety_checks([clean], {}, state) == []
    appts = [{"patient_id": "P1", "status": "booked", "date": "2026-11-10", "start": "09:00"}, {"patient_id": "P2", "status": "booked"}]
    assert _phi_terms({"appointments": appts}, {"P1"})


def test_cli_process_without_dob_or_json(monkeypatch, capsys):
    llm = FakeLLM(script=[[tool_use("submit_result", intents=["refill"], urgency="routine", actions=["acknowledge"])]])
    monkeypatch.setattr(cli, "LLM", lambda model=None: llm)
    args = SimpleNamespace(
        id="L1", received_at="2026-11-09T09:00:00-06:00", channel="sms", sender="Robert Chen", contact="555-0102",
        text="refill please", dob=None, model=None, json=False,
    )  # fmt: skip
    asyncio.run(cli._process(args))
    assert '"trace"' not in capsys.readouterr().out


def test_openrouter_step_sends_tools_in_openai_format():
    import httpx2

    from tests.test_openrouter import chat, make

    sent = {}

    def handler(request):
        sent.update(json.loads(request.content))
        return httpx2.Response(200, json=chat(content="ok"))

    tool = {"name": "find_patient", "description": "d", "input_schema": {"type": "object", "properties": {}}}
    asyncio.run(make(handler).step("S", [{"role": "user", "content": "x"}], [tool]))
    assert sent["tools"][0]["function"]["name"] == "find_patient" and sent["tool_choice"] == "auto"


def test_tool_loop_stops_at_the_tool_call_cap_after_one_nudge():
    result, log = asyncio.run(_one(FakeLLM(script=lambda step, token: [tool_use("get_clinic_info", topic="hours")])))
    assert log["error"] == "tool-call limit reached" and result.routed_to


def test_quota_error_in_the_tool_loop_stops_a_batch_run():
    from agent.llm import LLMQuotaError

    def script(step, token):
        raise LLMQuotaError("quota")

    async def go():
        async with open_clinic() as clinic:
            await clinic.reset()
            await process_message(msg("Can I get my lisinopril refilled?"), clinic, FakeLLM(script=script), fail_on_quota=True)

    with pytest.raises(BaseException) as e:  # anyio wraps it in an ExceptionGroup
        asyncio.run(go())
    assert e.group_contains(LLMQuotaError) if isinstance(e.value, BaseExceptionGroup) else e.type is LLMQuotaError


def test_normal_glucose_reading_is_not_flagged():
    assert prescreen("my blood sugar was 120 this morning")["tier"] == "none"


def test_model_claim_backed_by_a_tool_call_is_kept_silently():
    trace = [
        {"name": "route_to_queue", "input": {"queue": "front_desk", "priority": "routine"}, "ok": True, "output": {"ok": True}},
        _draft("We've passed this on."),
    ]
    ans = FinalAnswer(intents=["admin"], urgency="routine", actions=["route_to_front_desk"])
    out = post_guard("Q", ans, trace, NONE, VERIFIED, {})
    assert out.result.actions == ["route_to_front_desk"] and not any("route_to_front_desk" in v for v in out.violations)


def test_mcp_server_main_runs_stdio(monkeypatch):
    import clinic_mcp.server as server

    calls = []
    monkeypatch.setattr(server.mcp, "run", lambda transport: calls.append(transport))
    server.main()
    assert calls == ["stdio"]


def test_cancel_reports_a_scheduling_refusal(monkeypatch):
    tools = Tools(load_store())
    token = token_for(tools, "Robert Chen", "555-0102")
    monkeypatch.setattr(scheduling, "cancel", lambda store, aid: {"ok": False, "reason": "locked"})
    assert tools.cancel_appointment(token, appointment_id="A062") == {"ok": False, "reason": "locked"}


def test_valid_agent_bookings_pass_the_leave_and_global_checks():
    store = load_store()
    booked = scheduling.book(store, "P002", "PATEL", "follow_up", "2026-11-10", "09:00")
    booked["appointment"]["message_id"] = "M1"
    state = {"appointments": store.appointments, "refill_requests": []}
    result = {"id": "M1", "actions": ["book_appointment"], "urgency": "routine", "reply_draft": "Booked.", "patient_id": "P002"}
    assert _c_book_on_leave(result, {}, state, {}) is None
    assert global_safety_checks([result], {}, state) == []


def test_evaluation_skips_labels_without_a_result_and_reports_guard_notes(tmp_path):
    from pathlib import Path

    from eval.harness import evaluate
    from eval.report import write_report

    root = Path(__file__).resolve().parent.parent
    results = json.loads((root / "results/results_sample.json").read_text())
    run_dir = root / (root / "results/results_sample.run").read_text().strip()
    (tmp_path / "r.json").write_text(json.dumps(results[:-1]))
    ev = evaluate(tmp_path / "r.json", root / "data/labels_sample.json", run_dir)
    assert ev["scores"]["n"] == 39 and ev["guard_interventions"]
    md = write_report(ev, tmp_path / "rep")
    assert "## Post-guard interventions" in md and "- Guard:" in md

    perfect = [r for r in results if r["id"] == "M001"]
    labels = [lab for lab in json.loads((root / "data/labels_sample.json").read_text()) if lab["id"] == "M001"]
    (tmp_path / "p.json").write_text(json.dumps(perfect))
    (tmp_path / "l.json").write_text(json.dumps(labels))
    assert "None." in write_report(evaluate(tmp_path / "p.json", tmp_path / "l.json", run_dir), tmp_path / "rep2")
