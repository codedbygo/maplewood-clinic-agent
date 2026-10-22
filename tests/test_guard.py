from agent.safety import EMERGENCY_TEMPLATE, post_guard
from agent.schema import FinalAnswer

VERIFIED = {"status": "verified_patient", "patient_id": "P002", "candidate_patient_ids": ["P002"]}
UNVERIFIED = {"status": "unverified", "patient_id": None, "candidate_patient_ids": ["P013"]}
NO_FLAG = {"tier": "none", "matches": [], "language": "en"}
EMERG = {"tier": "emergency", "matches": ["chest_pain"], "language": "en"}
URGENT = {"tier": "urgent_clinical", "matches": ["low_mood"], "language": "en"}


def call(name, ok=True, **output):
    return {"name": name, "input": output.pop("input", {}), "ok": ok, "output": {"ok": ok, **output}}


def draft(text):
    return call("draft_reply", input={"text": text, "language": "en"})


def route(queue, priority="routine"):
    return call("route_to_queue", input={"queue": queue, "priority": priority, "summary": "s"})


def answer(**kw):
    base = dict(intents=["refill"], urgency="routine", actions=[], emergency=False)
    base.update(kw)
    return FinalAnswer(**base)


def run(ans, trace, screen=NO_FLAG, verification=VERIFIED, context=None):
    return post_guard("M1", ans, trace, screen, verification, context or {})


def test_unknown_action_is_dropped_and_logged():
    out = run(answer(actions=["acknowledge", "approve_refill"]), [draft("Thanks!")])
    assert "approve_refill" not in out.result.actions
    assert any("approve_refill" in v for v in out.violations)


def test_claimed_booking_without_trace_is_dropped():
    out = run(answer(intents=["schedule"], actions=["book_appointment"]), [draft("Booked!")])
    assert "book_appointment" not in out.result.actions
    assert any("book_appointment" in v for v in out.violations)


def test_tool_backed_actions_come_from_trace():
    trace = [call("book_appointment", appointment={"id": "A171"}), draft("You are booked.")]
    out = run(answer(intents=["schedule"], actions=[]), trace)
    assert out.result.actions == ["book_appointment"]
    assert out.result.tool_calls == ["book_appointment", "draft_reply"]


def test_refused_booking_does_not_count():
    trace = [call("book_appointment", ok=False, violations=["provider_leave"]), draft("Here are other times.")]
    out = run(answer(intents=["schedule"], actions=["offer_alternatives"]), trace)
    assert out.result.actions == ["offer_alternatives"]


def test_refill_decisions_become_actions_and_require_provider_route():
    trace = [call("check_refill_eligibility", decision="needs_visit"), draft("Please book a visit.")]
    out = run(answer(actions=["offer_appointment"]), trace)
    assert {"refill_needs_visit", "offer_appointment", "route_to_provider"} <= set(out.result.actions)
    assert ("provider_refills", "routine") in [(r["queue"], r["priority"]) for r in out.extra_routes]


def test_too_early_is_derived():
    trace = [call("check_refill_eligibility", decision="too_early", earliest_date="2026-11-17"), draft("From Nov 17.")]
    assert run(answer(), trace).result.actions == ["refill_too_early"]


def test_controlled_refill_without_route_gets_provider_route():
    trace = [call("check_refill_eligibility", decision="controlled_route_provider"), draft("Sent to your provider.")]
    out = run(answer(), trace)
    assert "route_to_provider" in out.result.actions


def test_prepare_route_is_a_queue_not_an_action():
    trace = [call("prepare_refill_for_approval", request={"id": "RR001"}), draft("Sent for approval.")]
    out = run(answer(), trace)
    assert out.result.actions == ["prepare_refill_for_approval"]
    assert out.result.routed_to == ["provider_refills"]


def test_emergency_screen_forces_template_and_escalation():
    out = run(answer(intents=["clinical"], actions=["answer_directly"]), [draft("Try aspirin and rest.")], screen=EMERG)
    assert out.result.actions == ["escalate_emergency"]
    assert out.result.urgency == "emergency"
    assert out.result.reply_draft == EMERGENCY_TEMPLATE["en"]
    assert ("clinician_urgent", "emergency") in [(r["queue"], r["priority"]) for r in out.extra_routes]


def test_emergency_screen_floor_cannot_be_lowered_by_llm():
    out = run(answer(intents=["clinical"], urgency="routine"), [route("clinician_urgent", "emergency"), draft(EMERGENCY_TEMPLATE["en"])], screen=EMERG)
    assert out.result.urgency == "emergency"


def test_urgent_screen_without_clinician_route_gets_one():
    trace = [call("prepare_refill_for_approval", request={"id": "RR1"}), draft("Refill sent.")]
    out = run(answer(intents=["refill", "clinical"], urgency="routine"), trace, screen=URGENT)
    assert out.result.urgency == "urgent"
    assert "route_to_clinician" in out.result.actions
    assert ("clinician_urgent", "urgent") in [(r["queue"], r["priority"]) for r in out.extra_routes]


def test_urgent_screen_satisfied_by_next_day_sick_visit():
    trace = [call("book_appointment", appointment={"id": "A171", "date": "2026-11-10", "visit_type": "sick_visit"}), draft("Booked tomorrow.")]
    out = run(answer(intents=["schedule", "clinical"], urgency="urgent"), trace, screen=URGENT,
              context={"today": "2026-11-09", "next_business_day": "2026-11-10"})
    assert out.extra_routes == []
    assert "route_to_clinician" not in out.result.actions


def test_unverified_sender_gets_null_patient_and_no_phi():
    ctx = {"phi_terms": ["2026-11-11", "13:00"]}
    out = run(answer(intents=["third_party"], actions=["decline_disclosure"]),
              [draft("Grace has an appointment on 2026-11-11 at 13:00.")], verification=UNVERIFIED, context=ctx)
    assert out.result.patient_id is None
    assert "2026-11-11" not in out.result.reply_draft
    assert any("phi" in v.lower() for v in out.violations)


def test_clinical_explanation_is_replaced_and_routed():
    out = run(answer(intents=["clinical"], actions=["answer_directly"]),
              [draft("High TSH means that your thyroid is underactive; you should take more levothyroxine.")])
    assert "means that" not in out.result.reply_draft
    assert "route_to_clinician" in out.result.actions
    assert "answer_directly" not in out.result.actions


def test_missing_reply_falls_back_to_acknowledgment_and_front_desk():
    out = run(answer(intents=["other"], actions=[]), [])
    assert out.result.reply_draft
    assert "route_to_front_desk" in out.result.actions


def test_no_action_only_when_alone():
    out = run(answer(intents=["spam"], actions=["no_action", "acknowledge"]), [draft("You are welcome!")])
    assert out.result.actions == ["acknowledge"]


def test_verified_patient_id_is_set():
    out = run(answer(actions=["acknowledge"]), [draft("Thanks!")])
    assert out.result.patient_id == "P002"


def test_flag_and_routes_derived():
    trace = [call("flag_suspicious_instruction"), route("billing"), draft("ok")]
    out = run(answer(intents=["billing"]), trace)
    assert set(out.result.actions) == {"flag_suspicious_instruction", "route_to_billing"}
    assert out.result.routed_to == ["billing"]
