"""The conversational actions have exact meanings; the guard applies them so the output vocabulary is consistent.

Root cause (eval run 20261022T055748Z): the model listed every quality of its reply as an action (a polite reply
became `acknowledge`, a booking confirmation became `offer_appointment`, a routing explanation became
`answer_directly`). These rules come from the action definitions, not from any message or label.
"""

from agent.safety import post_guard
from agent.schema import FinalAnswer

VERIFIED = {"status": "verified_patient", "patient_id": "P002", "candidate_patient_ids": ["P002"]}
NO_FLAG = {"tier": "none", "matches": [], "language": "en"}


def call(name, ok=True, **output):
    return {"name": name, "input": output.pop("input", {}), "ok": ok, "output": {"ok": ok, **output}}


def actions(model_actions, trace, intents=("refill",)):
    trace = [*trace, call("draft_reply", input={"text": "Thanks, done.", "language": "en"})]
    ans = FinalAnswer(intents=list(intents), urgency="routine", actions=list(model_actions))
    return post_guard("A1", ans, trace, NO_FLAG, VERIFIED, {}).result.actions


def test_acknowledge_only_when_nothing_else_was_done():
    assert actions(["acknowledge"], [call("prepare_refill_for_approval", request={"id": "R"})]) == ["prepare_refill_for_approval"]
    assert actions(["acknowledge"], [], intents=["other"]) == ["acknowledge"]


def test_a_booking_is_not_also_an_offer():
    booked = [call("book_appointment", appointment={"id": "A1", "date": "2026-11-17"})]
    assert actions(["offer_appointment"], booked, intents=["schedule"]) == ["book_appointment"]
    moved = [call("reschedule_appointment", appointment={"id": "A1", "date": "2026-11-17"})]
    assert actions(["offer_appointment"], moved, intents=["reschedule"]) == ["reschedule_appointment"]


def test_offer_without_booking_is_kept():
    assert actions(["offer_appointment"], [], intents=["schedule"]) == ["offer_appointment"]


def test_answer_directly_only_for_public_information_questions():
    routed = [call("route_to_queue", input={"queue": "billing", "priority": "routine"})]
    assert actions(["answer_directly"], routed, intents=["billing"]) == ["route_to_billing"]
    assert actions(["answer_directly"], [], intents=["admin"]) == ["answer_directly"]
    assert actions(["answer_directly", "offer_new_patient_booking"], [], intents=["new_patient"]) == [
        "offer_new_patient_booking", "answer_directly"]


def test_refill_needing_a_visit_offers_an_appointment_not_alternatives():
    trace = [call("check_refill_eligibility", decision="needs_visit"),
             call("route_to_queue", input={"queue": "provider_refills", "priority": "routine"})]
    out = actions(["offer_alternatives", "acknowledge"], trace)
    assert out == ["route_to_provider", "refill_needs_visit", "offer_appointment"]


def test_alternatives_kept_when_a_requested_booking_was_impossible():
    refused = [call("book_appointment", ok=False, violations=["provider_leave"])]
    assert actions(["offer_alternatives"], refused, intents=["schedule"]) == ["offer_alternatives"]
